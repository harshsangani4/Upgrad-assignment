"""FastAPI app for the upGrad course concierge.

Endpoints:
- POST /api/chat        SSE stream: extractor → planner → recommender (when ready)
- POST /api/recommend   force-recommend regardless of slot state
- GET  /api/courses/{slug}  full course detail (joined tags + modules)
- GET  /api/session/{id}    debug dump of slot state
- GET  /healthz             health probe
"""

from __future__ import annotations

import json
import os
from typing import AsyncIterator, Iterator

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
from sqlalchemy.orm import Session

from backend.chat.extractor import extract_slots
from backend.chat.persona import HOOK_MESSAGE, PERSONA_PROMPT
from backend.chat.planner import BROWSE_ALL, READY, plan_next, record_question
from backend.chat.recommender import browse_top, recommend
from backend.chat.slots import SLOT_QUICK_REPLIES
from backend.models import Course, CourseModule, CourseTag, get_engine, get_session_factory
from backend.schemas import (
    ChatRequest,
    CourseDetail,
    Recommendation,
    RecommendRequest,
    SessionDump,
)
from backend.store import db_session, get_or_create_session, get_session

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


# ---------- helpers --------------------------------------------------------------

def _openai() -> OpenAI:
    return OpenAI()


def _sse(event: str, data: dict | str) -> str:
    if not isinstance(data, str):
        data = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n"


LENGTH_RULES = (
    "Hard rules for this reply:\n"
    "- 1 or 2 short sentences. Under 30 words total.\n"
    "- Start with a complete sentence. Never start with 'is', 'to', 'and'.\n"
    "- Acknowledge what the user said in 5-8 words, then ask exactly one question.\n"
    "- No em dashes. No bullet lists. No generic enthusiasm like 'fascinating' or 'exciting'."
)


def _build_chat_messages(state, planner_hint: str | None, suggested_phrasing: str | None) -> list[dict]:
    msgs: list[dict] = [{"role": "system", "content": PERSONA_PROMPT}]
    if state.recommended_context:
        msgs.append({
            "role": "system",
            "content": (
                "Reference: these courses have been recommended to this user in this session. "
                "If they ask about instructors, faculty, fees, duration, or any other detail, "
                "answer from this data. Do not pretend to look it up.\n\n"
                + json.dumps(state.recommended_context, ensure_ascii=False, indent=2)
            ),
        })
    msgs.extend(state.messages)
    if planner_hint == READY:
        msgs.append({
            "role": "system",
            "content": (
                LENGTH_RULES + "\n\n"
                "The planner says READY_TO_RECOMMEND. Reply with one short transition line "
                "in the persona's voice, under 12 words, then stop. Example: \"Okay, three "
                "picks coming up.\" Do not list features."
            ),
        })
    elif planner_hint == BROWSE_ALL:
        msgs.append({
            "role": "system",
            "content": (
                LENGTH_RULES + "\n\n"
                "The user asked to browse the catalog. Reply with one short line that hands "
                "off to the cards, under 15 words. Example: \"Here is a quick slice of the "
                "catalog. Tell me what catches your eye.\" Do not list features."
            ),
        })
    elif planner_hint:
        phrasing = suggested_phrasing or planner_hint.replace("_", " ")
        msgs.append({
            "role": "system",
            "content": (
                LENGTH_RULES + "\n\n"
                f"Probe the slot '{planner_hint}' next. Suggested phrasing: \"{phrasing}\". "
                "Acknowledge their last reply in 5-8 words, then ask exactly that question."
            ),
        })
    return msgs


_DASH_REPLACEMENTS = {
    "—": ", ",  # em dash —
    "–": ", ",  # en dash –
}


def _strip_dashes(text: str) -> str:
    for src, dst in _DASH_REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text


def _stream_assistant(messages: list[dict], client: OpenAI) -> Iterator[str]:
    model = os.getenv("OPENAI_MODEL_CHAT", "gpt-4o-mini")
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.6,
        stream=True,
    )
    for chunk in stream:
        try:
            delta = chunk.choices[0].delta.content
        except (AttributeError, IndexError):
            delta = None
        if delta:
            yield _strip_dashes(delta)


# ---------- endpoints ------------------------------------------------------------

@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.get("/api/hook")
def hook() -> dict:
    return {"message": HOOK_MESSAGE}


@app.post("/api/chat")
def chat(req: ChatRequest):
    """Stream a single assistant turn via SSE.

    Flow: extract slots from `req.message` → merge into session → planner picks next
    slot or READY → if READY, run recommender and emit a `recommendations` event
    alongside the streamed transition message; otherwise stream a question turn.
    """
    state = get_or_create_session(req.session_id)
    state.messages.append({"role": "user", "content": req.message})

    client = _openai()
    updates = extract_slots(state.messages, req.message, client=client)
    state.merge_extracted(updates)
    planner_hint, suggested_phrasing = plan_next(state, latest_user_msg=req.message)

    def event_stream() -> Iterator[bytes]:
        yield _sse("session", {"session_id": state.session_id}).encode("utf-8")

        # If we're going to ask a slot question, offer chips
        if planner_hint and planner_hint not in (READY, BROWSE_ALL):
            chips = SLOT_QUICK_REPLIES.get(planner_hint, [])
            if chips:
                yield _sse("quick_replies", {"slot": planner_hint, "options": chips}).encode("utf-8")

        recommendations: list[dict] = []
        if planner_hint == READY:
            factory = get_session_factory(get_engine())
            with factory() as db:
                recommendations = recommend(db, state.slot_values, state.messages, client=client)
        elif planner_hint == BROWSE_ALL:
            factory = get_session_factory(get_engine())
            with factory() as db:
                recommendations = browse_top(db, state.slot_values, n=8)

        if recommendations:
            state.recommended_context = [
                {
                    "slug": r["course_slug"],
                    "title": r["title"],
                    "provider": r.get("provider"),
                    "duration_label": r.get("duration_label"),
                    "fee_bucket": r.get("fee_bucket"),
                    "why_this_fits": r.get("why_this_fits"),
                    "faculty": r.get("faculty") or [],
                }
                for r in recommendations
            ]

        messages_for_llm = _build_chat_messages(state, planner_hint, suggested_phrasing)
        assistant_buf: list[str] = []
        try:
            for token in _stream_assistant(messages_for_llm, client):
                assistant_buf.append(token)
                yield _sse("token", {"value": token}).encode("utf-8")
        except Exception as e:
            yield _sse("error", {"message": str(e)}).encode("utf-8")
            return

        full_text = "".join(assistant_buf).strip()
        if full_text:
            state.messages.append({"role": "assistant", "content": full_text})
        if planner_hint and planner_hint not in (READY, BROWSE_ALL):
            record_question(state, planner_hint)

        if recommendations:
            yield _sse("recommendations", {"items": recommendations}).encode("utf-8")
        yield _sse("done", {"ok": True}).encode("utf-8")

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/recommend", response_model=list[Recommendation])
def force_recommend(req: RecommendRequest, db: Session = Depends(db_session)):
    state = get_session(req.session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    return recommend(db, state.slot_values, state.messages, client=_openai())


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
