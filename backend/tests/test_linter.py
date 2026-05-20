"""Tests for the voice linter (backend/chat/linter.py).

Asserts:
  - Every canonical example from PATTERN A-D fires lint().
  - Clean phrases return an empty list.
"""

from __future__ import annotations

import pytest
from backend.chat.linter import lint


# ---- PATTERN A — empty acknowledgement praise --------------------------------

@pytest.mark.parametrize(
    "text",
    [
        "That's a solid start for someone new to AI.",
        "That is a great foundation to build on.",
        "That's an amazing field to move into.",
        "That'll really help you stand out.",
        "This goes a long way in your career.",
        "It opens doors in the industry.",
        "This can really open up opportunities for you.",
        "This sets you up well for the transition.",
        "That's an exciting space to explore.",
        "That is an incredible opportunity.",
    ],
)
def test_pattern_a_fires(text: str) -> None:
    hits = lint(text)
    assert "PATTERN_A" in hits, f"Expected PATTERN_A to fire on: {text!r}"


# ---- PATTERN B — brochure-acknowledgement openers ---------------------------

@pytest.mark.parametrize(
    "text",
    [
        "Noted, you've got a year or two under your belt.",
        "Got it, you're in product management.",
        "Cool, you have five years of experience.",
        "Right, you're focused on data engineering.",
        "Awesome, you've been in fintech.",
        "Alright, you're looking to switch careers.",
        "Nice, you have a bachelor's degree.",
    ],
)
def test_pattern_b_fires(text: str) -> None:
    hits = lint(text)
    assert "PATTERN_B" in hits, f"Expected PATTERN_B to fire on: {text!r}"


# ---- PATTERN C — meta-narration ----------------------------------------------

@pytest.mark.parametrize(
    "text",
    [
        "Let's find you some solid options in AI.",
        "Let's see what fits your schedule.",
        "Let me ask you about your budget.",
        "I'd like to understand your goals better.",
        "Time to think about what format works.",
        "Let's find you some options.",
        "I can find you some options right now.",
    ],
)
def test_pattern_c_fires(text: str) -> None:
    hits = lint(text)
    assert "PATTERN_C" in hits, f"Expected PATTERN_C to fire on: {text!r}"


# ---- PATTERN D — adjective stacking ------------------------------------------

@pytest.mark.parametrize(
    "text",
    [
        "Data science is an exciting space right now.",
        "That's an amazing field to be entering.",
        "This is an incredible opportunity for your career.",
        "Machine learning is a fascinating area.",
        "It can really make a difference.",
    ],
)
def test_pattern_d_fires(text: str) -> None:
    hits = lint(text)
    assert "PATTERN_D" in hits, f"Expected PATTERN_D to fire on: {text!r}"


# ---- Clean phrases — should NOT fire -----------------------------------------

@pytest.mark.parametrize(
    "text",
    [
        "Year or two in PM — what's pulling you toward AI specifically?",
        "Five years in product, that trajectory makes sense. What domain are you drawn to?",
        "With 8 hours a week you have real options. Do you prefer weekends or weekdays?",
        "A bachelor's in CS is fine for most of these. Budget range?",
        "Online-only narrows the field a bit, which is actually helpful. Any IIM preference?",
        "Switching into data is doable from your background. How much can you commit weekly?",
        "Three years in ops gives you a solid read on process. What's the goal — ML roles or analytics?",
    ],
)
def test_clean_phrase_does_not_fire(text: str) -> None:
    hits = lint(text)
    assert hits == [], f"Expected no lint hits, got {hits} on: {text!r}"
