"""One-shot migration (Phase 11.3.3).

Adds the `programme_type_key` and `eligibility_raw` columns to an existing
SQLite DB (SQLAlchemy create_all won't alter existing tables) and backfills
`programme_type_key` from the free-text `programme_type` of each row.

`eligibility_raw` stays NULL until the next `python -m scraper.run --refresh`,
since it can only be re-derived from the raw HTML.

    python -m scraper.migrate_programme_type
"""

from __future__ import annotations

from sqlalchemy import text

from backend.chat.heuristics import normalize_programme_type
from backend.models import get_engine


def _existing_columns(conn) -> set[str]:
    rows = conn.execute(text("PRAGMA table_info(courses)")).fetchall()
    return {r[1] for r in rows}


def migrate(db_path: str | None = None) -> dict[str, int]:
    engine = get_engine(db_path)
    added: list[str] = []
    backfilled = 0
    with engine.begin() as conn:
        cols = _existing_columns(conn)
        if "programme_type_key" not in cols:
            conn.execute(text("ALTER TABLE courses ADD COLUMN programme_type_key VARCHAR"))
            added.append("programme_type_key")
        if "eligibility_raw" not in cols:
            conn.execute(text("ALTER TABLE courses ADD COLUMN eligibility_raw TEXT"))
            added.append("eligibility_raw")

        rows = conn.execute(text("SELECT id, programme_type FROM courses")).fetchall()
        for row_id, programme_type in rows:
            key = normalize_programme_type(programme_type)
            conn.execute(
                text("UPDATE courses SET programme_type_key = :k WHERE id = :i"),
                {"k": key, "i": row_id},
            )
            backfilled += 1
    return {"columns_added": len(added), "rows_backfilled": backfilled}


def main() -> None:
    result = migrate()
    print(
        f"Migration done: added {result['columns_added']} column(s), "
        f"backfilled programme_type_key on {result['rows_backfilled']} rows."
    )


if __name__ == "__main__":
    main()
