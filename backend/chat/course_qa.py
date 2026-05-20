"""Course-specific Q&A handler (Task 9.4).

Loads full course data from DB, builds a grounded system context, and streams
an answer to a follow-up question about that specific course.
"""

from __future__ import annotations

import json
import os
from typing import Any, Iterator

from openai import OpenAI
from sqlalchemy.orm import Session

from backend.models import Course


COURSE_QA_SYSTEM = """\
You're answering a follow-up question about ONE specific course the user is interested in.
Use only the data below — never invent fees, faculty, modules, or any facts not in this payload.
If the answer isn't in the data, say so plainly: "That's not something I have data on — the upGrad page would have it."

Same warm, concise voice as the main chat. Plain prose only. 2-3 sentences, 28-50 words.
No bullet points, no headers, no em dashes. No brochure phrases.
"""


def build_course_context_message(course: Course) -> str:
    """Assemble the grounded context block from the course ORM object."""
    lines: list[str] = [
        f"Course: {course.title} by {course.provider or 'upGrad'}",
        f"Programme type: {course.programme_type or 'N/A'}",
        f"Duration: {course.duration_label or 'N/A'} (~{int(course.weekly_hours or 0)}h/week)",
        f"Eligibility: {course.min_degree or 'Not specified'}",
        f"EMI starts from: INR {course.emi_starts_from_inr or 'not listed'}",
        f"Format: {course.format or 'N/A'}",
        f"Schedule: {course.schedule or 'N/A'}",
        f"Level: {course.level or 'N/A'}",
    ]

    # Modules
    modules = sorted(course.modules, key=lambda m: m.position)
    if modules:
        lines.append(f"\nModules ({len(modules)} total):")
        for m in modules:
            topics: list[str] = json.loads(m.topics) if m.topics else []
            topic_str = ", ".join(topics[:4]) if topics else "—"
            lines.append(f"  {m.position}. {m.name or 'Unnamed'} — {topic_str}")
    else:
        lines.append("\nModules: not available")

    # Tags by type
    tags_by_type: dict[str, list[str]] = {}
    for t in course.tags:
        tags_by_type.setdefault(t.tag_type, []).append(t.tag_value)

    # Tools
    tools = tags_by_type.get("tool") or tags_by_type.get("tools") or []
    if tools:
        lines.append(f"\nTools: {', '.join(tools[:10])}")

    # Faculty
    faculty_raw = tags_by_type.get("faculty", [])
    if faculty_raw:
        faculty_names = [v.split("|")[0].strip() for v in faculty_raw[:6]]
        lines.append(f"\nFaculty: {', '.join(faculty_names)}")

    # Hiring companies
    companies = tags_by_type.get("hiring_company") or tags_by_type.get("company") or []
    if companies:
        lines.append(f"\nTop hiring companies: {', '.join(companies[:8])}")

    # Target roles
    roles = tags_by_type.get("target_role") or tags_by_type.get("role") or []
    if roles:
        lines.append(f"\nTarget roles: {', '.join(roles[:6])}")

    # FAQs
    faqs = tags_by_type.get("faq", [])
    if faqs:
        lines.append("\nFAQs:")
        for faq in faqs[:5]:
            lines.append(f"  - {faq}")

    return "\n".join(lines)


def get_course_by_slug(slug: str, db: Session) -> Course | None:
    return db.query(Course).filter(Course.slug == slug).one_or_none()


def stream_course_answer(
    course: Course,
    question: str,
    persona_reminder: str,
    client: OpenAI | None = None,
) -> Iterator[str]:
    """Yield streamed tokens answering `question` grounded in `course` data."""
    client = client or OpenAI()
    model = os.getenv("OPENAI_MODEL_CHAT", "gpt-4o-mini")
    context_block = build_course_context_message(course)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": COURSE_QA_SYSTEM},
        {"role": "system", "content": f"You're an expert on THIS course. {persona_reminder}"},
        {"role": "system", "content": context_block},
        {"role": "user", "content": question},
    ]

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
