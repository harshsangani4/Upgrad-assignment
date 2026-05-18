from scraper.enrich import (
    _normalize_enrichment,
    compute_fee_bucket,
    embedding_input,
    infer_prestige_signal_from_slug,
)


# --- compute_fee_bucket --------------------------------------------------------

def test_bucket_uses_total_fee_when_present():
    assert compute_fee_bucket(140_000, 5631) == "1-3L"
    assert compute_fee_bucket(90_000, None) == "<1L"
    assert compute_fee_bucket(400_000, None) == "3-5L"
    assert compute_fee_bucket(750_000, None) == "5-10L"
    assert compute_fee_bucket(1_200_000, None) == "10L+"


def test_bucket_falls_back_to_emi_times_24():
    # 5631 * 24 = 135,144 → 1-3L
    assert compute_fee_bucket(None, 5631) == "1-3L"
    # ~4000 emi * 24 = 96,000 → <1L
    assert compute_fee_bucket(None, 4000) == "<1L"


def test_bucket_returns_none_when_no_signal():
    assert compute_fee_bucket(None, None) is None
    assert compute_fee_bucket(0, 0) is None


# --- prestige inference --------------------------------------------------------

def test_prestige_iiit_from_iiitb_slug():
    assert infer_prestige_signal_from_slug(
        "applied-ai-and-agentic-ai-executive-pgp-certification-iiitb", "IIIT Bangalore", None
    ) == "iiit"


def test_prestige_iim_from_iim_slug():
    assert infer_prestige_signal_from_slug(
        "hrm-analytics-pcp-iimk", "IIM Kozhikode", None
    ) == "iim"


def test_prestige_global_uni_from_ljmu():
    assert infer_prestige_signal_from_slug(
        "data-science-masters-degree-ljmu", "Liverpool John Moores University", None
    ) == "global_uni"


def test_prestige_industry_only_from_microsoft():
    assert infer_prestige_signal_from_slug(
        "the-u-and-ai-genai-certificate-program-from-microsoft", "Microsoft", None
    ) == "industry_only"


def test_prestige_none_when_unknown():
    assert infer_prestige_signal_from_slug("some-random-course", None, None) is None


# --- embedding_input -----------------------------------------------------------

def test_embedding_input_assembles_expected_fields():
    course = {
        "title": "Applied AI",
        "hero_tagline": "from foundations to production",
        "one_line_pitch": "deploy real AI agents",
        "modules": [{"name": "Foundations"}, {"name": "MLOps"}, {"name": ""}],
        "tools": ["Python", "LangChain"],
    }
    out = embedding_input(course)
    assert "Applied AI" in out
    assert "Foundations" in out and "MLOps" in out
    assert "Python" in out and "LangChain" in out


# --- _normalize_enrichment -----------------------------------------------------

def test_normalize_coerces_invalid_enums_to_defaults():
    course = {"slug": "x", "fee_inr_total": 200_000}
    out = _normalize_enrichment({
        "level": "expert",            # not in allowed -> "intermediate"
        "format": "remote",           # not in allowed -> "online"
        "schedule": "anytime",        # -> "weekend_cohort"
        "primary_outcome": "fun",     # -> "skill_up"
        "vibe": ["chill"],            # filtered out -> defaults to ["applied"]
        "min_years_experience": "not-a-number",
        "max_weekly_hours": "n/a",
    }, course)
    assert out["level"] == "intermediate"
    assert out["format"] == "online"
    assert out["schedule"] == "weekend_cohort"
    assert out["primary_outcome"] == "skill_up"
    assert out["vibe"] == ["applied"]
    assert out["min_years_experience"] == 0
    assert out["max_weekly_hours"] == 12


def test_normalize_overrides_bucket_when_fee_known():
    course = {"slug": "x", "fee_inr_total": 140_000}
    out = _normalize_enrichment({"budget_bucket": "10L+"}, course)
    assert out["budget_bucket"] == "1-3L"  # deterministic wins over LLM hallucination


def test_normalize_backfills_prestige_from_slug():
    course = {"slug": "applied-ai-iiitb", "provider": "IIIT Bangalore"}
    out = _normalize_enrichment({}, course)
    assert out["prestige_signal"] == "iiit"
