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
