from backend.chat.lead_trigger import decide
from backend.chat.planner import SessionState


def make_session(**kw) -> SessionState:
    s = SessionState(session_id="t")
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def test_no_trigger_pre_recommendation():
    s = make_session(turns_since_first_recommendation=-1)
    assert decide(s, "how do I apply?").should_surface is False


def test_high_intent_phrase_triggers():
    s = make_session(turns_since_first_recommendation=2)
    d = decide(s, "how do I apply?")
    assert d.should_surface and d.reason == "high_intent_phrase"


def test_deadline_triggers():
    s = make_session(turns_since_first_recommendation=2)
    assert decide(s, "when's the deadline?").should_surface is True


def test_deep_focus_triggers():
    s = make_session(
        turns_since_first_recommendation=4,
        focused_course_slug="applied-ai-iiitb",
        course_qa_depth={"applied-ai-iiitb": 3},
    )
    d = decide(s, "tell me more about the modules")
    assert d.should_surface and d.reason == "deep_focus"
    assert d.course_slug == "applied-ai-iiitb"


def test_deep_focus_two_is_not_enough():
    s = make_session(
        turns_since_first_recommendation=3,
        focused_course_slug="applied-ai-iiitb",
        course_qa_depth={"applied-ai-iiitb": 2},
        engagement_score=2,
    )
    assert decide(s, "tell me more about the modules").should_surface is False


def test_decline_blocks_for_cool_off():
    s = make_session(
        turns_since_first_recommendation=3,
        user_declined_lead=True,
        turns_since_last_lead_offer=2,
    )
    assert decide(s, "how do I apply?").should_surface is False


def test_decline_then_cool_off_then_retry():
    s = make_session(
        turns_since_first_recommendation=3,
        user_declined_lead=True,
        turns_since_last_lead_offer=5,
    )
    assert decide(s, "when's the deadline?").should_surface is True


def test_explicit_decline_marks_and_blocks():
    s = make_session(turns_since_first_recommendation=3)
    d = decide(s, "not now, just browsing")
    assert d.should_surface is False
    assert s.user_declined_lead is True


def test_already_captured_never_retriggers():
    s = make_session(turns_since_first_recommendation=3, lead_captured=True)
    assert decide(s, "how do I apply?").should_surface is False


def test_sustained_engagement_triggers_without_phrase():
    # The key conversion path: no magic phrase, just continued engagement.
    s = make_session(
        turns_since_first_recommendation=4,
        engagement_score=3,
        turns_since_last_lead_offer=6,
    )
    d = decide(s, "tell me about the curriculum")
    assert d.should_surface and d.reason == "sustained_engagement"


def test_engagement_below_threshold_does_not_trigger():
    s = make_session(turns_since_first_recommendation=2, engagement_score=2)
    assert decide(s, "what tools does it cover?").should_surface is False


def test_engagement_does_not_renag_right_after_offer():
    # Just offered last turn (turns_since_last_lead_offer small) → hold off.
    s = make_session(
        turns_since_first_recommendation=5,
        engagement_score=4,
        turns_since_last_lead_offer=1,
    )
    assert decide(s, "what about projects?").should_surface is False
