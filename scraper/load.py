"""Persist parsed+enriched courses into SQLite, then regenerate `data/courses.xlsx`."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from openpyxl import Workbook
from sqlalchemy.orm import Session

from backend.models import Course, CourseModule, CourseTag, get_engine, get_session_factory, init_db


XLSX_PATH = Path("data/courses.xlsx")

TAG_SOURCES = (
    ("tool", "tools"),
    ("industry", "industries"),
    ("company", "hiring_companies"),
    ("vibe", "vibe"),
    ("persona", "best_for_personas"),
    ("domain", "domain_focus"),
)


def _to_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _to_datetime(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _bool_to_int(v: Any) -> int | None:
    if v is None:
        return None
    return 1 if v else 0


def _build_course(merged: dict) -> Course:
    """Construct a transient Course ORM object from a merged parsed+enriched dict."""
    return Course(
        slug=merged["slug"],
        url=merged.get("url") or f"https://www.upgrad.com/{merged['slug']}/",
        title=merged.get("title") or merged["slug"],
        provider=merged.get("provider"),
        co_brand=merged.get("co_brand"),
        programme_type=merged.get("programme_type"),
        category=merged.get("breadcrumb_category"),
        duration_weeks=merged.get("duration_weeks"),
        duration_label=merged.get("duration_label"),
        weekly_hours=merged.get("weekly_hours"),
        start_date=_to_date(merged.get("start_date")),
        admission_deadline=_to_date(merged.get("admission_deadline")),
        emi_starts_from_inr=merged.get("emi_starts_from_inr"),
        fee_inr_total=merged.get("fee_inr_total"),
        fee_usd_total=merged.get("fee_usd_total"),
        fee_bucket=merged.get("budget_bucket"),
        format=merged.get("format"),
        schedule=merged.get("schedule"),
        level=merged.get("level"),
        min_years_exp=merged.get("min_years_experience"),
        min_degree=merged.get("min_degree"),
        min_marks_pct=merged.get("min_marks_pct"),
        requires_coding=_bool_to_int(merged.get("requires_coding")),
        requires_quant=_bool_to_int(merged.get("requires_quant")),
        prestige_signal=merged.get("prestige_signal"),
        hero_tagline=merged.get("hero_tagline"),
        one_line_pitch=merged.get("one_line_pitch"),
        raw_html_path=str(Path("data/raw") / f"{merged['slug']}.html"),
        last_scraped_at=_to_datetime(merged.get("last_scraped_at")),
    )


def _tag_rows(merged: dict) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for tag_type, key in TAG_SOURCES:
        for value in merged.get(key) or []:
            if isinstance(value, str) and value.strip():
                rows.append((tag_type, value.strip()))
    # target_roles is a list of {role, salary_label}
    for role in merged.get("target_roles") or []:
        if isinstance(role, dict) and role.get("role"):
            rows.append(("role", role["role"].strip()))
    # faculty is a list of {name, title, linkedin}; flatten to "Name|Title"
    for fac in merged.get("faculty") or []:
        if isinstance(fac, dict) and fac.get("name"):
            title = (fac.get("title") or "").strip()
            rows.append(("faculty", f"{fac['name'].strip()}|{title}"))
    # dedupe preserving order
    seen, out = set(), []
    for tt, tv in rows:
        key = (tt, tv)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _module_rows(merged: dict) -> list[CourseModule]:
    out: list[CourseModule] = []
    modules = merged.get("modules") or []
    for idx, m in enumerate(modules, start=1):
        if not isinstance(m, dict):
            continue
        out.append(CourseModule(
            position=idx,
            name=m.get("name"),
            weeks=m.get("weeks"),
            topics=json.dumps(m.get("topics") or [], ensure_ascii=False),
        ))
    return out


def upsert_course(session: Session, merged: dict) -> Course:
    """Insert-or-update one course (replacing its tags + modules)."""
    slug = merged["slug"]
    existing = session.query(Course).filter_by(slug=slug).one_or_none()
    new = _build_course(merged)

    if existing is None:
        session.add(new)
        session.flush()
        existing = new
    else:
        for col in (
            "url", "title", "provider", "co_brand", "programme_type", "category",
            "duration_weeks", "duration_label", "weekly_hours",
            "start_date", "admission_deadline",
            "emi_starts_from_inr", "fee_inr_total", "fee_usd_total", "fee_bucket",
            "format", "schedule", "level", "min_years_exp", "min_degree", "min_marks_pct",
            "requires_coding", "requires_quant", "prestige_signal",
            "hero_tagline", "one_line_pitch", "raw_html_path", "last_scraped_at",
        ):
            setattr(existing, col, getattr(new, col))
        existing.tags.clear()
        existing.modules.clear()
        session.flush()

    for tag_type, tag_value in _tag_rows(merged):
        existing.tags.append(CourseTag(tag_type=tag_type, tag_value=tag_value))
    for module in _module_rows(merged):
        existing.modules.append(module)

    session.flush()
    return existing


def upsert_many(courses: Iterable[dict], db_path: Path | str | None = None) -> int:
    """Upsert a batch; returns the number of rows written."""
    engine = get_engine(db_path)
    init_db(engine)
    factory = get_session_factory(engine)
    count = 0
    with factory() as session:
        for merged in courses:
            upsert_course(session, merged)
            count += 1
        session.commit()
    return count


# ---------- xlsx export ---------------------------------------------------------

XLSX_COLUMNS = (
    "slug", "url", "title", "provider", "co_brand", "programme_type", "category",
    "duration_weeks", "duration_label", "weekly_hours",
    "start_date", "admission_deadline",
    "emi_starts_from_inr", "fee_inr_total", "fee_usd_total", "fee_bucket",
    "format", "schedule", "level", "min_years_exp", "min_degree", "min_marks_pct",
    "requires_coding", "requires_quant", "prestige_signal",
    "hero_tagline", "one_line_pitch", "last_scraped_at",
)


def _course_to_row(course: Course) -> list[Any]:
    row: list[Any] = []
    for col in XLSX_COLUMNS:
        val = getattr(course, col)
        if val is None:
            row.append("")
        elif isinstance(val, (date, datetime)):
            row.append(val.isoformat())
        else:
            row.append(val)

    tags_by_type: dict[str, list[str]] = {}
    for t in course.tags:
        tags_by_type.setdefault(t.tag_type, []).append(t.tag_value)
    for tag_type in ("tool", "industry", "company", "role", "vibe", "persona", "domain"):
        row.append(", ".join(sorted(tags_by_type.get(tag_type, []))))

    module_names = " | ".join(
        f"{m.position}. {m.name}" + (f" ({m.weeks}w)" if m.weeks else "")
        for m in course.modules if m.name
    )
    row.append(module_names)
    return row


def export_xlsx(db_path: Path | str | None = None, xlsx_path: Path | str = XLSX_PATH) -> Path:
    """Dump the courses table into a single-sheet xlsx for ops visibility."""
    factory = get_session_factory(get_engine(db_path))
    target = Path(xlsx_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "courses"
    header = list(XLSX_COLUMNS) + ["tools", "industries", "companies", "roles", "vibe", "personas", "domains", "modules"]
    ws.append(header)

    with factory() as session:
        courses = session.query(Course).order_by(Course.slug).all()
        for course in courses:
            ws.append(_course_to_row(course))

    wb.save(target)
    return target
