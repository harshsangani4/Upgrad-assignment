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
    messages: list[dict[str, str]] = field(default_factory=list)
    slot_values: dict[str, Any] = field(default_factory=dict)
    asked_history: list[str] = field(default_factory=list)
    attempts: Counter = field(default_factory=Counter)
    recommended_context: list[dict[str, Any]] = field(default_factory=list)

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


def plan_next(state: SessionState, latest_user_msg: str = "") -> tuple[str, str | None]:
    """Return (next_slot_name | READY | BROWSE_ALL, suggested_phrasing or None)."""
    msg = latest_user_msg or ""
    if BROWSE_RE.search(msg):
        return BROWSE_ALL, None
    if SHOW_ME_RE.search(msg):
        return READY, None
    if _all_hard_filled(state):
        return READY, None

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
    if slot_name in (READY, BROWSE_ALL):
        return
    state.asked_history.append(slot_name)
    state.attempts[slot_name] += 1
