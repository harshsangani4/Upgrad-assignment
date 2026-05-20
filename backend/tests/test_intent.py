import json
from types import SimpleNamespace

from backend.chat.extractor import classify_intent


class FakeOpenAI:
    """Returns a fixed JSON payload (or raw string) for the intent classifier."""

    def __init__(self, payload):
        self._payload = payload
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        content = self._payload if isinstance(self._payload, str) else json.dumps(self._payload)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def test_more_cards_intent():
    fake = FakeOpenAI({"intent": "more_cards", "filter_override": None})
    out = classify_intent("show me more", [], client=fake)
    assert out["intent"] == "more_cards"
    assert out["filter_override"] is None


def test_filter_change_with_override():
    fake = FakeOpenAI({"intent": "filter_change", "filter_override": {"fee_bucket_max": "1-3L"}})
    out = classify_intent("any cheaper options?", [], client=fake)
    assert out["intent"] == "filter_change"
    assert out["filter_override"] == {"fee_bucket_max": "1-3L"}


def test_filter_change_prestige():
    fake = FakeOpenAI({"intent": "filter_change", "filter_override": {"prestige_signal": ["iim"]}})
    out = classify_intent("I prefer IIM", [], client=fake)
    assert out["intent"] == "filter_change"
    assert out["filter_override"]["prestige_signal"] == ["iim"]


def test_compare_intent():
    fake = FakeOpenAI({"intent": "compare", "filter_override": None})
    out = classify_intent("compare the first two", [], client=fake)
    assert out["intent"] == "compare"


def test_answering_intent():
    fake = FakeOpenAI({"intent": "answering", "filter_override": None})
    out = classify_intent("I'm a dev", [], client=fake)
    assert out["intent"] == "answering"


def test_invalid_intent_normalized():
    fake = FakeOpenAI({"intent": "banana", "filter_override": None})
    out = classify_intent("???", [], client=fake)
    assert out["intent"] == "answering"


def test_bad_json_falls_back():
    fake = FakeOpenAI("not json at all")
    out = classify_intent("hello", [], client=fake)
    assert out["intent"] == "answering"
    assert out["filter_override"] is None


def test_non_dict_override_coerced_to_none():
    fake = FakeOpenAI({"intent": "filter_change", "filter_override": "oops"})
    out = classify_intent("cheaper", [], client=fake)
    assert out["filter_override"] is None
