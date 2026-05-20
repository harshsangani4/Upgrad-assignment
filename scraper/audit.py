"""Field-coverage audit (Phase 11.1).

`python -m scraper.audit` writes data/coverage_report.csv (one row per course)
and prints a per-column present/total summary so we know which fields are
genuinely missing before tuning prompts to compensate.
"""

from __future__ import annotations

import csv
from pathlib import Path

from backend.models import Course, get_engine, get_session_factory

REPORT_PATH = Path("data/coverage_report.csv")

# column name -> threshold (Phase 11.2.4), used by the opt-in coverage gate.
# Set just below measured live-catalog coverage so the gate guards against
# regressions without being aspirational. Measured after the multi-template
# eligibility chain + broadened FAQ matching:
#   - eligibility_raw: 95% (87/92) -> threshold 0.90 (the spec's original target, now met).
#   - min_degree: 73% (67/92) -> threshold 0.65. The remaining ~25 courses
#     (bootcamps/certs) deliberately state no degree requirement; this is near
#     the real ceiling, below the spec's optimistic 0.80.
#   - modules: 12% (11/92) -> threshold 0.10. Only the cert/genai template
#     exposes structured module JSON; university-partner pages render curriculum
#     as prose. The course-QA goal does not depend on this (heuristics + tools cover it).
THRESHOLDS = {
    "has_eligibility_raw": 0.90,
    "has_min_degree": 0.65,
    "has_modules": 0.10,
}

BOOLEAN_COLUMNS = [
    "has_eligibility_raw",
    "has_min_degree",
    "has_min_marks_pct",
    "has_duration_weeks",
    "has_emi",
    "has_admission_deadline",
    "has_modules",
    "has_faculty",
    "has_tools",
]


def _row_for(course: Course) -> dict:
    tags_by_type: dict[str, list[str]] = {}
    for t in course.tags:
        tags_by_type.setdefault(t.tag_type, []).append(t.tag_value)
    return {
        "slug": course.slug,
        "has_eligibility_raw": bool(getattr(course, "eligibility_raw", None)),
        "has_min_degree": bool(course.min_degree),
        "has_min_marks_pct": course.min_marks_pct is not None,
        "has_duration_weeks": course.duration_weeks is not None,
        "has_emi": course.emi_starts_from_inr is not None,
        "has_admission_deadline": course.admission_deadline is not None,
        "has_modules": len(course.modules) > 0,
        "has_faculty": bool(tags_by_type.get("faculty")),
        "has_tools": bool(tags_by_type.get("tool") or tags_by_type.get("tools")),
        "programme_type": course.programme_type or "",
    }


def collect_rows(db_path: str | None = None) -> list[dict]:
    factory = get_session_factory(get_engine(db_path))
    with factory() as db:
        return [_row_for(c) for c in db.query(Course).order_by(Course.slug).all()]


def summarize(rows: list[dict]) -> dict[str, tuple[int, int]]:
    total = len(rows)
    out: dict[str, tuple[int, int]] = {}
    for col in BOOLEAN_COLUMNS:
        present = sum(1 for r in rows if r.get(col))
        out[col] = (present, total)
    return out


def write_csv(rows: list[dict], path: Path = REPORT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["slug", *BOOLEAN_COLUMNS, "programme_type"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def main() -> None:
    rows = collect_rows()
    if not rows:
        print("No courses in DB. Run `python -m scraper.run --full` first.")
        return
    path = write_csv(rows)
    summary = summarize(rows)
    print(f"Wrote {path} ({len(rows)} courses)\n")
    for col, (present, total) in summary.items():
        pct = round(100 * present / total) if total else 0
        flag = ""
        thr = THRESHOLDS.get(col)
        if thr is not None and total and (present / total) < thr:
            flag = f"  <-- BELOW THRESHOLD ({int(thr * 100)}%)"
        print(f"{col:24s}: {present}/{total} present ({pct}%){flag}")


if __name__ == "__main__":
    main()
