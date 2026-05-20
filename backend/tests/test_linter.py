"""Tests for the voice linter (backend/chat/linter.py).

Asserts:
  - Every canonical example from PATTERN A-D fires lint().
  - Clean phrases return an empty list.
"""

from __future__ import annotations

import pytest
from backend.chat.linter import lint

from backend.chat.linter import lint, strip_banned_patterns

@pytest.mark.parametrize(
    "phrase",
    [
        "That's an amazing field to move into.",
        "This goes a long way in your career.",
        "It opens doors in the industry.",
        "This can really open up opportunities for you.",
        "This sets you up well for the transition.",
        "That's an exciting space to explore.",
        "That is an incredible opportunity.",
        "Switching into AI sounds like a smart move.",
    ],
)
def test_pattern_a_fires(phrase: str) -> None:
    hits = lint(phrase)
    assert "PATTERN_A" in hits


@pytest.mark.parametrize(
    "phrase",
    [
        "Noted, you've got a year or two under your belt.",
        "Got it, you're in product management.",
        "Cool, you have five years of experience.",
        "Right, you're focused on data engineering.",
        "Awesome, you've been in fintech.",
        "Alright, you're looking to switch careers.",
        "Nice, you have a bachelor's degree.",
        "Noted, you've got some time under your belt since January 2026.",
    ],
)
def test_pattern_b_fires(phrase: str) -> None:
    hits = lint(phrase)
    assert "PATTERN_B" in hits


@pytest.mark.parametrize(
    "phrase",
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
def test_pattern_c_fires(phrase: str) -> None:
    hits = lint(phrase)
    assert "PATTERN_C" in hits


@pytest.mark.parametrize(
    "phrase",
    [
        "Data science is an exciting space right now.",
        "That's an amazing field to be entering.",
        "This is an incredible opportunity for your career.",
        "Machine learning is a fascinating area.",
        "It can really make a difference.",
    ],
)
def test_pattern_d_fires(phrase: str) -> None:
    hits = lint(phrase)
    assert "PATTERN_D" in hits


def test_multiple_patterns_fire() -> None:
    hits = lint("Noted, you've got some time under your belt since January 2026.")
    assert "PATTERN_B" in hits
    assert "PATTERN_A" in hits

    hits = lint("Right, a little coding experience can be a helpful foundation in AI.")
    assert "PATTERN_B" in hits
    assert "PATTERN_A" in hits

def test_apology_with_answer_fires() -> None:
    hits = lint("I don't have that on the course page, but it has 5 modules.")
    assert "APOLOGY_WITH_ANSWER" in hits


def test_pattern_q_internal_leak_fires() -> None:
    assert "PATTERN_Q" in lint("The faculty is not specified in the scraped data.")
    assert "PATTERN_Q" in lint("That detail isn't specified in the course information.")


def test_pattern_r_bare_redirect_fires() -> None:
    assert "PATTERN_R" in lint("The upGrad page covers placement guarantees in detail.")
    assert "PATTERN_R" in lint("The upGrad page has the alumni community details.")


def test_polite_redirect_does_not_fire() -> None:
    # Two-sentence, value-first answers must NOT trip Q or R.
    good = (
        "upGrad usually offers placement support like resume reviews and hiring-partner "
        "introductions rather than a blanket guarantee. The official upGrad page spells out "
        "what this course includes."
    )
    hits = lint(good)
    assert "PATTERN_Q" not in hits and "PATTERN_R" not in hits


def test_data_science_mention_does_not_fire() -> None:
    assert lint("This is great if you're interested in the data science field.") == []

def test_em_dash_fires() -> None:
    hits = lint("This is a great — wait, no.")
    assert "EM_DASH" in hits

def test_strip_banned_patterns_b():
    draft = "Noted, you've got a great background. Let's see what fits."
    stripped = strip_banned_patterns(draft, ["PATTERN_B"])
    assert stripped == "You've got a great background. Let's see what fits."
    
def test_strip_banned_patterns_em_dash():
    draft = "No em dashes — they are bad."
    stripped = strip_banned_patterns(draft, ["EM_DASH"])
    assert stripped == "No em dashes, they are bad."

@pytest.mark.parametrize(
    "phrase",
    [
        "Year or two in PM, what's pulling you toward AI specifically?",
        "Five years in product, that trajectory makes sense. What domain are you drawn to?",
        "With 8 hours a week you have real options. Do you prefer weekends or weekdays?",
        "A bachelor's in CS is fine for most of these. Budget range?",
        "Online-only narrows the field a bit, which is actually helpful. Any IIM preference?",
        "Switching into data is doable from your background. How much can you commit weekly?",
        "PM, got it. How long have you been at it?",
    ],
)
def test_clean_phrase_does_not_fire(phrase: str) -> None:
    hits = lint(phrase)
    assert not hits
