import json
from types import SimpleNamespace

from backend.chat.extractor import extract_slots, _format_history


class FakeChat:
    def __init__(self, payload: dict):
        self._payload = payload
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        msg = SimpleNamespace(content=json.dumps(self._payload))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_extract_filters_null_fields():
    fake = FakeChat({
        "current_role": "backend dev",
        "years_experience": 5,
        "can_code": True,
        "education_level": None,
        "vibe_preference": None,
    })
    out = extract_slots(history=[], latest_user_msg="I'm a backend dev with 5 yrs", client=fake)
    assert out == {"current_role": "backend dev", "years_experience": 5, "can_code": True}


def test_extract_returns_empty_on_exception():
    class BoomClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._boom))

        def _boom(self, **kwargs):
            raise RuntimeError("network down")

    out = extract_slots(history=[], latest_user_msg="hey", client=BoomClient())
    assert out == {}


def test_format_history_keeps_only_last_window():
    history = [
        {"role": "user", "content": "one"},
        {"role": "assistant", "content": "two"},
        {"role": "user", "content": "three"},
        {"role": "assistant", "content": "four"},
        {"role": "user", "content": "five"},
    ]
    out = _format_history(history, window=2)
    assert "one" not in out
    assert "four" in out and "five" in out
