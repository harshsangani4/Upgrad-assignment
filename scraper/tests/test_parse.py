import warnings
from pathlib import Path

import pytest

from scraper.parse import parse

FIXTURE = Path(__file__).parent / "fixtures" / "iiitb_applied_ai.html"
SLUG = "applied-ai-and-agentic-ai-executive-pgp-certification-iiitb"


def _load_fixture() -> str:
    if not FIXTURE.exists() or FIXTURE.stat().st_size < 1000:
        pytest.skip(f"fixture {FIXTURE.name} is empty or missing — capture via scraper.detail first")
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def parsed() -> dict:
    return parse(_load_fixture(), slug=SLUG, url=f"https://www.upgrad.com/{SLUG}/")


def test_title(parsed):
    assert parsed["title"] == "Executive Post Graduate Programme in Applied AI and Agentic AI"


def test_provider(parsed):
    assert parsed["provider"] == "IIIT Bangalore"


def test_duration_weeks(parsed):
    assert parsed["duration_weeks"] == 30


def test_emi_present_or_warn(parsed):
    emi = parsed["emi_starts_from_inr"]
    assert emi is None or isinstance(emi, int)
    if emi is None:
        warnings.warn(
            "emi_starts_from_inr is None — fixture likely captured from /us/ variant. "
            "Re-capture with India-exit IP to verify the EMI selector."
        )


def test_modules(parsed):
    assert len(parsed["modules"]) >= 6


def test_faqs(parsed):
    assert len(parsed["faqs"]) >= 10


def test_breadcrumb_category(parsed):
    cat = parsed["breadcrumb_category"]
    assert cat and isinstance(cat, str) and len(cat) > 0
