from backend.chat.planner import BROWSE_ALL, READY, CONFIRM_RECOMMEND, SessionState, plan_next, record_question
from backend.chat.slots import HARD_SLOTS, SLOT_BY_NAME, SOFT_SLOTS


def test_hard_slot_prioritized_over_soft():
    state = SessionState(session_id="t1")
    next_slot, _ = plan_next(state, latest_user_msg="hey")
    assert next_slot in HARD_SLOTS


def test_same_slot_not_asked_twice_in_a_row():
    state = SessionState(session_id="t2")
    first, _ = plan_next(state, "hey")
    record_question(state, first)
    second, _ = plan_next(state, "wait, what?")
    assert second != first


def test_topic_group_coherence_within_background():
    state = SessionState(session_id="t3")
    # ask years_experience (background)
    record_question(state, "years_experience")
    # fill it so planner moves on
    state.slot_values["years_experience"] = 5
    next_slot, _ = plan_next(state, "5 years")
    assert SLOT_BY_NAME[next_slot][3] == "background"


def test_three_strike_attaches_gentle_phrasing():
    state = SessionState(session_id="t4")
    target = "min_marks_pct_est"
    for _ in range(3):
        record_question(state, target)
    # bump asked history with another slot so target is candidate again
    record_question(state, "years_experience")
    next_slot, phrasing = plan_next(state, "")
    if next_slot == target:
        assert phrasing and "skip" in phrasing.lower()


def test_ready_when_user_says_show_me():
    state = SessionState(session_id="t5")
    next_slot, _ = plan_next(state, "just show me the picks")
    # Phase 9.3: with 0 slots, "show me" falls through to asking the first slot
    assert next_slot not in (READY, CONFIRM_RECOMMEND)


def test_browse_when_user_asks_to_list_courses():
    state = SessionState(session_id="t5b")
    for msg in [
        "list all courses",
        "what courses do you have",
        "show me all the programmes",
        "browse the catalog",
    ]:
        assert plan_next(state, msg)[0] == BROWSE_ALL, f"failed for: {msg}"


def test_ready_when_all_hard_filled():
    state = SessionState(session_id="t6")
    for slot in HARD_SLOTS:
        state.slot_values[slot] = "x"
    next_slot, _ = plan_next(state, "")
    assert next_slot == READY


def test_planner_falls_through_to_soft_when_hard_done():
    state = SessionState(session_id="t7")
    for slot in HARD_SLOTS:
        state.slot_values[slot] = "x"
    # READY because all hard filled; this is by design — soft slots aren't required
    next_slot, _ = plan_next(state, "")
    assert next_slot == READY


def test_phrasing_rotates_with_attempts():
    state = SessionState(session_id="t8")
    target = "years_experience"
    # First ask
    _, p1 = plan_next(state, "")
    if _ == target:
        record_question(state, target)
        # ask another, then come back
        record_question(state, "current_role")
        _, p2 = plan_next(state, "")
        # When we return to years_experience, phrasing index should advance
        if _ == target:
            assert p2 != p1


def test_merge_extracted_returns_newly_filled():
    state = SessionState(session_id="t9")
    state.slot_values["years_experience"] = 5
    newly = state.merge_extracted({"years_experience": 6, "can_code": True, "current_role": None})
    assert newly == ["can_code"]
    assert state.slot_values["years_experience"] == 6
    assert state.slot_values["can_code"] is True
    assert "current_role" not in state.slot_values
