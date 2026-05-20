"""Coverage gate (Phase 11.6.3).

Opt-in: this gate depends on a fresh `scraper.run --refresh`, so it does not run
in the normal unit suite (which would go red on stale/un-refreshed data). Run it
explicitly after a refresh:

    RUN_COVERAGE_GATE=1 pytest backend/tests/test_coverage.py -q   # bash
    $env:RUN_COVERAGE_GATE=1; pytest backend/tests/test_coverage.py -q   # PowerShell

Fails if any tracked column drops below its Phase 11.2.4 threshold.
"""

import os

import pytest

from scraper.audit import THRESHOLDS, collect_rows, summarize

DB_PATH = os.getenv("COURSES_DB", "data/courses.sqlite")

_ENABLED = os.getenv("RUN_COVERAGE_GATE") == "1"
_ROWS = collect_rows(DB_PATH) if (_ENABLED and os.path.exists(DB_PATH)) else []
pytestmark = pytest.mark.skipif(
    not _ENABLED or not _ROWS,
    reason="coverage gate is opt-in: set RUN_COVERAGE_GATE=1 after scraper.run --refresh",
)


@pytest.mark.parametrize("column,threshold", list(THRESHOLDS.items()))
def test_column_meets_threshold(column, threshold):
    summary = summarize(_ROWS)
    present, total = summary[column]
    pct = present / total if total else 0
    assert pct >= threshold, f"{column}: {present}/{total} ({pct:.0%}) below {threshold:.0%}"
