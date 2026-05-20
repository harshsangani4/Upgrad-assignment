"""Tests for persona voice and profile block.

BANNED_PHRASES was replaced by 4 structural regex patterns in v0.3.
These tests now use the linter to verify the same semantic guarantees.
"""

from __future__ import annotations

import pytest

from backend.chat.linter import lint
from backend.chat.persona import (
    BANNED_PATTERNS_DOC,
    PERSONA_FULL,
    PERSONA_TURN_REMINDER,
    build_user_profile_block,
)


# ---- Linter catches brochure lines ------------------------------------------

@pytest.mark.parametrize(
    "line",
    [
        "Right, you're focused on product management. That's a field with so much potential.",
        "That's a solid start for someone new to AI.",
        "Let's find you some options in data.",
        "Data science is an exciting space right now.",
        "I'd like to understand your goals better.",
    ],
)
def test_banned_detector_catches_brochure_lines(line: str) -> None:
    hits = lint(line)
    assert hits, f"Linter should have flagged: {line!r} (got no hits)"


@pytest.mark.parametrize(
    "line",
    [
        "PM, got it. How long have you been at it?",
        "Five years in product, makes sense. What's pulling you toward AI?",
        "Cool, that narrows it. How many hours a week can you give?",
    ],
)
def test_banned_detector_passes_clean_lines(line: str) -> None:
    hits = lint(line)
    assert not hits, f"Linter should NOT have flagged: {line!r} (got {hits})"


# ---- PERSONA_FULL mentions banned patterns (as instructions, not output) ----
# We only enforce that the short per-turn REMINDER itself never uses em dashes
# in its directive text (it's sent every turn and must be compact / clean).

def test_persona_turn_reminder_has_no_em_dash_in_directives() -> None:
    # The reminder can reference "em dashes" in words but must not use the
    # actual character as punctuation in its own directives.
    # Only true em dashes (U+2014) count; hyphens are fine.
    ALLOWED_CONTEXT = "no em dashes"  # the phrase "no em dashes" is permitted
    cleaned = PERSONA_TURN_REMINDER.replace(ALLOWED_CONTEXT, "")
    assert "\u2014" not in cleaned, (
        "PERSONA_TURN_REMINDER should not use em dash (—) as punctuation in its own directives. "
        "Found: " + repr(PERSONA_TURN_REMINDER)
    )


# ---- BANNED_PATTERNS_DOC is a non-empty docstring ---------------------------

def test_banned_patterns_doc_is_populated() -> None:
    assert len(BANNED_PATTERNS_DOC.strip()) > 100, "BANNED_PATTERNS_DOC should describe all 4 patterns"
    for pattern in ("PATTERN A", "PATTERN B", "PATTERN C", "PATTERN D"):
        assert pattern in BANNED_PATTERNS_DOC, f"{pattern} missing from BANNED_PATTERNS_DOC"


# ---- Profile block ----------------------------------------------------------

def test_profile_block_lists_filled_and_open_slots() -> None:
    slots = {"current_role": "PM", "years_experience": 5, "domain_interest": ["AI / ML"]}
    block = build_user_profile_block(slots, open_slots=["can_code", "weekly_hours"], last_asked="years_experience")
    assert "Current role: PM" in block
    assert "Years experience: 5" in block
    assert "AI / ML" in block
    assert "Slots still open:" in block
    assert "Can code" in block
    assert "Last slot asked: Years experience" in block


def test_profile_block_handles_empty() -> None:
    block = build_user_profile_block({}, open_slots=["years_experience"], last_asked=None)
    assert "(nothing yet)" in block
    assert "Last slot asked: none" in block

