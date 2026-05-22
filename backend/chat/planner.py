"""Slot planner: pick the next slot to probe, or signal READY_TO_RECOMMEND.

Rules (BUILD_PLAN.md §5.4):
1. Hard slots before soft slots.
2. Never re-ask the same slot 2 turns in a row.
3. Prefer slots in the same `topic_group` as the previously asked slot.
4. After 3 failed attempts on a hard slot, return a gentle flagging phrasing.
5. If all hard slots filled OR the user says "show me", return READY_TO_RECOMMEND.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .slots import HARD_SLOTS, SLOT_BY_NAME, SLOT_PHRASINGS, SLOTS


READY = "READY_TO_RECOMMEND"
BROWSE_ALL = "BROWSE_ALL"
STEER_BACK = "STEER_BACK"
CONFIRM_RECOMMEND = "CONFIRM_RECOMMEND"

# How many hard slots must be filled before auto-recommending.
MIN_HARD_SLOTS_FOR_AUTO_RECOMMEND = 5   # of 7 hard slots
# Minimum slots required for a forced recommend (user explicitly says "show me").
MIN_HARD_SLOTS_FOR_FORCED_RECOMMEND = 3
# After this many turns, lower the threshold so we don't trap people.
MAX_TURNS_BEFORE_LOWERING_THRESHOLD = 12

# Heuristic: user said something that means "stop interviewing me, recommend".
SHOW_ME_RE = re.compile(
    r"\b(show me|just (the )?(courses?|picks?)|skip ahead|recommend(ations?)?|let'?s (see|do this)|i'?m ready)\b",
    re.IGNORECASE,
)

# Heuristic: user wants to browse the catalog directly, not slot-fill.
BROWSE_RE = re.compile(
    r"\b("
    r"list (?:me )?(?:all|the|every|some)?\s*(?:courses?|programmes?|programs?|options?)|"
    r"what (?:courses?|programmes?|programs?|options?) (?:do you have|are (?:there|available))|"
    r"all (?:the )?(?:courses?|programmes?|programs?|options?)|"
    r"available (?:courses?|programmes?|programs?|options?)|"
    r"browse (?:the )?(?:catalog|courses?)|"
    r"see (?:all|every|the) (?:courses?|programmes?|programs?|options?)|"
    r"give me (?:all|the) (?:courses?|programmes?|programs?|options?)|"
    r"show (?:me )?everything|"
    r"see everything|"
    r"catalog"
    r")\b",
    re.IGNORECASE,
)


@dataclass
class SessionState:
    session_id: str
    slot_values: dict[str, Any] = field(default_factory=dict)
    asked_history: list[str] = field(default_factory=list)
    attempts: Counter = field(default_factory=Counter)
    
    # NEW state tracking
    turn_count: int = 0
    empty_extract_streak: int = 0
    
    # Store LLM generated replies to maintain context window
    messages: list[dict[str, str]] = field(default_factory=list)
    
    # Summarized older context (to keep window short)
    history_summary: str | None = None
    
    # State around recommended cards for follow-up questions
    recommended_context: list[dict] = field(default_factory=list)
    recommended_slugs: list[str] = field(default_factory=list)
    last_filter_override: dict | None = None
    pagination_offset: int = 0
    
    last_comparison: dict | None = None

    # Course the user is currently discussing in the main chat (typed, not dragged).
    # Follow-up questions stay on this course until they ask for other courses.
    focused_course_slug: str | None = None

    used_templates: dict[str, list[int]] = field(default_factory=lambda: {
        "ack_then_ask": [],
        "recommend_transition": [],
        "course_overview": [],
        "confirm_recommend": [],
    })

    def merge_extracted(self, updates: dict[str, Any]) -> list[str]:
        """Merge new slot values; return the list of slots that newly transitioned to filled."""
        newly_filled: list[str] = []
        for k, v in updates.items():
            if v in (None, "", []):
                continue
            if k not in self.slot_values:
                newly_filled.append(k)
            self.slot_values[k] = v
        return newly_filled

    def open_slots(self) -> list[str]:
        """Hard slots not yet filled, then soft slots not yet filled."""
        order = [name for (name, _, hard, _) in SLOTS if hard]
        order += [name for (name, _, hard, _) in SLOTS if not hard]
        return [s for s in order if self.slot_values.get(s) in (None, "", [])]


def _is_filled(state: SessionState, slot_name: str) -> bool:
    v = state.slot_values.get(slot_name)
    return v not in (None, "", [])


def _all_hard_filled(state: SessionState) -> bool:
    return all(_is_filled(state, s) for s in HARD_SLOTS)


def _candidate_slots(state: SessionState, hard_only: bool) -> list[str]:
    out: list[str] = []
    last_asked = state.asked_history[-1] if state.asked_history else None
    for name, _, hard, _ in SLOTS:
        if hard_only and not hard:
            continue
        if _is_filled(state, name):
            continue
        if name == last_asked:
            continue  # never re-ask the same slot 2 turns in a row
        out.append(name)
    return out


def _hard_slots_filled_count(state: SessionState) -> int:
    return sum(1 for s in HARD_SLOTS if _is_filled(state, s))


def plan_next(state: SessionState, latest_user_msg: str = "") -> tuple[str, str | None]:
    """Return (next_slot_name | READY | BROWSE_ALL | CONFIRM_RECOMMEND, suggested_phrasing or None)."""
    msg = latest_user_msg or ""
    if BROWSE_RE.search(msg):
        return BROWSE_ALL, None

    hard_filled = _hard_slots_filled_count(state)
    show_me = bool(SHOW_ME_RE.search(msg))

    # Turn-count fallback: if the conversation has been going a long time, lower the bar.
    if state.turn_count > MAX_TURNS_BEFORE_LOWERING_THRESHOLD and hard_filled >= 4:
        return READY, None

    if _all_hard_filled(state):
        return READY, None

    if hard_filled >= MIN_HARD_SLOTS_FOR_AUTO_RECOMMEND:
        return READY, None

    if show_me:
        if hard_filled >= MIN_HARD_SLOTS_FOR_FORCED_RECOMMEND:
            # Have some data but not enough for ideal picks — ask to confirm.
            return CONFIRM_RECOMMEND, None
        # Too little data even for a forced recommend — keep gathering.
        pass  # fall through to normal ASK logic

    candidates = _candidate_slots(state, hard_only=True) or _candidate_slots(state, hard_only=False)
    if not candidates:
        return READY, None

    last_asked = state.asked_history[-1] if state.asked_history else None
    if last_asked:
        last_group = SLOT_BY_NAME[last_asked][3]
        same_group = [c for c in candidates if SLOT_BY_NAME[c][3] == last_group]
        if same_group:
            candidates = same_group

    next_slot = candidates[0]
    attempt = state.attempts[next_slot]
    phrasings = SLOT_PHRASINGS.get(next_slot, [])

    if attempt >= 3:
        # gentle: explicitly give them an out so we don't badger
        base = phrasings[0] if phrasings else f"about {next_slot.replace('_', ' ')}"
        return next_slot, f"feel free to skip this if it doesn't apply — {base}"

    if phrasings:
        return next_slot, phrasings[attempt % len(phrasings)]
    return next_slot, None


def record_question(state: SessionState, slot_name: str) -> None:
    """Mark that the assistant just asked about `slot_name`."""
    if slot_name in (READY, BROWSE_ALL, STEER_BACK):
        return
    state.asked_history.append(slot_name)
    state.attempts[slot_name] += 1


def should_steer_back(state: SessionState) -> bool:
    """True when the user has gone off-topic for 2+ consecutive turns and a slot is still open."""
    return state.empty_extract_streak >= 2 and bool(state.open_slots())
