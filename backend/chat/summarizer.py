"""History summarization + token budgeting for long conversations (Phase 8.3).

We keep the last `VERBATIM_WINDOW` turns intact and compress everything older into a
short running summary stored on the session. The planner reads slot state as ground
truth, so the summary only needs to preserve soft context (preferences, things the
user liked/disliked, explicit asks) that doesn't live in slots.
"""

from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

VERBATIM_WINDOW = 8          # turns kept verbatim in the LLM context
TOKEN_BUDGET = 4000          # force a summarization pass above this estimate
_CHARS_PER_TOKEN = 4         # rough heuristic (avoids a tiktoken dependency)


SUMMARY_PROMPT = """\
You compress the older part of a chat between a career coach and a user into a compact memory.
Output STRICT JSON only: {"summary": "<= 200 words"}.

Keep: key facts about the user, what they liked or disliked, anything they explicitly asked for,
and any preference not already obvious from a single slot value. Drop pleasantries and filler.
If a prior summary is given, merge it with the new turns into one updated summary.
"""


def estimate_tokens(messages: list[dict[str, str]], extra: str = "") -> int:
    """Cheap char-based token estimate so we don't pull in tiktoken."""
    chars = sum(len(m.get("content") or "") for m in messages) + len(extra)
    return chars // _CHARS_PER_TOKEN


def split_history(messages: list[dict[str, str]], window: int = VERBATIM_WINDOW):
    """Return (older_messages, recent_window)."""
    if len(messages) <= window:
        return [], messages
    return messages[:-window], messages[-window:]


def summarize_history(
    older_messages: list[dict[str, str]],
    prior_summary: str | None = None,
    client: OpenAI | None = None,
) -> str:
    """Compress older turns (and any prior summary) into <=200 words. Returns prior on failure."""
    if not older_messages:
        return prior_summary or ""
    client = client or OpenAI()
    model = os.getenv("OPENAI_MODEL_EXTRACT", "gpt-4o-mini")

    transcript_lines = []
    for m in older_messages:
        role = (m.get("role") or "user").upper()
        content = (m.get("content") or "").strip()
        if content:
            transcript_lines.append(f"{role}: {content}")
    transcript = "\n".join(transcript_lines)

    user_block = transcript
    if prior_summary:
        user_block = f"Prior summary:\n{prior_summary}\n\nNewer turns to fold in:\n{transcript}"

    try:
        import json

        resp = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": SUMMARY_PROMPT},
                {"role": "user", "content": user_block},
            ],
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        summary = (data.get("summary") or "").strip()
        return summary or (prior_summary or "")
    except Exception:
        return prior_summary or ""


def maybe_summarize(
    messages: list[dict[str, str]],
    prior_summary: str | None,
    client: OpenAI | None = None,
    force: bool = False,
) -> tuple[str | None, list[dict[str, str]]]:
    """Decide whether to summarize. Returns (summary, recent_window_to_send).

    Summarizes when history exceeds the verbatim window, or when `force` is set
    (token-budget guard). The recent window is always the last VERBATIM_WINDOW turns.
    """
    older, recent = split_history(messages)
    over_budget = estimate_tokens(messages) > TOKEN_BUDGET
    if older and (force or over_budget or prior_summary is None):
        summary = summarize_history(older, prior_summary, client=client)
        return summary, recent
    if not older:
        return prior_summary, messages
    return prior_summary, recent
