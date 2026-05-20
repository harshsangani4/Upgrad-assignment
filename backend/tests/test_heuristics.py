from backend.chat.heuristics import (
    PROGRAMME_TYPE_KEYS,
    heuristic_block,
    heuristic_for,
    normalize_programme_type,
)


def test_normalize_known_types():
    assert normalize_programme_type("Bootcamp") == "bootcamp"
    assert normalize_programme_type("Job-ready Program in Data Science") == "bootcamp"
    assert normalize_programme_type("Executive Certificate") == "executive_cert"
    assert normalize_programme_type("MBA") == "mba"
    assert normalize_programme_type("DBA from Golden Gate") == "dba"
    assert normalize_programme_type("Master's Degree") == "masters"
    assert normalize_programme_type("PG Certificate") == "certificate"


def test_normalize_specificity_order():
    assert normalize_programme_type("Master of Business Administration") == "mba"
    assert normalize_programme_type("Doctorate of Business Administration") == "dba"


def test_normalize_empty_defaults_to_certificate():
    assert normalize_programme_type(None) == "certificate"
    assert normalize_programme_type("") == "certificate"
    assert normalize_programme_type("something weird") == "certificate"


def test_heuristic_for_returns_text():
    assert "12th-pass" in heuristic_for("eligibility", "bootcamp")
    assert heuristic_for("fees", "mba")
    assert heuristic_for("nonexistent", "bootcamp") is None


def test_heuristic_for_unknown_key_falls_back_to_certificate():
    out = heuristic_for("eligibility", "banana")
    assert out == heuristic_for("eligibility", "certificate")


def test_heuristic_block_contains_all_four_and_caveat():
    block = heuristic_block("pgp")
    for word in ["Eligibility:", "Duration:", "Format:", "Fees:", "typically", "official upGrad page"]:
        assert word in block


def test_all_keys_have_all_tables():
    for key in PROGRAMME_TYPE_KEYS:
        for field in ("eligibility", "duration", "format", "fees"):
            assert heuristic_for(field, key), f"missing {field} heuristic for {key}"
