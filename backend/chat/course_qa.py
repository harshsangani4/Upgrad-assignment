"""Course-specific Q&A handler (Task 9.4, rewritten in Phase 11.4).

Loads full course data from the DB, layers in programme-type heuristics and a
question-to-field router, and streams an always-helpful answer. The bot must
never punt on a top-tier question (eligibility, duration, format, fees, etc.).
"""

from __future__ import annotations

import json
import os
from typing import Any, Iterator

from openai import OpenAI
from sqlalchemy.orm import Session

from backend.chat.heuristics import heuristic_block, heuristic_for, normalize_programme_type
from backend.chat.question_router import route
from backend.models import Course


COURSE_QA_SYSTEM = """\
You're the warm, knowledgeable voice of upGrad, answering a follow-up question about ONE specific course the user is looking at. You have two layers of information to draw on.

LAYER 1 — known course details (use these first).
LAYER 2 — sensible defaults for this kind of programme (use only when a LAYER 1 detail is blank).

NEVER reveal how you work. The user must never see words like "scraped", "scraped data", "the data", "in the data", "dataset", "not specified", "not available", "no information", "I don't have", "field", "LAYER", or "database". You are an insider who knows this programme, not a system reading a table. If a detail genuinely isn't on hand, speak from how upGrad programmes of this type usually work, then point to the official page warmly. Never announce an absence.

ANSWER ROUTING:
- If LAYER 1 has the answer: give it concretely, with numbers and names.
- If LAYER 1 is blank but LAYER 2 covers it: answer from LAYER 2, soften with "typically" or "usually", and close with something like "the official upGrad page has the exact terms".
- For topics that vary by cohort (alumni community, placement guarantees, scholarships, refund specifics, exact upcoming dates): you must STILL be helpful. Lead with one genuinely useful sentence about how upGrad usually handles it, THEN point to the page for specifics. Two sentences minimum. Never reply with a bare "the upGrad page covers that."

TOP-TIER QUESTIONS (always answer with substance, never punt):
- Eligibility / degree requirements
- Duration / weekly time commitment
- Format (online/offline/hybrid) and schedule (self-paced/cohort)
- Fees / EMI options (approximate is fine)
- Who it's built for / target persona
- What you'll learn / curriculum scope
- Faculty: if names are known, give the count and an example. If not, say it's taught by upGrad's industry-expert faculty and mentors, and the official page lists the named instructors. Never say a faculty detail is missing.
- Certificate / who issues it

EXAMPLES:
GOOD (faculty, no names known): "This certificate is taught by upGrad's industry-expert faculty and practicing mentors who work in generative AI. The official upGrad page lists the named instructors for this cohort."
GOOD (placement): "upGrad usually offers placement support such as resume reviews, mock interviews, and introductions to hiring partners, rather than a blanket guarantee. The official page spells out exactly what this course includes."
BAD: "The faculty profile is not specified in the scraped data."
BAD: "The upGrad page covers placement guarantees in detail."

VOICE:
- Warm and concrete, like a senior friend who knows the catalog. No brochure phrases, no em dashes, no scripted openers.
- Reference a concrete word from the user's question.
- 2 to 4 sentences.

OPEN-ENDED FALLBACK:
- If the user message is open-ended like "tell me more", "what is this", "summary" — give a 2 to 3 sentence overview using title, programme_type, duration, top 2 tools, and primary target role. Always answer.
"""


def _tags_by_type(course: Course) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for t in course.tags:
        out.setdefault(t.tag_type, []).append(t.tag_value)
    return out


def _faculty_names(tags_by_type: dict[str, list[str]], limit: int = 6) -> list[str]:
    return [v.split("|")[0].strip() for v in tags_by_type.get("faculty", [])[:limit]]


def _ptk(course: Course) -> str:
    key = getattr(course, "programme_type_key", None)
    if isinstance(key, str) and key:
        return key
    return normalize_programme_type(getattr(course, "programme_type", None))


def build_course_context_message(course: Course) -> str:
    """LAYER 1: assemble the grounded context block from the course ORM object."""
    eligibility = getattr(course, "eligibility_raw", None) or course.min_degree or "Not specified"
    lines: list[str] = [
        f"Course: {course.title} by {course.provider or 'upGrad'}",
        f"Programme type: {course.programme_type or 'N/A'}",
        f"Duration: {course.duration_label or 'N/A'} (~{int(course.weekly_hours or 0)}h/week)",
        f"Eligibility: {eligibility}",
        f"Minimum degree: {course.min_degree or 'Not specified'}",
        f"Minimum marks: {course.min_marks_pct or 'Not specified'}",
        f"EMI starts from: INR {course.emi_starts_from_inr or 'not listed'}",
        f"Fee bucket: {course.fee_bucket or 'N/A'}",
        f"Format: {course.format or 'N/A'}",
        f"Schedule: {course.schedule or 'N/A'}",
        f"Level: {course.level or 'N/A'}",
    ]

    modules = sorted(course.modules, key=lambda m: m.position)
    if modules:
        lines.append(f"\nModules ({len(modules)} total):")
        for m in modules:
            topics: list[str] = json.loads(m.topics) if m.topics else []
            topic_str = ", ".join(topics[:4]) if topics else "—"
            lines.append(f"  {m.position}. {m.name or 'Unnamed'} — {topic_str}")
    else:
        lines.append("\nModules: not available")

    tags_by_type = _tags_by_type(course)

    tools = tags_by_type.get("tool") or tags_by_type.get("tools") or []
    if tools:
        lines.append(f"\nTools: {', '.join(tools[:10])}")

    faculty_names = _faculty_names(tags_by_type)
    if faculty_names:
        lines.append(f"\nFaculty ({len(faculty_names)}): {', '.join(faculty_names)}")

    companies = tags_by_type.get("hiring_company") or tags_by_type.get("company") or []
    if companies:
        lines.append(f"\nTop hiring companies: {', '.join(companies[:8])}")

    roles = tags_by_type.get("target_role") or tags_by_type.get("role") or []
    if roles:
        lines.append(f"\nTarget roles: {', '.join(roles[:6])}")

    faqs = tags_by_type.get("faq", [])
    if faqs:
        lines.append("\nFAQs:")
        for faq in faqs[:5]:
            lines.append(f"  - {faq}")

    return "\n".join(lines)


def _field_display(course: Course, field: str, tags_by_type: dict[str, list[str]]) -> str | None:
    """Render a single routed field's value, or None if absent."""
    if field == "faculty":
        names = _faculty_names(tags_by_type)
        return ", ".join(names) if names else None
    if field == "modules":
        names = [m.name for m in sorted(course.modules, key=lambda m: m.position) if m.name]
        return ", ".join(names[:8]) if names else None
    if field == "tools":
        tools = tags_by_type.get("tool") or tags_by_type.get("tools") or []
        return ", ".join(tools[:10]) if tools else None
    if field == "hiring_companies":
        c = tags_by_type.get("hiring_company") or tags_by_type.get("company") or []
        return ", ".join(c[:8]) if c else None
    if field == "target_roles":
        r = tags_by_type.get("target_role") or tags_by_type.get("role") or []
        return ", ".join(r[:6]) if r else None
    if field in ("key_highlights", "certificates", "industries"):
        v = tags_by_type.get(field) or tags_by_type.get(field.rstrip("s")) or []
        return ", ".join(v[:6]) if v else None
    if field == "programme_type_key":
        return _ptk(course)
    val = getattr(course, field, None)
    if val in (None, ""):
        return None
    return str(val)


def build_relevant_fields_block(course: Course, user_msg: str) -> str:
    """Surface the fields most relevant to the question (Phase 11.5)."""
    fields = route(user_msg)
    tags_by_type = _tags_by_type(course)
    ptk = _ptk(course)
    lines = ["MOST RELEVANT FIELDS for this question:"]
    for f in fields:
        if f.startswith("<heuristic:"):
            hf = f[len("<heuristic:"):-1]
            h = heuristic_for(hf, ptk)
            if h:
                lines.append(f"- heuristic ({hf}, use only if the matching field above is null): {h}")
            continue
        val = _field_display(course, f, tags_by_type)
        lines.append(f"- {f}: {val if val else 'null (not in scraped data)'}")
    return "\n".join(lines)


def get_course_by_slug(slug: str, db: Session) -> Course | None:
    return db.query(Course).filter(Course.slug == slug).one_or_none()


def build_course_qa_messages(course: Course, question: str, persona_reminder: str) -> list[dict[str, Any]]:
    """Assemble the full message list for one course-QA turn."""
    return [
        {"role": "system", "content": COURSE_QA_SYSTEM},
        {"role": "system", "content": f"You're an expert on THIS course. {persona_reminder}"},
        {"role": "system", "content": "LAYER 1 — SCRAPED COURSE DATA:\n" + build_course_context_message(course)},
        {"role": "system", "content": "LAYER 2 — " + heuristic_block(_ptk(course))},
        {"role": "system", "content": build_relevant_fields_block(course, question)},
        {"role": "user", "content": question},
    ]


def stream_course_answer(
    course: Course,
    question: str,
    persona_reminder: str,
    client: OpenAI | None = None,
) -> Iterator[str]:
    """Yield streamed tokens answering `question` grounded in `course` data + heuristics."""
    client = client or OpenAI()
    model = os.getenv("OPENAI_MODEL_CHAT", "gpt-4o-mini")
    messages = build_course_qa_messages(course, question, persona_reminder)

    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.5,
        stream=True,
    )
    for chunk in stream:
        try:
            delta = chunk.choices[0].delta.content
        except (AttributeError, IndexError):
            delta = None
        if delta:
            yield delta
