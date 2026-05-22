"""FastAPI app for the upGrad course concierge.

Endpoints:
- POST /api/chat               SSE stream: extractor → planner → recommender (when ready)
- POST /api/recommend          force-recommend regardless of slot state
- POST /api/course/{slug}/ask  SSE stream: course-specific Q&A (Task 9.4)
- POST /api/compare            structured course comparison (Task 9.5)
- GET  /api/courses/{slug}     full course detail (joined tags + modules)
- GET  /api/session/{id}       debug dump of slot state
- GET  /healthz                health probe
"""

from __future__ import annotations

import json
import os
from typing import AsyncIterator, Iterator

import pydantic
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
from sqlalchemy.orm import Session

from backend.chat.extractor import classify_intent, extract_slots
from backend.chat.linter import lint as voice_lint
from backend.chat.persona import (
    HOOK_MESSAGE,
    PERSONA_FULL,
    PERSONA_TURN_REMINDER,
    build_user_profile_block,
)
from backend.chat.planner import (
    BROWSE_ALL,
    CONFIRM_RECOMMEND,
    READY,
    STEER_BACK,
    plan_next,
    record_question,
    should_steer_back,
)
from backend.chat.recommender import browse_top, build_comparison, recommend, recommend_all
from backend.chat.slots import SLOT_PHRASINGS, SLOT_QUICK_REPLIES
from backend.chat.summarizer import maybe_summarize
from backend.chat.course_qa import get_course_by_slug, stream_course_answer
from backend.chat.lead_trigger import decide as lead_decide
from backend.chat.lead_templates import pick_opener
from backend.chat.redaction import scrub_history_for_llm
from backend.routes.leads import router as leads_router
from backend.models import Course, CourseModule, CourseTag, get_engine, get_session_factory
from backend.schemas import (
    ChatRequest,
    CourseDetail,
    Recommendation,
    RecommendRequest,
    SessionDump,
)
from backend.store import db_session, get_or_create_session, get_session


# Local directive markers (post-recommendation intents that bypass the slot flow).
MORE_CARDS = "MORE_CARDS"
ALL_CARDS = "ALL_CARDS"
FILTER_CHANGE = "FILTER_CHANGE"
COMPARE = "COMPARE"
DONE = "DONE"
COURSE_QA = "COURSE_QA"
LEAD_FORM = "LEAD_FORM"
PAGE_SIZE = 3

# The user wants to leave a course thread and see other/new courses.
import re as _re
EXIT_FOCUS_RE = _re.compile(
    r"\b(show me (?:more|other|another)|other (?:courses?|options?|programs?|programmes?)|"
    r"different (?:courses?|options?)|something else|see (?:all|more|other)|more options|"
    r"new search|start over|any other|what else|go back)\b",
    _re.IGNORECASE,
)
_COURSE_MATCH_STOPWORDS = {
    "the", "and", "for", "with", "from", "program", "programme", "course", "courses",
    "certificate", "certification", "executive", "online", "upgrad", "post", "graduate",
    "advanced", "professional", "management", "data", "science",
}
# (title phrase, message regex) — lets "AI"/"ML"/"DS" abbreviations match full titles.
_COURSE_ALIASES = [
    ("artificial intelligence", r"\bai\b"),
    ("machine learning", r"\bml\b"),
    ("data science", r"\b(ds|data sci)\b"),
    ("generative", r"\bgen[- ]?ai\b"),
]

load_dotenv()


app = FastAPI(title="upGrad Course Concierge", version="0.1.0")


def _allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "").strip()
    defaults = ["http://localhost:5173", "http://127.0.0.1:5173"]
    if not raw:
        return defaults
    extra = [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    return list(dict.fromkeys(defaults + extra))


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lead capture (PII firewall) — a separate route that never touches OpenAI.
app.include_router(leads_router)


# ---------- helpers --------------------------------------------------------------

def _openai() -> OpenAI:
    return OpenAI()


def _friendly_error(exc: Exception) -> str:
    """User-facing message for a failed turn. The raw exception is logged, never shown."""
    import logging

    logging.getLogger(__name__).warning("turn error: %r", exc)
    msg = str(exc).lower()
    if "rate limit" in msg or "rate_limit" in msg or "429" in msg or "quota" in msg:
        return "I'm getting a lot of requests right now. Give me a few seconds and try that again."
    if "timeout" in msg or "timed out" in msg:
        return "That took longer than expected on my end. Mind trying again?"
    return "Something hiccuped on my end. Could you try that again in a moment?"


def _sse(event: str, data: dict | str) -> str:
    if not isinstance(data, str):
        data = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n"


LENGTH_RULES = (
    "Style rules for this reply:\n"
    "- 2 to 3 sentences. 28 to 50 words. Hard cap 60.\n"
    "- Start with a complete sentence. Never start with 'is', 'to', 'and'.\n"
    "- React to the SPECIFIC thing they just told you (their actual answer), not their overall "
    "goal. Build the next question off that detail.\n"
    "- Do NOT validate or comment on their goal every turn. Ban empty praise: 'big leap', "
    "'rewarding', 'solid foundation', 'great choice', 'exciting journey', 'good move'. Skip it "
    "and engage with substance.\n"
    "- Vary the SHAPE of each reply from your previous one. If your last message opened with a "
    "reaction, open this one with the question directly. Never reuse the same opener two turns "
    "in a row. Do not begin with the same word twice running.\n"
    "- BANNED stock openers: 'It sounds like', 'It's great that', 'It's good to hear', 'I see "
    "that', 'I understand', 'That's awesome', 'I'm glad'.\n"
    "- No em dashes. No bullet lists. No generic enthusiasm ('fascinating', 'exciting', "
    "'amazing', 'I love that')."
)


def _directive_text(hint: str | None, phrasing: str | None, state) -> str:
    """Build the per-turn system directive (length rules + what to do this turn)."""
    import random
    from backend.chat.persona import (
        ACK_THEN_ASK_TEMPLATES,
        RECOMMEND_TRANSITION_TEMPLATES,
        CONFIRM_RECOMMEND_TEMPLATES,
    )
    
    def _pick_template(kind: str, templates: list[str]) -> str:
        used = state.used_templates[kind]
        available = [i for i in range(len(templates)) if i not in used]
        if not available:
            used.clear()
            available = list(range(len(templates)))
        idx = random.choice(available)
        used.append(idx)
        return templates[idx]

    base = LENGTH_RULES + "\n\n"
    if hint == READY:
        template = _pick_template("recommend_transition", RECOMMEND_TRANSITION_TEMPLATES)
        return base + (
            "The planner says READY_TO_RECOMMEND. "
            f"Use this response shape: {template} "
            "Do not list features."
        )
    if hint == BROWSE_ALL:
        return base + (
            "The user asked to browse the catalog. Reply with one short handoff line under 15 "
            "words. Example: \"Here is a quick slice of the catalog, see what catches your eye.\""
        )
    if hint == STEER_BACK:
        last_open = state.open_slots()[0] if state.open_slots() else None
        ph = (SLOT_PHRASINGS.get(last_open, [phrasing or ""]) or [""])[0]
        return base + (
            "The user has drifted off topic. Acknowledge their digression in under 8 words, then "
            f"gently circle back to what we still need. Suggested phrasing: \"{ph}\"."
        )
    if hint == CONFIRM_RECOMMEND:
        template = _pick_template("confirm_recommend", CONFIRM_RECOMMEND_TEMPLATES)
        return base + (
            "The planner says CONFIRM_RECOMMEND: user asked to see courses but we have fewer than "
            "5 hard slots filled. "
            f"Use this response shape: {template} "
            "Keep it under 20 words. Example: \"Happy to, I'll have sharper picks with a couple more details — but I can take "
            "a swing now. Which?\""
        )
    if hint == MORE_CARDS:
        return base + (
            "The user wants more options. Reply with one short line handing off to the new cards, "
            "under 15 words. Example: \"Sure, a few more worth a look.\" Do not list features."
        )
    if hint == ALL_CARDS:
        return base + (
            "The user asked for ALL courses that match. Reply with the concrete count in one sentence "
            "under 20 words. Example: \"Here are all 14 that match your filters — the right rail's got them.\""
            " If fewer than 5 match, note that and suggest loosening one filter."
        )
    if hint == FILTER_CHANGE:
        return base + (
            "The user refined what they want. Acknowledge the new constraint in under 10 words, "
            "then hand off to the refreshed cards. Example: \"Cheaper it is, here is what fits.\""
        )
    if hint == COMPARE:
        return base + (
            "The user wants a comparison of courses already shown. Compare them in plain prose "
            "using the recommended-course context. 2 to 4 sentences. No new cards, no bullet lists."
        )
    if hint == DONE:
        return base + (
            "The user seems satisfied or wrapping up. Reply with one warm, brief closing line. "
            "Offer to keep going if they want, but do not push."
        )
    if hint:
        ph = phrasing or hint.replace("_", " ")
        template = _pick_template("ack_then_ask", ACK_THEN_ASK_TEMPLATES)
        
        # Get last 3 assistant openers
        assistant_msgs = [m["content"] for m in state.messages if m["role"] == "assistant"]
        openers = [" ".join(m.split()[:5]) for m in assistant_msgs[-3:]]
        mimic_rule = f"\nDo NOT mimic these previous openers from this session: {', '.join(openers)}" if openers else ""
        
        return base + (
            f"Probe the slot '{hint}' next. Suggested phrasing: \"{ph}\". "
            f"Use this response shape: {template}{mimic_rule}"
        )
    return base


def _build_chat_messages(state, directive: str, recent_window: list[dict], is_first_turn: bool) -> list[dict]:
    msgs: list[dict] = [
        {"role": "system", "content": PERSONA_FULL if is_first_turn else PERSONA_TURN_REMINDER}
    ]
    last_asked = state.asked_history[-1] if state.asked_history else None
    msgs.append({
        "role": "system",
        "content": build_user_profile_block(state.slot_values, state.open_slots(), last_asked),
    })
    if state.history_summary:
        msgs.append({"role": "system", "content": f"Earlier conversation summary: {state.history_summary}"})
    if state.recommended_context:
        msgs.append({
            "role": "system",
            "content": (
                "Reference: these courses have already been shown to this user. Answer follow-up "
                "questions about instructors, faculty, fees, duration, or any detail from this data. "
                "Do not say you cannot look it up.\n\n"
                + json.dumps(state.recommended_context, ensure_ascii=False, indent=2)
            ),
        })
    if state.lead_captured:
        msgs.append({
            "role": "system",
            "content": (
                "The user has already shared their contact details with the team. Do not ask for "
                "them again or offer to connect them. Just keep helping with their questions."
            ),
        })
    # PII firewall: mask any stray email/phone and collapse redacted turns to a marker.
    msgs.extend(scrub_history_for_llm(recent_window))
    if directive:
        msgs.append({"role": "system", "content": directive})
    return msgs


_DASH_REPLACEMENTS = {
    "—": ", ",  # em dash —
    "–": ", ",  # en dash –
}


def _strip_dashes(text: str) -> str:
    for src, dst in _DASH_REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text


def _generate_assistant(messages: list[dict], client: OpenAI) -> str:
    model = os.getenv("OPENAI_MODEL_CHAT", "gpt-4o-mini")
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.75,
    )
    content = resp.choices[0].message.content or ""
    return _strip_dashes(content)


_COURSE_QA_CORRECTION = (
    " Do not mention data, sources, or that anything is unavailable. Speak as an upGrad "
    "insider. If a detail is unknown, describe how upGrad programmes of this type usually "
    "work, then point to the course page warmly. At least two sentences."
)


def _answer_course(course, question: str, client: OpenAI, lead_handoff: bool = False) -> str:
    """Generate a course-QA answer, then lint+regen once if it leaks jargon or punts.

    With lead_handoff=True the answer ends by segueing naturally into a chat-with-the-team
    offer (the lead form renders right after), so the opener is contextual, not canned.
    """
    def gen(extra: str = "") -> str:
        return _strip_dashes(
            "".join(stream_course_answer(
                course, question, PERSONA_TURN_REMINDER + extra, client=client, lead_handoff=lead_handoff
            ))
        )

    answer = gen()
    if voice_lint(answer):
        answer = gen(_COURSE_QA_CORRECTION)
    return answer


# ---------- endpoints ------------------------------------------------------------

@app.api_route("/healthz", methods=["GET", "HEAD"])
def healthz() -> dict:
    # GET and HEAD both supported — uptime monitors often probe with HEAD.
    return {"ok": True}


@app.get("/api/hook")
def hook() -> dict:
    return {"message": HOOK_MESSAGE}


def _store_recommended_context(state, recommendations: list[dict], *, append: bool) -> None:
    ctx = [
        {
            "slug": r["course_slug"],
            "title": r["title"],
            "provider": r.get("provider"),
            "programme_type": r.get("programme_type"),
            "duration_label": r.get("duration_label"),
            "fee_bucket": r.get("fee_bucket"),
            "why_this_fits": r.get("why_this_fits"),
            "faculty": r.get("faculty") or [],
        }
        for r in recommendations
    ]
    slugs = [r["course_slug"] for r in recommendations]
    if append:
        state.recommended_context += ctx
        state.recommended_slugs += [s for s in slugs if s not in state.recommended_slugs]
    else:
        state.recommended_context = ctx
        state.recommended_slugs = list(slugs)
    # Start the lead-capture clock the first time we show recommendations.
    if recommendations and state.turns_since_first_recommendation < 0:
        state.turns_since_first_recommendation = 0


def _progress(state) -> dict:
    from backend.chat.slots import HARD_SLOTS

    filled = sum(1 for s in HARD_SLOTS if state.slot_values.get(s) not in (None, "", []))
    return {"filled": filled, "total": len(HARD_SLOTS)}


def _match_recommended_course(state, message: str) -> str | None:
    """Return the slug of a recommended course the message clearly names, else None.

    Scored by overlap of distinctive provider/title tokens. A provider hit is strong
    (e.g. 'IIIT Bangalore' -> 'iiit', 'bangalore'); title words add 1 each. Threshold 2.
    """
    msg = (message or "").lower()
    msg_tokens = set(_re.findall(r"[a-z]{3,}", msg))
    best_slug, best_score = None, 0
    for c in state.recommended_context:
        score = 0
        provider = (c.get("provider") or "").lower()
        for tok in _re.findall(r"[a-z]{3,}", provider):
            if tok not in _COURSE_MATCH_STOPWORDS and tok in msg_tokens:
                score += 2
        title = (c.get("title") or "").lower()
        for tok in _re.findall(r"[a-z]{4,}", title):
            if tok not in _COURSE_MATCH_STOPWORDS and tok in msg_tokens:
                score += 1
        # Abbreviations: users say "AI / ML" for "Artificial Intelligence / Machine Learning".
        for phrase, pat in _COURSE_ALIASES:
            if phrase in title and _re.search(pat, msg):
                score += 2
        if score > best_score:
            best_score, best_slug = score, c.get("slug")
    return best_slug if best_score >= 2 else None


def _plan_turn(state, message: str, client: OpenAI) -> dict:
    """Decide what this turn does. Returns a dict of directives + any recommendations."""
    # Increment turn counter for threshold fallback
    state.turn_count += 1
    # Lead-capture clocks: advance once recommendations have been shown.
    if state.turns_since_first_recommendation >= 0:
        state.turns_since_first_recommendation += 1
    state.turns_since_last_lead_offer += 1
    # Every turn after recommendations is the user continuing to engage. Counting
    # this (not specific phrases) is what lets the funnel surface the form on intent.
    if state.recommended_context:
        state.engagement_score += 1

    # Post-recommendation intents only matter once cards exist.
    intent_info = {"intent": "answering", "filter_override": None, "requested_count": None}
    if state.recommended_context:
        intent_info = classify_intent(message, state.messages, client=client)
    intent = intent_info["intent"]
    requested_count = intent_info.get("requested_count") or PAGE_SIZE

    factory = get_session_factory(get_engine())

    if intent == "more_cards" and state.recommended_context:
        page_size = requested_count
        with factory() as db:
            recs = recommend(
                db, state.slot_values, state.messages, client=client,
                offset=state.pagination_offset, limit=page_size,
                filter_override=state.last_filter_override,
                exclude_slugs=set(state.recommended_slugs),
            )
        state.pagination_offset += len(recs)
        _store_recommended_context(state, recs, append=True)
        return {"hint": MORE_CARDS, "phrasing": None, "recommendations": recs, "quick_slot": None,
                "all_count": None}

    if intent == "all_cards" and state.recommended_context:
        with factory() as db:
            recs = recommend_all(
                db, state.slot_values, client=client,
                filter_override=state.last_filter_override,
            )
        _store_recommended_context(state, recs, append=False)
        state.pagination_offset = len(recs)
        return {"hint": ALL_CARDS, "phrasing": None, "recommendations": recs, "quick_slot": None,
                "all_count": len(recs)}

    if intent == "filter_change" and state.recommended_context:
        override = intent_info.get("filter_override") or {}
        state.last_filter_override = override
        state.pagination_offset = 0
        state.recommended_slugs = []
        with factory() as db:
            recs = recommend(
                db, state.slot_values, state.messages, client=client,
                offset=0, limit=PAGE_SIZE, filter_override=override,
            )
        state.pagination_offset = len(recs)
        _store_recommended_context(state, recs, append=False)
        return {"hint": FILTER_CHANGE, "phrasing": None, "recommendations": recs, "quick_slot": None,
                "all_count": None}

    if intent == "compare" and state.recommended_context:
        return {"hint": COMPARE, "phrasing": None, "recommendations": [], "quick_slot": None,
                "all_count": None}

    if intent == "done":
        return {"hint": DONE, "phrasing": None, "recommendations": [], "quick_slot": None,
                "all_count": None}

    # Lead capture (server-side trigger, deterministic). Takes precedence once the
    # user is past recommendations and showing buying intent. The form, not the LLM,
    # collects contact details.
    lead = lead_decide(state, message)
    if lead.should_surface:
        state.turns_since_last_lead_offer = 0
        return {"hint": LEAD_FORM, "lead_course_slug": lead.course_slug, "phrasing": None,
                "recommendations": [], "quick_slot": None, "all_count": None}

    # Course focus: if the user names one of the recommended courses, answer about it
    # specifically (full course data + heuristics) and signal the frontend to keep the
    # thread on that course for follow-ups.
    if state.recommended_context and not EXIT_FOCUS_RE.search(message or ""):
        focus_slug = _match_recommended_course(state, message)
        if focus_slug:
            state.focused_course_slug = focus_slug
            state.course_qa_depth[focus_slug] = state.course_qa_depth.get(focus_slug, 0) + 1
            return {"hint": COURSE_QA, "focus_slug": focus_slug, "phrasing": None,
                    "recommendations": [], "quick_slot": None, "all_count": None}

    # Normal flow: extract slots, track off-topic streak, plan next slot.
    updates = extract_slots(state.messages, message, client=client)
    newly_filled = state.merge_extracted(updates)
    state.empty_extract_streak = 0 if updates else state.empty_extract_streak + 1
    if newly_filled:
        # ranking basis changed: reset pagination
        state.pagination_offset = 0
        state.last_filter_override = None

    hint, phrasing = plan_next(state, latest_user_msg=message)

    if hint not in (READY, BROWSE_ALL) and should_steer_back(state):
        return {"hint": STEER_BACK, "phrasing": phrasing, "recommendations": [], "quick_slot": None,
                "all_count": None}

    already_recommended = bool(state.recommended_context)

    # If we've already shown cards and nothing new came in, this is a follow-up
    # question, not a re-recommend. Answer it conversationally from the context.
    if hint == READY and already_recommended and not newly_filled:
        return {"hint": None, "phrasing": None, "recommendations": [], "quick_slot": None,
                "all_count": None}

    recs: list[dict] = []
    if hint == READY:
        with factory() as db:
            recs = recommend(db, state.slot_values, state.messages, client=client, offset=0, limit=PAGE_SIZE)
        state.pagination_offset = len(recs)
        _store_recommended_context(state, recs, append=False)
    elif hint == BROWSE_ALL:
        with factory() as db:
            recs = browse_top(db, state.slot_values, n=8)
        _store_recommended_context(state, recs, append=False)

    quick_slot = hint if hint not in (READY, BROWSE_ALL, CONFIRM_RECOMMEND) else None
    return {"hint": hint, "phrasing": phrasing, "recommendations": recs, "quick_slot": quick_slot,
            "all_count": None}


@app.post("/api/chat")
def chat(req: ChatRequest):
    """Stream a single assistant turn via SSE."""
    state = get_or_create_session(req.session_id)
    is_first_turn = not any(m["role"] == "assistant" for m in state.messages)
    state.messages.append({"role": "user", "content": req.message})

    client = _openai()
    turn = _plan_turn(state, req.message, client)
    hint = turn["hint"]
    all_count = turn.get("all_count")

    # Course-focus: answer about the named course and tell the client to keep the
    # thread on it. Follow-ups then route to /api/course/{slug}/ask via the chip.
    if hint == COURSE_QA:
        focus_slug = turn["focus_slug"]

        def course_stream() -> Iterator[bytes]:
            yield _sse("session", {"session_id": state.session_id}).encode("utf-8")
            yield _sse("progress", _progress(state)).encode("utf-8")
            factory = get_session_factory(get_engine())
            with factory() as db:
                course = get_course_by_slug(focus_slug, db)
                if course is None:
                    yield _sse("error", {"message": "course not found"}).encode("utf-8")
                    return
                yield _sse("focused_course", {
                    "slug": course.slug, "title": course.title, "provider": course.provider,
                }).encode("utf-8")
                try:
                    answer = _answer_course(course, req.message, client)
                except Exception as e:
                    yield _sse("error", {"message": _friendly_error(e)}).encode("utf-8")
                    return
            for i in range(0, len(answer), 4):
                yield _sse("token", {"value": answer[i:i + 4]}).encode("utf-8")
            state.messages.append({"role": "assistant", "content": answer})
            yield _sse("done", {"ok": True}).encode("utf-8")

        return StreamingResponse(course_stream(), media_type="text/event-stream")

    # Lead capture: answer the user's question and segue into the offer, then the form widget.
    if hint == LEAD_FORM:
        course_slug = turn.get("lead_course_slug")
        form_id = state.new_form_id()
        short_title = None
        course_obj = None
        if course_slug:
            factory = get_session_factory(get_engine())
            with factory() as db:
                course_obj = get_course_by_slug(course_slug, db)
                short_title = course_obj.title if course_obj else None

        if course_obj is not None:
            # Contextual: answer their question, then transition to the offer.
            try:
                opener = _answer_course(course_obj, req.message, client, lead_handoff=True)
            except Exception:
                opener = pick_opener(short_title)
        else:
            opener = pick_opener(None)

        def lead_stream() -> Iterator[bytes]:
            yield _sse("session", {"session_id": state.session_id}).encode("utf-8")
            yield _sse("progress", _progress(state)).encode("utf-8")
            for i in range(0, len(opener), 4):
                yield _sse("token", {"value": opener[i:i + 4]}).encode("utf-8")
            state.messages.append({"role": "assistant", "content": opener})
            yield _sse("lead_form", {
                "form_id": form_id, "course_slug": course_slug, "course_title": short_title,
            }).encode("utf-8")
            yield _sse("done", {"ok": True}).encode("utf-8")

        return StreamingResponse(lead_stream(), media_type="text/event-stream")

    # Long-conversation: summarize older turns, keep recent window.
    state.history_summary, recent_window = maybe_summarize(
        state.messages, state.history_summary, client=client
    )

    # Inject last_comparison context if available
    if state.last_comparison:
        slugs = [c["title"] for c in state.last_comparison.get("courses", [])]
        if slugs:
            recent_window = [
                {
                    "role": "system",
                    "content": (
                        "The user recently compared these courses: "
                        + ", ".join(slugs)
                        + ". They may ask follow-ups; reference the courses by short title."
                    ),
                }
            ] + recent_window

    directive = _directive_text(hint, turn["phrasing"], state)
    # For ALL_CARDS, inject the actual count into the directive
    if hint == ALL_CARDS and all_count is not None:
        directive = directive.replace(
            "Here are all 14 that match",
            f"Here are all {all_count} that match"
        )
        if all_count < 5:
            directive += (
                f" Only {all_count} strictly match — mention this and suggest loosening "
                "budget or experience as quick-reply chips."
            )
    messages_for_llm = _build_chat_messages(state, directive, recent_window, is_first_turn)

    # CONFIRM_RECOMMEND chips
    confirm_chips: list[str] = []
    if hint == CONFIRM_RECOMMEND:
        confirm_chips = ["Keep going", "Show me now"]

    def event_stream() -> Iterator[bytes]:
        yield _sse("session", {"session_id": state.session_id}).encode("utf-8")
        yield _sse("progress", _progress(state)).encode("utf-8")

        if turn["quick_slot"]:
            chips = SLOT_QUICK_REPLIES.get(turn["quick_slot"], [])
            if chips:
                yield _sse("quick_replies", {"slot": turn["quick_slot"], "options": chips}).encode("utf-8")

        if confirm_chips:
            yield _sse("quick_replies", {"slot": "confirm_recommend", "options": confirm_chips}).encode("utf-8")

        # --- Single-emission generation + lint ---
        try:
            full_text = _generate_assistant(messages_for_llm, client)
        except Exception as e:
            yield _sse("error", {"message": _friendly_error(e)}).encode("utf-8")
            return

        hits = voice_lint(full_text) if full_text else []
        if hits:
            import logging
            logging.getLogger(__name__).warning("Voice lint hit on first pass: %s", hits)
            rewrite_directive = (
                f"Your previous draft contained banned patterns: {', '.join(hits)}. "
                "Rewrite the response now without those patterns. "
                + directive
            )
            rewrite_msgs = _build_chat_messages(state, rewrite_directive, recent_window, is_first_turn)
            try:
                retry_text = _generate_assistant(rewrite_msgs, client)
                hits2 = voice_lint(retry_text) if retry_text else []
                if hits2:
                    logging.getLogger(__name__).warning(
                        "Voice lint still hitting after retry: %s", hits2
                    )
                    from backend.chat.linter import strip_banned_patterns
                    retry_text = strip_banned_patterns(retry_text, hits2)
                if retry_text:
                    full_text = retry_text
            except Exception:
                pass  # ship what we have

        if full_text:
            # Stream the final approved text in chunks to simulate typing
            chunk_size = 4
            for i in range(0, len(full_text), chunk_size):
                yield _sse("token", {"value": full_text[i:i+chunk_size]}).encode("utf-8")
            
            state.messages.append({"role": "assistant", "content": full_text})
        
        if turn["quick_slot"]:
            record_question(state, turn["quick_slot"])

        if turn["recommendations"]:
            mode = "append" if hint in (MORE_CARDS, ALL_CARDS) else "replace"
            yield _sse("recommendations", {"items": turn["recommendations"], "mode": mode}).encode("utf-8")
        yield _sse("done", {"ok": True}).encode("utf-8")

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/recommend", response_model=list[Recommendation])
def force_recommend(req: RecommendRequest, db: Session = Depends(db_session)):
    state = get_session(req.session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    exclude = set(state.recommended_slugs) if req.offset > 0 else None
    recs = recommend(
        db, state.slot_values, state.messages, client=_openai(),
        offset=req.offset, limit=req.limit, filter_override=req.filter_override,
        exclude_slugs=exclude,
    )
    if req.offset == 0:
        _store_recommended_context(state, recs, append=False)
        state.pagination_offset = len(recs)
    else:
        _store_recommended_context(state, recs, append=True)
        state.pagination_offset = req.offset + len(recs)
    return recs


@app.get("/api/courses/{slug}", response_model=CourseDetail)
def course_detail(slug: str, db: Session = Depends(db_session)):
    course = db.query(Course).filter(Course.slug == slug).one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="course not found")

    tags_by_type: dict[str, list[str]] = {}
    for t in course.tags:
        tags_by_type.setdefault(t.tag_type, []).append(t.tag_value)

    modules = [
        {
            "position": m.position,
            "name": m.name,
            "weeks": m.weeks,
            "topics": json.loads(m.topics) if m.topics else [],
        }
        for m in course.modules
    ]

    return CourseDetail(
        slug=course.slug,
        url=course.url,
        title=course.title,
        provider=course.provider,
        co_brand=course.co_brand,
        programme_type=course.programme_type,
        category=course.category,
        duration_weeks=course.duration_weeks,
        duration_label=course.duration_label,
        weekly_hours=course.weekly_hours,
        start_date=course.start_date.isoformat() if course.start_date else None,
        admission_deadline=course.admission_deadline.isoformat() if course.admission_deadline else None,
        emi_starts_from_inr=course.emi_starts_from_inr,
        fee_inr_total=course.fee_inr_total,
        fee_bucket=course.fee_bucket,
        format=course.format,
        schedule=course.schedule,
        level=course.level,
        prestige_signal=course.prestige_signal,
        hero_tagline=course.hero_tagline,
        one_line_pitch=course.one_line_pitch,
        tags=tags_by_type,
        modules=modules,
    )


@app.get("/api/session/{session_id}", response_model=SessionDump)
def session_dump(session_id: str):
    state = get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    return SessionDump(
        session_id=state.session_id,
        slot_values=state.slot_values,
        asked_history=state.asked_history,
        attempts=dict(state.attempts),
        message_count=len(state.messages),
    )


# ---------- Course Q&A endpoint (Task 9.4) ------------------------------------

class CourseAskRequest(pydantic.BaseModel):
    session_id: str | None = None
    message: str


@app.post("/api/course/{slug}/ask")
def course_ask(slug: str, req: CourseAskRequest, db: Session = Depends(db_session)):
    """Answer a follow-up about a specific course, OR surface the lead form.

    This is where most engagement happens (the user has dragged a course in), so the
    lead trigger MUST run here too, not just in /api/chat. Otherwise high-intent
    messages like "how can I enrol" never convert.
    """
    course = get_course_by_slug(slug, db)
    if course is None:
        raise HTTPException(status_code=404, detail="course not found")

    client = _openai()
    state = get_or_create_session(req.session_id)
    state.messages.append({"role": "user", "content": req.message})

    # Engagement accounting (mirrors /api/chat's clocks). Attaching a course means
    # the user has seen recommendations, so start the clock if it hasn't.
    if state.turns_since_first_recommendation < 1:
        state.turns_since_first_recommendation = 1
    state.turns_since_last_lead_offer += 1
    state.engagement_score += 1
    state.focused_course_slug = slug
    state.course_qa_depth[slug] = state.course_qa_depth.get(slug, 0) + 1

    decision = lead_decide(state, req.message)

    if decision.should_surface:
        state.turns_since_last_lead_offer = 0
        form_id = state.new_form_id()

        def lead_stream() -> Iterator[bytes]:
            # Answer their actual question, then segue into the offer (not a canned line).
            try:
                opener = _answer_course(course, req.message, client, lead_handoff=True)
            except Exception:
                opener = pick_opener(course.title)
            for i in range(0, len(opener), 4):
                yield _sse("token", {"value": opener[i:i + 4]}).encode("utf-8")
            state.messages.append({"role": "assistant", "content": opener})
            yield _sse("lead_form", {
                "form_id": form_id, "course_slug": slug, "course_title": course.title,
            }).encode("utf-8")
            yield _sse("done", {"ok": True}).encode("utf-8")

        return StreamingResponse(lead_stream(), media_type="text/event-stream")

    def event_stream() -> Iterator[bytes]:
        try:
            answer = _answer_course(course, req.message, client)
        except Exception as e:
            yield _sse("error", {"message": _friendly_error(e)}).encode("utf-8")
            return
        state.messages.append({"role": "assistant", "content": answer})
        yield _sse("token", {"value": answer}).encode("utf-8")
        yield _sse("done", {"ok": True}).encode("utf-8")

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ---------- Compare endpoint (Task 9.5) ---------------------------------------

class CompareRequest(pydantic.BaseModel):
    session_id: str
    slugs: list[str]


@app.post("/api/compare")
def compare_courses(req: CompareRequest, db: Session = Depends(db_session)):
    """Return a structured comparison of 2-3 courses and store it in the session."""
    if len(req.slugs) < 2 or len(req.slugs) > 3:
        raise HTTPException(status_code=400, detail="compare requires 2 to 3 slugs")

    state = get_session(req.session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")

    client = _openai()
    result = build_comparison(req.slugs, state.slot_values, db, client=client)
    state.last_comparison = result
    return result

