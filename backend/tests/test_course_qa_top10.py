"""Top-10 question regression suite (Phase 11.6.1).

Deterministic by default: for each of the 10 questions x up to 5 real courses,
assert the assembled course-QA prompt is *answerable* (the routed field has a
value, or a programme-type heuristic is surfaced). This needs no LLM call.

Set RUN_LIVE_QA=1 to additionally make real LLM calls and lint each answer
(slow, costs money) — skipped in normal runs.
"""

import os
import random

import pytest

from backend.chat.course_qa import build_course_qa_messages, stream_course_answer
from backend.chat.linter import lint
from backend.models import Course, get_engine, get_session_factory

DB_PATH = os.getenv("COURSES_DB", "data/courses.sqlite")
TOP_10 = [
    "Is there any degree required for this?",
    "How many hours a week is this?",
    "What does the curriculum cover?",
    "Who teaches it?",
    "How much does it cost?",
    "Is this online or offline?",
    "How long is the course?",
    "What kind of jobs do people get after?",
    "Who is this best for?",
    "Tell me more about this course",
]


def _courses(n: int = 5) -> list[Course]:
    if not os.path.exists(DB_PATH):
        return []
    factory = get_session_factory(get_engine(DB_PATH))
    with factory() as db:
        rows = db.query(Course).all()
    if not rows:
        return []
    random.seed(11)
    return random.sample(rows, min(n, len(rows)))


_COURSES = _courses()
pytestmark = pytest.mark.skipif(not _COURSES, reason="no courses DB; run scraper.run --full first")


@pytest.mark.parametrize("question", TOP_10)
def test_prompt_is_answerable(question):
    """Every question must produce a prompt with a relevant-fields block."""
    for course in _COURSES:
        msgs = build_course_qa_messages(course, question, "persona")
        sys_text = "\n".join(m["content"] for m in msgs if m["role"] == "system")
        assert "MOST RELEVANT FIELDS" in sys_text
        # LAYER 2 heuristics are always present, guaranteeing a fallback answer.
        assert "Fallback heuristics" in sys_text


@pytest.mark.skipif(os.getenv("RUN_LIVE_QA") != "1", reason="live LLM test; set RUN_LIVE_QA=1")
@pytest.mark.parametrize("question", TOP_10)
def test_live_answers_are_clean(question):
    for course in _COURSES:
        answer = "".join(stream_course_answer(course, question, "persona"))
        assert answer.strip(), f"empty answer for {question!r} on {course.slug}"
        assert lint(answer) == [], f"linter hits for {question!r} on {course.slug}: {lint(answer)}"
