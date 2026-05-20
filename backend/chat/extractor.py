"""Slot extractor: reads chat history + latest user message, returns a partial slot dict."""

from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

EXTRACTOR_PROMPT = """\
You extract structured user info from a chat transcript. Output STRICT JSON only — no prose.

Schema:
{
  "current_role": string | null,
  "years_experience": int | null,
  "education_level": "12th"|"diploma"|"bachelors"|"masters"|"phd"|null,
  "min_marks_pct_est": int | null,
  "can_code": bool | null,
  "career_goal": "switch"|"promotion"|"skill_up"|"founders"|"academic"|null,
  "domain_interest": [string] | null,
  "weekly_hours": int | null,
  "format_preference": "online"|"offline"|"hybrid"|null,
  "schedule_preference": "self_paced"|"weekend_cohort"|"weekday_cohort"|null,
  "budget_bucket": "<1L"|"1-3L"|"3-5L"|"5-10L"|"10L+"|null,
  "prestige_preference": "iit_iim"|"global_uni"|"industry_only"|"any"|null,
  "vibe_preference": [string] | null
}

Rules:
- Only return fields the user clearly stated. Use null for everything else.
- Don't infer beyond direct statements ("I'm a senior dev" ≠ years_experience).
- If a user gave a range, use the midpoint as an int.
- Output ONLY the JSON. No explanation, no markdown fence.
"""


def _format_history(history: list[dict[str, str]], window: int = 8) -> str:
    """Render the last N turns as plain text for the extractor."""
    tail = history[-window:] if window else history
    lines = []
    for msg in tail:
        role = msg.get("role", "user").upper()
        content = (msg.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def extract_slots(history: list[dict[str, str]], latest_user_msg: str, client: OpenAI | None = None) -> dict[str, Any]:
    """Call the extractor model; return a dict of slot updates (only non-null fields)."""
    client = client or OpenAI()
    model = os.getenv("OPENAI_MODEL_EXTRACT", "gpt-4o-mini")

    transcript = _format_history(history)
    user_block = f"Transcript so far:\n{transcript}\n\nLatest user turn: {latest_user_msg}"

    try:
        resp = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": EXTRACTOR_PROMPT},
                {"role": "user", "content": user_block},
            ],
        )
        raw = json.loads(resp.choices[0].message.content or "{}")
    except Exception:
        return {}

    return {k: v for k, v in raw.items() if v is not None}


INTENT_PROMPT = """\
You classify the user's latest message in a course-recommendation chat where courses have already been shown.

Output STRICT JSON only:
{
  "intent": "answering" | "more_cards" | "all_cards" | "filter_change" | "off_topic" | "compare" | "done",
  "filter_override": null | {
    "fee_bucket_max": "<1L"|"1-3L"|"3-5L"|"5-10L"|"10L+"|null,
    "prestige_signal": ["iit"|"iim"|"iiit"|"global_uni"|"industry_only"]|null,
    "format": ["online"|"offline"|"hybrid"]|null
  },
  "requested_count": null | int
}

Intents:
- more_cards: wants more or different picks ("show me more", "other options", "anything else", "next 3").
  Set requested_count if they specify a number ("show me 10 more" → requested_count=10).
- all_cards: wants EVERYTHING that matches ("show me all", "give me all courses", "everything that fits",
  "can you provide me all courses", "list all options"). requested_count is null.
- filter_change: wants to narrow or change criteria ("any cheaper?", "IIM options?", "only online",
  "something shorter"). Set filter_override.
- compare: wants the shown courses compared ("compare the first two", "which is better").
- done: satisfied or wrapping up ("thanks", "that's all", "perfect").
- answering: giving profile info or answering a question.
- off_topic: unrelated to courses or career.

Key distinction: "more" = next page (more_cards). "all" or "everything" = all_cards.
filter_override is null unless intent is filter_change. "cheaper" sets fee_bucket_max one bucket below the
user's current budget when known. Brand names map to prestige_signal. Output ONLY the JSON.
"""

_VALID_INTENTS = {"answering", "more_cards", "all_cards", "filter_change", "off_topic", "compare", "done"}


def classify_intent(
    latest_user_msg: str,
    recent_messages: list[dict[str, str]] | None = None,
    client: OpenAI | None = None,
) -> dict[str, Any]:
    """Classify a post-recommendation message.

    Returns {"intent": str, "filter_override": dict|None, "requested_count": int|None}.
    """
    client = client or OpenAI()
    model = os.getenv("OPENAI_MODEL_EXTRACT", "gpt-4o-mini")
    context = _format_history(recent_messages or [], window=6)
    user_block = f"Recent turns:\n{context}\n\nLatest user turn: {latest_user_msg}"

    try:
        resp = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": INTENT_PROMPT},
                {"role": "user", "content": user_block},
            ],
        )
        raw = json.loads(resp.choices[0].message.content or "{}")
    except Exception:
        return {"intent": "answering", "filter_override": None, "requested_count": None}

    intent = raw.get("intent")
    if intent not in _VALID_INTENTS:
        intent = "answering"
    override = raw.get("filter_override")
    if not isinstance(override, dict):
        override = None
    requested_count = raw.get("requested_count")
    if not isinstance(requested_count, int) or requested_count <= 0:
        requested_count = None
    return {"intent": intent, "filter_override": override, "requested_count": requested_count}
