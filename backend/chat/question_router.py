"""Question-to-field router (Phase 11.5).

Maps a user's course question to the exact fields that answer it, so the
course-QA prompt can surface the most relevant data at the top of the context
block. `<heuristic:*>` tokens are resolved later by course_qa using
heuristics.heuristic_for when the real field is null.
"""

from __future__ import annotations

import re

# Note: patterns use a leading \b only (no trailing \b) so stems and plurals match
# ("eligib" -> "eligibility", "fee" -> "fees", "requirement" -> "requirements").
QUESTION_FIELD_MAP: list[tuple[str, list[str]]] = [
    (r"\b(degree|eligib|qualif|prereq|who can (?:join|apply)|requirement)",
     ["eligibility_raw", "min_degree", "min_marks_pct", "programme_type_key", "<heuristic:eligibility>"]),

    (r"\b(hours?|weekly|how (?:long|much time)|how many sessions?|workload|duration)",
     ["weekly_hours", "duration_weeks", "duration_label", "schedule", "<heuristic:duration>"]),

    (r"\b(fee|cost|price|emi|payment|installment|instalment|tuition)",
     ["emi_starts_from_inr", "fee_inr_total", "fee_bucket", "programme_type_key", "<heuristic:fees>"]),

    (r"\b(faculty|teacher|prof\.?|instructor|who teaches?|mentor)",
     ["faculty", "co_brand", "provider"]),

    (r"\b(curriculum|module|topic|syllabus|what (?:do|will) (?:i|we) learn|content|cover)",
     ["modules", "tools", "key_highlights"]),

    (r"\b(format|online|offline|hybrid|in[- ]?person|classroom|self[- ]?paced|cohort|weekend|weekday)",
     ["format", "schedule", "<heuristic:format>"]),

    (r"\b(certificate|certification|credential|degree (?:on offer|awarded))",
     ["certificates", "co_brand", "provider", "programme_type"]),

    (r"\b(job|placement|career|salary|hiring|company|companies)",
     ["hiring_companies", "target_roles", "industries"]),
]

DEFAULT_FIELDS = ["title", "programme_type", "duration_label", "tools", "target_roles"]

_COMPILED = [(re.compile(pat, re.IGNORECASE), fields) for pat, fields in QUESTION_FIELD_MAP]


def route(user_msg: str) -> list[str]:
    """Return the deduped, ordered list of fields most relevant to the question.

    Multiple patterns can match ("duration and fees?"); their fields are merged.
    No match returns DEFAULT_FIELDS.
    """
    msg = user_msg or ""
    matched: list[str] = []
    for pat, fields in _COMPILED:
        if pat.search(msg):
            matched.extend(fields)
    if not matched:
        return list(DEFAULT_FIELDS)
    # dedupe preserving order
    seen, out = set(), []
    for f in matched:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out
