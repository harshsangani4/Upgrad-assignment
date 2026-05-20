from backend.chat.question_router import DEFAULT_FIELDS, route


def test_eligibility_question_surfaces_expected_fields():
    fields = route("any degree needed?")
    for f in ["eligibility_raw", "min_degree", "min_marks_pct", "programme_type_key", "<heuristic:eligibility>"]:
        assert f in fields


def test_multimatch_duration_and_fees():
    fields = route("tell me the hours and fees")
    assert "duration_label" in fields or "duration_weeks" in fields
    assert "fee_inr_total" in fields or "emi_starts_from_inr" in fields
    assert "<heuristic:duration>" in fields
    assert "<heuristic:fees>" in fields


def test_unrouted_returns_default():
    assert route("tell me more") == DEFAULT_FIELDS
    assert route("") == DEFAULT_FIELDS


def test_faculty_question():
    fields = route("who teaches it?")
    assert "faculty" in fields


def test_format_question():
    fields = route("is this online or offline?")
    assert "format" in fields
    assert "<heuristic:format>" in fields


def test_dedupe_preserves_order_no_duplicates():
    fields = route("what's the duration, hours, and how long")
    assert len(fields) == len(set(fields))
