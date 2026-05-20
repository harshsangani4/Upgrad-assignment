"""Tests for planner threshold logic (Task 9.3).

Scenarios:
  1. 3 hard slots filled, no "show me" → plan_next returns ASK (some slot name).
  2. 3 hard slots filled + user says "show me" → CONFIRM_RECOMMEND.
  3. Turn 13, 4 hard slots filled → READY (fallback kicks in).
  4. 5 hard slots filled (no "show me") → READY (auto-recommend).
  5. 2 hard slots filled + "show me" → ASK (too early, ignore show me).
"""

from __future__ import annotations

import pytest
from backend.chat.planner import (
    CONFIRM_RECOMMEND,
    MAX_TURNS_BEFORE_LOWERING_THRESHOLD,
    MIN_HARD_SLOTS_FOR_AUTO_RECOMMEND,
    READY,
    SessionState,
    plan_next,
)
from backend.chat.slots import HARD_SLOTS


def _state_with_slots(*slot_names: str, turn_count: int = 1) -> SessionState:
    """Create a SessionState with the given hard slots filled."""
    state = SessionState(session_id="test")
    state.turn_count = turn_count
    for name in slot_names:
        state.slot_values[name] = "some_value"
    return state


# ---- 1. 3 hard slots, no "show me" → ASK -----------------------------------

def test_3_slots_no_show_me_returns_ask() -> None:
    slots = HARD_SLOTS[:3]
    state = _state_with_slots(*slots)
    result, _ = plan_next(state, latest_user_msg="I work in finance")
    assert result not in (READY, CONFIRM_RECOMMEND), (
        f"Expected ASK (slot name) but got {result!r} with only 3 hard slots"
    )


# ---- 2. 3 hard slots + "show me" → CONFIRM_RECOMMEND -----------------------

def test_3_slots_show_me_returns_confirm() -> None:
    slots = HARD_SLOTS[:3]
    state = _state_with_slots(*slots)
    result, _ = plan_next(state, latest_user_msg="show me some courses")
    assert result == CONFIRM_RECOMMEND, (
        f"Expected CONFIRM_RECOMMEND with 3 slots + 'show me', got {result!r}"
    )


# ---- 3. Turn 13 + 4 slots → READY (fallback) --------------------------------

def test_turn_13_4_slots_fallback_to_ready() -> None:
    slots = HARD_SLOTS[:4]
    state = _state_with_slots(*slots, turn_count=MAX_TURNS_BEFORE_LOWERING_THRESHOLD + 1)
    result, _ = plan_next(state, latest_user_msg="whatever")
    assert result == READY, (
        f"Expected READY fallback at turn {state.turn_count} with 4 slots, got {result!r}"
    )


# ---- 4. 5 hard slots filled → READY (auto-recommend) -----------------------

def test_5_slots_auto_recommend() -> None:
    slots = HARD_SLOTS[:MIN_HARD_SLOTS_FOR_AUTO_RECOMMEND]
    state = _state_with_slots(*slots)
    result, _ = plan_next(state, latest_user_msg="sounds good")
    assert result == READY, (
        f"Expected READY with {MIN_HARD_SLOTS_FOR_AUTO_RECOMMEND} hard slots, got {result!r}"
    )


# ---- 5. 2 hard slots + "show me" → ASK (below forced threshold) ------------

def test_2_slots_show_me_still_asks() -> None:
    slots = HARD_SLOTS[:2]
    state = _state_with_slots(*slots)
    result, _ = plan_next(state, latest_user_msg="show me now please")
    assert result not in (READY, CONFIRM_RECOMMEND), (
        f"Expected ASK with only 2 slots + 'show me', got {result!r}"
    )


# ---- 6. All hard slots filled → READY regardless of message -----------------

def test_all_hard_slots_filled_is_ready() -> None:
    state = _state_with_slots(*HARD_SLOTS)
    result, _ = plan_next(state, latest_user_msg="whatever")
    assert result == READY
