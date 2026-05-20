"""Pipeline CLI: `python -m scraper.run --full | --refresh | --one <slug>`.

`--full`    discover → scrape every detail → parse → enrich → upsert → embed → xlsx.
`--refresh` re-scrape; only re-enrich/re-embed courses whose raw HTML changed.
`--one`     run a single slug end-to-end (no global embeddings rebuild).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

from backend.models import Course, CourseTag, get_engine, get_session_factory, init_db

from .detail import RAW_DIR, scrape_detail
from .discover import CourseURL, discover
from .enrich import embed_batch, embedding_input, enrich_one
from .load import XLSX_PATH, export_xlsx, upsert_course
from .parse import parse

load_dotenv()

EMB_PATH = Path("data/course_embeddings.npy")
EMB_INDEX_PATH = Path("data/course_embeddings.index.json")


def _hash_html(html: str) -> str:
    return hashlib.sha256(html.encode("utf-8", errors="ignore")).hexdigest()


def _read_existing_html(slug: str) -> str | None:
    path = RAW_DIR / f"{slug}.html"
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _process_one(url: str, category_hint: str | None = None, *, force_enrich: bool = True) -> dict | None:
    """Scrape one URL, parse, enrich. Returns the merged dict ready for upsert."""
    try:
        detail = scrape_detail(url, save_html=True)
    except Exception as e:
        print(f"  [error] scrape {url}: {e}", file=sys.stderr)
        return None

    try:
        parsed = parse(detail.html, slug=detail.slug, url=url)
    except Exception as e:
        print(f"  [error] parse {detail.slug}: {e}", file=sys.stderr)
        return None

    if category_hint and not parsed.get("breadcrumb_category"):
        # use the seed-page category as a fallback when JSON-LD breadcrumb is missing
        parsed["breadcrumb_category"] = category_hint

    if force_enrich:
        try:
            enriched = enrich_one(parsed)
        except Exception as e:
            print(f"  [error] enrich {detail.slug}: {e}", file=sys.stderr)
            enriched = {}
    else:
        enriched = {}

    return {**parsed, **enriched, "slug": detail.slug, "url": url}


def _rebuild_embeddings(merged_list: list[dict]) -> None:
    """Embed every (merged) course and write npy + index json keyed by course_id."""
    if not merged_list:
        print("[embed] no courses; skipping embeddings.")
        return
    texts = [embedding_input(m) for m in merged_list]
    print(f"[embed] embedding {len(texts)} courses...")
    vectors = embed_batch(texts)

    factory = get_session_factory(get_engine())
    with factory() as session:
        slug_to_id = {c.slug: c.id for c in session.query(Course).all()}

    index = {}
    aligned: list[np.ndarray] = []
    for row, merged in enumerate(merged_list):
        course_id = slug_to_id.get(merged["slug"])
        if course_id is None:
            continue
        index[str(course_id)] = len(aligned)
        aligned.append(vectors[row])

    matrix = np.array(aligned, dtype=np.float32) if aligned else np.zeros((0, vectors.shape[1]), dtype=np.float32)
    EMB_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.save(EMB_PATH, matrix)
    EMB_INDEX_PATH.write_text(json.dumps(index, indent=2))
    print(f"[embed] wrote {matrix.shape[0]} embeddings of dim {matrix.shape[1]} to {EMB_PATH}")


def cmd_full() -> int:
    init_db(get_engine())
    urls: list[CourseURL] = discover()
    print(f"[discover] {len(urls)} URLs")

    merged_list: list[dict] = []
    factory = get_session_factory(get_engine())
    with factory() as session:
        for i, cu in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}] {cu.slug}")
            merged = _process_one(cu.url, category_hint=cu.category_hint)
            if not merged:
                continue
            upsert_course(session, merged)
            merged_list.append(merged)
            if i % 10 == 0:
                session.commit()
        session.commit()

    _rebuild_embeddings(merged_list)
    export_xlsx(xlsx_path=XLSX_PATH)
    print(f"[done] {len(merged_list)} courses; xlsx → {XLSX_PATH}")
    return 0


def cmd_refresh() -> int:
    init_db(get_engine())
    urls: list[CourseURL] = discover()
    print(f"[discover] {len(urls)} URLs (refresh mode)")

    merged_list: list[dict] = []
    changed_slugs: set[str] = set()
    factory = get_session_factory(get_engine())

    with factory() as session:
        for i, cu in enumerate(urls, 1):
            old_html = _read_existing_html(cu.slug)
            try:
                detail = scrape_detail(cu.url, save_html=True)
            except Exception as e:
                print(f"  [error] scrape {cu.url}: {e}", file=sys.stderr)
                continue
            old_hash = _hash_html(old_html) if old_html else None
            new_hash = _hash_html(detail.html)
            if old_hash == new_hash:
                continue
            print(f"[{i}/{len(urls)}] CHANGED {cu.slug}")
            parsed = parse(detail.html, slug=detail.slug, url=cu.url)
            if cu.category_hint and not parsed.get("breadcrumb_category"):
                parsed["breadcrumb_category"] = cu.category_hint
            try:
                enriched = enrich_one(parsed)
            except Exception as e:
                print(f"  [error] enrich {cu.slug}: {e}", file=sys.stderr)
                enriched = {}
            merged = {**parsed, **enriched, "slug": detail.slug, "url": cu.url}
            upsert_course(session, merged)
            merged_list.append(merged)
            changed_slugs.add(cu.slug)
            if len(changed_slugs) % 10 == 0:
                session.commit()
        session.commit()

    print(f"[refresh] {len(changed_slugs)} changed; rebuilding embeddings for full catalog")
    # rebuild embeddings for the WHOLE catalog so the matrix stays aligned with DB ids
    if changed_slugs:
        with factory() as session:
            all_courses = session.query(Course).order_by(Course.slug).all()
        # synthesize minimal merged dicts from DB for unchanged courses
        full_merged: list[dict] = []
        merged_by_slug = {m["slug"]: m for m in merged_list}
        for c in all_courses:
            if c.slug in merged_by_slug:
                full_merged.append(merged_by_slug[c.slug])
            else:
                full_merged.append({
                    "slug": c.slug,
                    "title": c.title,
                    "hero_tagline": c.hero_tagline,
                    "one_line_pitch": c.one_line_pitch,
                    "modules": [{"name": m.name} for m in c.modules],
                    "tools": [t.tag_value for t in c.tags if t.tag_type == "tool"],
                })
        _rebuild_embeddings(full_merged)
    export_xlsx(xlsx_path=XLSX_PATH)
    print(f"[done] {len(changed_slugs)} updated; xlsx → {XLSX_PATH}")
    return 0


def cmd_backfill_faculty() -> int:
    """Re-parse every saved data/raw/<slug>.html for faculty and refresh the faculty tags.

    Cheap, no scraping, no LLM calls. Useful when the faculty extractor improves and
    you don't want to re-enrich the whole catalog.
    """
    init_db(get_engine())
    factory = get_session_factory(get_engine())
    touched = 0
    skipped_no_html = 0
    with factory() as session:
        for course in session.query(Course).order_by(Course.slug).all():
            html_path = Path(course.raw_html_path or RAW_DIR / f"{course.slug}.html")
            if not html_path.exists():
                skipped_no_html += 1
                continue
            try:
                html = html_path.read_text(encoding="utf-8")
            except OSError:
                continue
            parsed = parse(html, slug=course.slug, url=course.url)
            faculty = parsed.get("faculty") or []

            # drop existing faculty tags, insert new
            for t in list(course.tags):
                if t.tag_type == "faculty":
                    session.delete(t)
            session.flush()
            for fac in faculty:
                if not isinstance(fac, dict) or not fac.get("name"):
                    continue
                title = (fac.get("title") or "").strip()
                course.tags.append(CourseTag(
                    course_id=course.id,
                    tag_type="faculty",
                    tag_value=f"{fac['name'].strip()}|{title}",
                ))
            touched += 1
            if touched % 20 == 0:
                session.commit()
                print(f"[backfill] {touched} courses processed")
        session.commit()
    print(f"[done] backfilled faculty for {touched} courses ({skipped_no_html} skipped — no raw HTML)")
    return 0


def cmd_rederive_eligibility() -> int:
    """Re-parse eligibility (+ derive degree/marks) from each saved data/raw/<slug>.html.

    No scraping, no LLM calls. Re-runs the parser's eligibility chain over local HTML
    so improvements to selectors / FAQ matching / degree derivation take effect without
    a full re-scrape.
    """
    init_db(get_engine())
    factory = get_session_factory(get_engine())
    touched = 0
    filled_elig = 0
    filled_degree = 0
    skipped = 0
    with factory() as session:
        for course in session.query(Course).order_by(Course.slug).all():
            html_path = Path(course.raw_html_path or RAW_DIR / f"{course.slug}.html")
            if not html_path.exists():
                skipped += 1
                continue
            try:
                html = html_path.read_text(encoding="utf-8")
            except OSError:
                skipped += 1
                continue
            parsed = parse(html, slug=course.slug, url=course.url)
            elig = parsed.get("eligibility_raw")
            if elig:
                course.eligibility_raw = elig
                filled_elig += 1
            if parsed.get("min_degree"):
                course.min_degree = parsed["min_degree"]
                filled_degree += 1
            if parsed.get("min_marks_pct") is not None:
                course.min_marks_pct = parsed["min_marks_pct"]
            touched += 1
        session.commit()
    print(
        f"[done] reparsed {touched} courses ({skipped} skipped); "
        f"eligibility_raw set on {filled_elig}, min_degree on {filled_degree}"
    )
    return 0


def cmd_one(slug: str) -> int:
    init_db(get_engine())
    url = f"https://www.upgrad.com/{slug}/"
    merged = _process_one(url)
    if not merged:
        print(f"[error] pipeline failed for {slug}", file=sys.stderr)
        return 1
    factory = get_session_factory(get_engine())
    with factory() as session:
        upsert_course(session, merged)
        session.commit()
    print(f"[done] {slug} upserted; modules={len(merged.get('modules', []))} tools={len(merged.get('tools', []))}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="upGrad course scraper pipeline.")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--full", action="store_true", help="Discover + scrape every URL end-to-end.")
    group.add_argument("--refresh", action="store_true", help="Only re-enrich/embed pages whose HTML changed.")
    group.add_argument("--one", metavar="SLUG", help="Run a single slug through the pipeline.")
    group.add_argument("--backfill-faculty", action="store_true",
                       help="Re-parse saved HTML for faculty only; no scraping, no LLM calls.")
    group.add_argument("--rederive-eligibility", action="store_true",
                       help="Re-derive min_degree/min_marks_pct from stored eligibility_raw; no scraping, no LLM calls.")
    args = ap.parse_args()

    t0 = time.time()
    if args.full:
        rc = cmd_full()
    elif args.refresh:
        rc = cmd_refresh()
    elif args.backfill_faculty:
        rc = cmd_backfill_faculty()
    elif args.rederive_eligibility:
        rc = cmd_rederive_eligibility()
    else:
        rc = cmd_one(args.one)
    print(f"[time] {time.time() - t0:.1f}s")
    return rc


if __name__ == "__main__":
    sys.exit(main())
