import json
from types import SimpleNamespace

from backend.chat.summarizer import (
    VERBATIM_WINDOW,
    estimate_tokens,
    maybe_summarize,
    split_history,
)


class FakeOpenAI:
    def __init__(self, summary: str = "User is a 5-yr PM moving into AI, wants weekend cohort."):
        self.summary = summary
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        body = json.dumps({"summary": self.summary})
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=body))])


def _turns(n: int) -> list[dict]:
    out = []
    for i in range(n):
        out.append({"role": "user", "content": f"user message number {i}"})
        out.append({"role": "assistant", "content": f"assistant reply number {i}"})
    return out


def test_estimate_tokens_rough():
    msgs = [{"role": "user", "content": "a" * 400}]
    assert estimate_tokens(msgs) == 100  # 400 chars / 4


def test_split_history_under_window_keeps_all():
    msgs = _turns(2)  # 4 messages, under window
    older, recent = split_history(msgs)
    assert older == []
    assert recent == msgs


def test_split_history_over_window():
    msgs = _turns(10)  # 20 messages
    older, recent = split_history(msgs, window=VERBATIM_WINDOW)
    assert len(recent) == VERBATIM_WINDOW
    assert len(older) == 20 - VERBATIM_WINDOW
    assert recent == msgs[-VERBATIM_WINDOW:]


def test_maybe_summarize_short_history_no_summary():
    msgs = _turns(2)
    summary, window = maybe_summarize(msgs, prior_summary=None, client=FakeOpenAI())
    assert summary is None
    assert window == msgs


def test_maybe_summarize_long_history_produces_summary():
    msgs = _turns(10)  # 20 messages > window
    summary, window = maybe_summarize(msgs, prior_summary=None, client=FakeOpenAI())
    assert summary  # non-empty
    assert "PM" in summary
    assert len(window) == VERBATIM_WINDOW


def test_maybe_summarize_force_flag():
    msgs = _turns(6)  # 12 messages > window of 8
    summary, window = maybe_summarize(msgs, prior_summary=None, client=FakeOpenAI(), force=True)
    assert summary
    assert len(window) == VERBATIM_WINDOW
