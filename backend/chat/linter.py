"""Pre-send voice linter for the upGrad concierge.

Four banned patterns (A-D) replace the old phrase-based blocklist.
Pattern-based blocking is harder for the LLM to paraphrase around.
"""

from __future__ import annotations

import re

# ---- Banned patterns ---------------------------------------------------------
# Each entry is (pattern_id, compiled_regex).
# lint() returns the IDs of every pattern that fires in a given draft.

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "PATTERN_A",  # empty acknowledgement praise
        re.compile(
            r"\b("
            r"that(?:'?s| is) (?:a |an )?(?:solid|great|amazing|exciting|incredible|fantastic|wonderful)"
            r"|great foundation"
            r"|strong base"
            r"|that(?:'?ll| will) really help"
            r"|goes? a long way"
            r"|opens? (?:up )?(?:doors?|opportunities)"
            r"|sets? you up (?:well|nicely|for)"
            r"|can really open"
            r")",
            re.IGNORECASE,
        ),
    ),
    (
        "PATTERN_B",  # brochure-acknowledgement openers
        re.compile(
            r"^(?:right|cool|got it|noted|alright|awesome|nice),?\s+you(?:'re|'ve| are| have)\b",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    (
        "PATTERN_C",  # meta-narration
        re.compile(
            r"\b("
            r"let'?s find(?: you)?(?: some| a few)?(?: solid)? options?"
            r"|let'?s see what (?:fits?|works?|matches?)"
            r"|let me ask you about"
            r"|i'?d like to understand"
            r"|time to think about"
            r"|find you some"
            r")",
            re.IGNORECASE,
        ),
    ),
    (
        "PATTERN_D",  # adjective stacking on neutral facts
        re.compile(
            r"\b("
            r"exciting space"
            r"|amazing field"
            r"|incredible opportunity"
            r"|fascinating (?:area|field|space|topic)"
            r"|it can really"
            r")",
            re.IGNORECASE,
        ),
    ),
]


def lint(draft: str) -> list[str]:
    """Return list of pattern IDs that fired. Empty list means the draft is clean."""
    return [pid for pid, pat in _PATTERNS if pat.search(draft)]
