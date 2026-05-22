"""PII firewall (Phase 13.4): captured contact details must never reach the LLM prompt."""

import re

from backend.chat.planner import SessionState
from backend.chat.redaction import REDACTION_TOKEN, scrub_history_for_llm


def test_scrub_drops_redacted_and_masks_pii():
    history = [
        {"role": "user", "content": "[contact_shared]", "redacted": True},
        {"role": "user", "content": "my email is astha@theproductfolks.com, phone 9876543210"},
        {"role": "assistant", "content": "sure thing"},
    ]
    cleaned = scrub_history_for_llm(history)
    blob = str(cleaned).lower()
    assert "astha@" not in blob
    assert "9876543210" not in blob
    assert REDACTION_TOKEN in str(cleaned)


def test_build_chat_messages_scrubs_pii():
    # The actual prompt builder must not leak PII left in history.
    from backend.main import _build_chat_messages

    s = SessionState(session_id="t")
    s.messages = [
        {"role": "user", "content": "call me at 9876543210 or email astha@x.com"},
        {"role": "assistant", "content": "ok"},
    ]
    msgs = _build_chat_messages(s, "directive", s.messages, is_first_turn=True)
    blob = str(msgs).lower()
    assert "astha@x.com" not in blob
    assert not re.search(r"\b9876543210\b", blob)


def test_lead_captured_flag_only_no_pii_note():
    from backend.main import _build_chat_messages

    s = SessionState(session_id="t")
    s.lead_captured = True
    s.lead_first_name = "Astha"
    s.lead_id = "abc-123"
    s.messages = [{"role": "user", "content": "[contact_shared]", "redacted": True}]
    msgs = _build_chat_messages(s, "", s.messages, is_first_turn=False)
    blob = str(msgs)
    # The bot is told contact was shared, but never the name/id.
    assert "Astha" not in blob
    assert "abc-123" not in blob
    assert "already shared their contact" in blob
