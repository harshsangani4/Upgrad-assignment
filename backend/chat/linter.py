"""Pre-send voice linter for the upGrad concierge.

Four banned patterns (A-D) replace the old phrase-based blocklist.
Pattern-based blocking is harder for the LLM to paraphrase around.
"""

from __future__ import annotations

import re

# ---- Banned patterns ---------------------------------------------------------
# Each entry is (pattern_id, compiled_regex).
# lint() returns the IDs of every pattern that fires in a given draft.

BANNED_REGEXES = [
    # PATTERN A — empty acknowledgement praise
    (r"\b(it can really|that(?:'?s| is) (?:a |an )?(?:solid|great|amazing|exciting|incredible|fantastic|wonderful|smart move))", "PATTERN_A"),
    (r"\b(opens? doors?|goes? a long way|under your belt|solid start|good foundation|helpful foundation|great start|sets? you up|open up (?:fresh )?opportunities|sounds like a smart move)", "PATTERN_A"),
    (r"\b(big leap|solid foundation|foundation for your|(?:quite |very |really )?rewarding|great choice|good move|exciting journey)\b", "PATTERN_A"),

    # PATTERN B — brochure-acknowledgement openers
    (r"^(noted|got it|cool|right|okay|alright|nice|awesome|great)[,!]?\s+(you'?re|you'?ve|you have|a little|some)", "PATTERN_B"),

    # PATTERN C — meta-narration
    (r"\b(let'?s find|find you some|let'?s see what|let me ask|i'?d like to understand|time to think about|that'?ll help (?:us|me) figure)", "PATTERN_C"),

    # PATTERN D — adjective stacking
    (r"\b(exciting space|amazing field|incredible opportunity|fascinating area|so much potential|potential for growth|can really)", "PATTERN_D"),

    # NEW — em-dash ban from updated persona
    (r"—", "EM_DASH"),

    # NEW — self-contradicting apology (10.3.2)
    (r"(That'?s? not something I have data on|I don'?t have that on the course page).+(week|hour|session|fee|EMI|certificate|module|faculty|teacher|prof\.)", "APOLOGY_WITH_ANSWER"),

    # PATTERN P (11.4.2) — apology is the ENTIRE response (whole-string match)
    (r"^[\s]*(I don'?t have that|That'?s? not something I have|The upGrad page (?:would |should )?have).{0,100}\.?\s*$", "PATTERN_P"),

    # PATTERN Q (12.x) — internal-mechanics leak: the user must never see these.
    (r"(scraped data|the dataset\b|not specified in (?:the|our|my)|isn'?t specified in|no data (?:on|about)|from (?:the|our) data\b)", "PATTERN_Q"),

    # PATTERN R (12.x) — bare redirect as the ENTIRE response (rude one-liner).
    (r"^[\s]*the upGrad page (?:covers|has|details|will have|would have|should have|includes|provides)\b.{0,90}\.?\s*$", "PATTERN_R"),

    # PATTERN S (12.x) — third-party framing of upGrad (this bot IS upGrad).
    (r"(official upGrad page|upGrad'?s (?:official )?(?:page|website|site)|check (?:out )?upGrad|on upGrad'?s (?:page|website|site))", "PATTERN_S"),

    # PATTERN T (13.2) — blunt / robotic lead-capture asks (the form does this, not prose).
    (r"\bwhich (course|one|program(?:me)?) (?:are you|interests you)\b", "PATTERN_T"),
    (r"\bcan i (?:get|have) your (?:contact|email|phone|number|details)\b", "PATTERN_T"),
    (r"\bfill out (?:this|the) form\b", "PATTERN_T"),
    (r"\bplease (?:provide|enter|share) your\b", "PATTERN_T"),
]

_DOTALL_IDS = {"APOLOGY_WITH_ANSWER", "PATTERN_P", "PATTERN_R"}

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (pid, re.compile(pat, re.IGNORECASE | (re.MULTILINE if "PATTERN_B" in pid else 0) | (re.DOTALL if pid in _DOTALL_IDS else 0)))
    for pat, pid in BANNED_REGEXES
]


def lint(draft: str) -> list[str]:
    """Return list of pattern IDs that fired. Empty list means the draft is clean."""
    # Collect unique hits
    hits = []
    for pid, pat in _PATTERNS:
        if pat.search(draft) and pid not in hits:
            hits.append(pid)
    return hits

def strip_banned_patterns(draft: str, hits: list[str]) -> str:
    """Sentence-level recovery for when retries fail.
    Strips Pattern B openers cleanly.
    """
    if "PATTERN_B" in hits:
        # Split on sentence boundaries loosely
        parts = re.split(r'(?<=[.!?])\s+', draft)
        if parts:
            first_sentence = parts[0]
            # If the first sentence matches Pattern B, try to strip just the opener phrase
            match = None
            for pat_str, pid in BANNED_REGEXES:
                if pid == "PATTERN_B":
                    # find the match
                    comp = re.compile(pat_str, re.IGNORECASE | re.MULTILINE)
                    match = comp.search(first_sentence)
                    if match:
                        break
            if match:
                # We could drop the whole first sentence, but the spec says:
                # "split on `. ` or `, `, drop the first segment if it matches the pattern, and capitalize the next segment's first letter."
                sub_parts = re.split(r'[,.!?]\s+', first_sentence, maxsplit=1)
                if len(sub_parts) > 1:
                    new_start = sub_parts[1]
                    new_start = new_start[0].upper() + new_start[1:] if new_start else ""
                    parts[0] = new_start
                else:
                    parts.pop(0)
            
        draft = " ".join(parts).strip()
    
    # Strip EM_DASH
    if "EM_DASH" in hits:
        draft = draft.replace(" — ", ", ").replace("—", ", ")
        
    return draft
