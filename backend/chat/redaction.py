"""Single source of truth for what the LLM is allowed to see (Phase 13.4).

Anything that ever held PII must pass through `scrub_history_for_llm` before
being placed in a prompt. Lead contact details flow only through /api/leads and
are never appended to chat history, so this is the belt-and-suspenders layer:
even a stray email/phone in free text gets masked.
"""

from __future__ import annotations

import re

EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PHONE_RE = re.compile(r"(?<!\d)(\+?\d{1,3}[- ]?)?\d{10}(?!\d)")

REDACTION_TOKEN = "[contact_shared]"


def scrub_text(text: str) -> str:
    """Mask any email/phone patterns in free text."""
    if not text:
        return text
    text = EMAIL_RE.sub("[email]", text)
    text = PHONE_RE.sub("[phone]", text)
    return text


def scrub_history_for_llm(history: list[dict]) -> list[dict]:
    """Drop redacted messages to the marker; mask stray PII in all other text."""
    cleaned: list[dict] = []
    for msg in history:
        if msg.get("redacted"):
            cleaned.append({"role": "user", "content": REDACTION_TOKEN})
            continue
        cleaned.append({
            "role": msg.get("role", "user"),
            "content": scrub_text(msg.get("content") or ""),
        })
    return cleaned
