"""Course-QA always-helpful tests (Phase 11.4.3).

The LLM is mocked, so output assertions check the mock; the meaningful checks
assert that the assembled system prompt carries the right LAYER 1 data or
LAYER 2 heuristic so the model *could* answer.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.chat.course_qa import build_course_qa_messages, stream_course_answer


def _course(**overrides) -> MagicMock:
    c = MagicMock()
    c.title = "Job-ready Program in Data Science and Analytics"
    c.provider = "upGrad Campus"
    c.programme_type = "Bootcamp"
    c.programme_type_key = "bootcamp"
    c.duration_label = "auto"
    c.weekly_hours = None
    c.min_degree = None
    c.min_marks_pct = None
    c.eligibility_raw = None
    c.emi_starts_from_inr = None
    c.fee_inr_total = None
    c.fee_bucket = None
    c.format = None
    c.schedule = None
    c.level = "beginner"
    c.modules = []
    c.tags = [
        MagicMock(tag_type="tool", tag_value="Python"),
        MagicMock(tag_type="tool", tag_value="SQL"),
        MagicMock(tag_type="role", tag_value="Data Analyst"),
    ]
    for k, v in overrides.items():
        setattr(c, k, v)
    return c


def _system_text(course, question) -> str:
    msgs = build_course_qa_messages(course, question, "persona reminder")
    return "\n\n".join(m["content"] for m in msgs if m["role"] == "system")


def _run(course, question, mock_text) -> str:
    with patch("backend.chat.course_qa.OpenAI") as mock_openai:
        client = MagicMock()
        mock_openai.return_value = client
        chunk = MagicMock()
        chunk.choices = [MagicMock(delta=MagicMock(content=mock_text))]
        client.chat.completions.create.return_value = [chunk]
        return "".join(stream_course_answer(course, question, "persona", client=client))


# ---- Prompt wiring (the real logic under test) -------------------------------

def test_bootcamp_null_eligibility_injects_heuristic():
    course = _course(programme_type_key="bootcamp", eligibility_raw=None)
    text = _system_text(course, "any degree required?")
    # bootcamp eligibility heuristic must be present for the LLM to use
    assert "12th-pass" in text
    assert "typically" in text.lower()
    assert "official upGrad page" in text


def test_pgp_with_real_eligibility_surfaces_real_data():
    course = _course(
        programme_type="Post Graduate Programme",
        programme_type_key="pgp",
        eligibility_raw="Bachelor's degree in any discipline with minimum 50% aggregate.",
        min_degree="Bachelor's",
        min_marks_pct=50,
    )
    text = _system_text(course, "any degree required?")
    assert "Bachelor's degree in any discipline with minimum 50%" in text


def test_router_surfaces_fee_and_duration_for_multimatch():
    course = _course()
    text = _system_text(course, "what's the duration and fees?")
    assert "MOST RELEVANT FIELDS" in text
    assert "duration" in text.lower()
    assert "fee" in text.lower() or "emi" in text.lower()


# ---- Mocked-output behavior (11.4.3 table) -----------------------------------

@pytest.mark.parametrize(
    "course, question, mock_text, must_have, must_not_have",
    [
        (
            _course(programme_type_key="bootcamp", eligibility_raw=None),
            "any degree required?",
            "Typically there's no strict degree, it's open to 12th-pass folks with interest. The official upGrad page has the exact terms.",
            ["typically", "12th-pass"],
            [],
        ),
        (
            _course(
                programme_type="Post Graduate Programme", programme_type_key="pgp",
                eligibility_raw="Bachelor's degree, minimum 50% aggregate.", min_degree="Bachelor's", min_marks_pct=50,
            ),
            "any degree required?",
            "Yes, you'll need a bachelor's degree with a minimum 50% aggregate to enrol.",
            ["bachelor's", "50%"],
            [],
        ),
        (
            _course(),
            "tell me about this",
            "It's a Bootcamp in data science and analytics, built around Python and SQL for aspiring data analysts.",
            ["Bootcamp"],
            ["I don't have that on the course page"],
        ),
        (
            _course(),
            "what's the alumni Facebook group?",
            "upGrad programmes usually have an active alumni community and networking groups. The official upGrad page has the group details for this course.",
            ["upGrad page"],
            ["scraped data"],
        ),
        (
            _course(programme_type_key="bootcamp", weekly_hours=None),
            "how many hours a week?",
            "Usually around 8-12 hours a week for a bootcamp like this. The official upGrad page has the exact terms.",
            ["8-12"],
            [],
        ),
    ],
)
def test_course_qa_cases(course, question, mock_text, must_have, must_not_have):
    out = _run(course, question, mock_text)
    for s in must_have:
        assert s.lower() in out.lower(), f"missing {s!r} in {out!r}"
    for s in must_not_have:
        assert s.lower() not in out.lower(), f"unexpected {s!r} in {out!r}"


def test_system_prompt_has_answer_routing_and_open_ended():
    msgs = build_course_qa_messages(_course(), "tell me more", "persona")
    sys_text = "\n".join(m["content"] for m in msgs if m["role"] == "system")
    assert "ANSWER ROUTING" in sys_text
    assert "OPEN-ENDED FALLBACK" in sys_text
    assert "TOP-TIER QUESTIONS" in sys_text
