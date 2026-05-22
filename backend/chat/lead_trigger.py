"""Decides whether to surface the in-chat lead-capture form this turn (Phase 13.1).

Server-side and deterministic on purpose: we never let the LLM decide when to ask
for contact details. Inputs come from SessionState; output is a boolean plus the
inferred course-of-interest slug.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

HIGH_INTENT_REGEXES = [
    r"\b(how (do|can) i (apply|enrol|enroll|join))\b",
    r"\b(application (process|deadline|steps?))\b",
    r"\b(admission|admissions)\b",
    r"\b(next steps?|what'?s next)\b",
    r"\b(deadline|last date|cut[- ]?off|when does it close)\b",
    r"\b(am i eligible|do i qualify|will i get in)\b",
    r"\b(emi (options?|details?|breakdown))\b",
    r"\b(scholarship|discount|loan)\b",
    r"\b(talk (to|with) (a |someone|counsellor|advisor))\b",
    r"\b(call me|connect me|reach out)\b",
    r"\b(i('?| a)m (interested|in)|i want to (join|enrol|enroll))\b",
    r"\b(sign me up|let'?s do it|i'?ll take it)\b",
    # decision affirmations (only reachable post-recommendation, so safe)
    r"\b(works for me|that works|that'?ll work)\b",
    r"\b(i'?m sold|count me in|i'?m convinced)\b",
    r"\b(this is the one|that'?s the one|i'?ll go with|go(ing)? with (this|that|it))\b",
    r"\b((sounds?|looks?) perfect|perfect for me)\b",
    r"\b(ready to (apply|enrol|enroll|join|start)|let'?s (go|move|proceed))\b",
    r"\b(i'?ll (do|take|pick|choose) (this|that|it))\b",
]
HIGH_INTENT_PATTERN = re.compile("|".join(HIGH_INTENT_REGEXES), re.IGNORECASE)

DECLINE_REGEXES = [
    r"\b(not now|later|maybe later|skip|no thanks|not yet)\b",
    r"\b(don'?t (share|give|send)|won'?t share)\b",
    r"\b(just looking|just browsing|exploring)\b",
]
DECLINE_PATTERN = re.compile("|".join(DECLINE_REGEXES), re.IGNORECASE)


@dataclass
class LeadTriggerDecision:
    should_surface: bool
    reason: str            # for logs only, never shown to the user
    course_slug: str | None


def decide(session, last_user_message: str) -> LeadTriggerDecision:
    """Return whether to surface the lead form, why, and which course to pre-fill."""
    if session.lead_captured:
        return LeadTriggerDecision(False, "already_captured", None)

    if session.turns_since_first_recommendation < 1:
        return LeadTriggerDecision(False, "pre_recommendation", None)

    # Recently offered and declined — back off for a few turns.
    if session.user_declined_lead and session.turns_since_last_lead_offer < 4:
        return LeadTriggerDecision(False, "cool_off", None)

    msg = last_user_message or ""

    # Explicit decline this turn → don't surface (mark declined).
    if DECLINE_PATTERN.search(msg):
        session.user_declined_lead = True
        session.turns_since_last_lead_offer = 0
        return LeadTriggerDecision(False, "declined_now", None)

    # Strong signal: an explicit high-intent / decision phrase. Surface promptly
    # (just avoid firing twice in immediate succession).
    if HIGH_INTENT_PATTERN.search(msg) and session.turns_since_last_lead_offer >= 2:
        return LeadTriggerDecision(True, "high_intent_phrase", session.focused_course_slug)

    # Deep focus on one course is a strong intent signal on its own.
    if session.focused_course_slug:
        depth = session.course_qa_depth.get(session.focused_course_slug, 0)
        if depth >= 3 and session.turns_since_last_lead_offer >= 3:
            return LeadTriggerDecision(True, "deep_focus", session.focused_course_slug)

    # Behavioral (phrase-independent): the user keeps engaging after recommendations.
    # This is the main conversion path; users rarely say a magic phrase. We offer
    # after a few substantive turns, then back off (re-offer gap widens) so we never nag.
    if session.engagement_score >= 3 and session.turns_since_last_lead_offer >= 5:
        return LeadTriggerDecision(True, "sustained_engagement", session.focused_course_slug)

    return LeadTriggerDecision(False, "no_signal", None)
