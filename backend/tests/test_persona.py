import re

from backend.chat.persona import (
    BANNED_PHRASES,
    PERSONA_FULL,
    PERSONA_TURN_REMINDER,
    build_user_profile_block,
)

_BANNED_RE = re.compile("|".join(re.escape(p) for p in BANNED_PHRASES), re.IGNORECASE)


def contains_banned(text: str) -> bool:
    return bool(_BANNED_RE.search(text or ""))


def test_banned_detector_catches_brochure_lines():
    bad = [
        "Right, you're focused on product management. That's a field with so much potential.",
        "Great question! Let me help.",
        "It sounds like you want AI.",
        "AI is a fascinating space.",
    ]
    for line in bad:
        assert contains_banned(line), f"should have flagged: {line}"


def test_banned_detector_passes_clean_lines():
    good = [
        "PM, got it. How long have you been at it?",
        "Five years in, nice. What's pulling you toward AI?",
        "Cool, that narrows it. How many hours a week can you give?",
    ]
    for line in good:
        assert not contains_banned(line), f"should NOT have flagged: {line}"


def test_persona_full_and_reminder_have_no_em_dashes():
    assert "—" not in PERSONA_FULL
    assert "—" not in PERSONA_TURN_REMINDER


def test_profile_block_lists_filled_and_open_slots():
    slots = {"current_role": "PM", "years_experience": 5, "domain_interest": ["AI / ML"]}
    block = build_user_profile_block(slots, open_slots=["can_code", "weekly_hours"], last_asked="years_experience")
    assert "Current role: PM" in block
    assert "Years experience: 5" in block
    assert "AI / ML" in block
    assert "Slots still open:" in block
    assert "Can code" in block
    assert "Last slot asked: Years experience" in block


def test_profile_block_handles_empty():
    block = build_user_profile_block({}, open_slots=["years_experience"], last_asked=None)
    assert "(nothing yet)" in block
    assert "Last slot asked: none" in block
