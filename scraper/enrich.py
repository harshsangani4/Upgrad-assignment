"""
LLM enrichment + embeddings for parsed courses.

`enrich_one(course)` calls the chat model in JSON mode and returns the constraint
fields the recommender filters on (level, format, schedule, requires_coding,
prestige_signal, one_line_pitch, vibe tags, etc.). `embed_batch(texts)` calls
the embedding model. Deterministic helpers (`compute_fee_bucket`,
`infer_prestige_signal_from_slug`) bypass the LLM where we can trust regex.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


ALLOWED = {
    "level": ("beginner", "intermediate", "advanced", "executive"),
    "format": ("online", "offline", "hybrid"),
    "schedule": ("self_paced", "weekend_cohort", "weekday_cohort"),
    "budget_bucket": ("<1L", "1-3L", "3-5L", "5-10L", "10L+"),
    "primary_outcome": ("career_switch", "promotion", "skill_up", "founders_track", "academic"),
    "prestige_signal": ("iit", "iim", "iiit", "global_uni", "industry_only", "none"),
}

VIBE_TAGS = ("rigorous", "applied", "research-heavy", "industry-led")

ENRICH_SCHEMA_NOTE = """\
You normalize a single upGrad course's raw scraped content into structured constraints. Output STRICT JSON only — no prose.

Input: a JSON blob with the course's title, hero_tagline, modules, tools, eligibility text, target roles, programme_type, duration_weeks, weekly_hours, emi_starts_from_inr.

Schema:
{
  "level": "beginner"|"intermediate"|"advanced"|"executive",
  "min_years_experience": 0,
  "requires_coding": true,
  "requires_quant": true,
  "max_weekly_hours": 12,
  "format": "online"|"offline"|"hybrid",
  "schedule": "self_paced"|"weekend_cohort"|"weekday_cohort",
  "budget_bucket": "<1L"|"1-3L"|"3-5L"|"5-10L"|"10L+",
  "language": "english",
  "primary_outcome": "career_switch"|"promotion"|"skill_up"|"founders_track"|"academic",
  "vibe": ["rigorous", "applied", "research-heavy", "industry-led"],
  "best_for_personas": ["working professional 5-10 yrs", "fresh grad", "manager moving into IC"],
  "domain_focus": ["agentic_ai", "applied_ml", "data_engineering"],
  "prestige_signal": "iit"|"iim"|"iiit"|"global_uni"|"industry_only"|"none",
  "one_line_pitch": "..."
}

Rules:
- budget_bucket inference: if upfront fee is null but EMI is known, assume 24-month tenure → total ≈ EMI × 24, then bucket. If both are null, infer from programme_type: Certificate=<1L, Bootcamp=<1L, PGP=3-5L, Masters=5-10L, MBA=5-10L, DBA=10L+.
- prestige_signal: pick the single strongest brand on the page (IIT > IIM > IIIT > global_uni > industry_only > none).
- one_line_pitch: max 22 words. Plain prose. No marketing adjectives ("transformative", "cutting-edge"). Reference the actual outcome.
- Output ONLY the JSON.
"""


def _client() -> OpenAI:
    return OpenAI()


# ---------- deterministic helpers ----------------------------------------------

def compute_fee_bucket(fee_inr_total: int | None, emi_starts_from_inr: int | None) -> str | None:
    """Pick a bucket from total fee if known, else estimate via EMI × 24 per spec §3.1."""
    estimate: int | None = None
    if fee_inr_total and fee_inr_total > 0:
        estimate = fee_inr_total
    elif emi_starts_from_inr and emi_starts_from_inr > 0:
        estimate = emi_starts_from_inr * 24
    if estimate is None:
        return None
    if estimate < 100_000:
        return "<1L"
    if estimate < 300_000:
        return "1-3L"
    if estimate < 500_000:
        return "3-5L"
    if estimate < 1_000_000:
        return "5-10L"
    return "10L+"


def infer_prestige_signal_from_slug(slug: str, provider: str | None, co_brand: str | None) -> str | None:
    """Cheap deterministic prestige tag. Returns None if we can't confidently decide."""
    s = (slug or "").lower()
    p = " ".join(filter(None, [provider or "", co_brand or ""])).lower()
    blob = f"{s} {p}"
    if "iiitb" in blob or re.search(r"\biiit[-\s]?bangalore\b", blob) or "iiit" in blob:
        return "iiit"
    if re.search(r"\biim[-\s]?[a-z]?\b", blob) or "indian institute of management" in blob:
        return "iim"
    if re.search(r"\biit[-\s]?[a-z]?\b", blob) or "indian institute of technology" in blob:
        return "iit"
    if any(tag in blob for tag in ("ljmu", "ggu", "golden gate", "edgewood", "esgci", "ssbm",
                                   "northeastern", "maryland", "touro", "liverpool", "rushford",
                                   "jindal", "jgu", "jgls", "psb", "waterloo", "mit", "imt-",
                                   "imtg", "ism-germany", "neu-")):
        return "global_uni"
    if any(tag in blob for tag in ("microsoft", "pwc", "hdfc")):
        return "industry_only"
    return None


# ---------- LLM enrichment ------------------------------------------------------

def _course_summary_for_prompt(course: dict) -> str:
    fields = (
        ("slug", course.get("slug")),
        ("title", course.get("title")),
        ("provider", course.get("provider")),
        ("co_brand", course.get("co_brand")),
        ("programme_type", course.get("programme_type")),
        ("duration_label", course.get("duration_label")),
        ("duration_weeks", course.get("duration_weeks")),
        ("weekly_hours", course.get("weekly_hours")),
        ("breadcrumb_category", course.get("breadcrumb_category")),
        ("hero_tagline", course.get("hero_tagline")),
        ("eligibility_raw", (course.get("eligibility_raw") or "")[:600]),
        ("emi_starts_from_inr", course.get("emi_starts_from_inr")),
        ("fee_inr_total", course.get("fee_inr_total")),
    )
    lines = [f"{k}: {v}" for k, v in fields if v not in (None, "")]
    modules = course.get("modules") or []
    if modules:
        names = ", ".join(m.get("name", "") for m in modules if m.get("name"))
        lines.append(f"modules: {names}")
    tools = course.get("tools") or []
    if tools:
        lines.append(f"tools: {', '.join(tools[:20])}")
    roles = course.get("target_roles") or []
    if roles:
        names = ", ".join(r.get("role", "") for r in roles if r.get("role"))
        if names:
            lines.append(f"target_roles: {names}")
    highlights = course.get("key_highlights") or []
    if highlights:
        lines.append("key_highlights: " + " | ".join(highlights[:6]))
    return "\n".join(lines)


def _coerce_enum(value: Any, allowed: tuple[str, ...], default: str | None = None) -> str | None:
    if isinstance(value, str) and value in allowed:
        return value
    return default


def _coerce_list_enum(value: Any, allowed: tuple[str, ...]) -> list[str]:
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, str) and v in allowed]


def _normalize_enrichment(raw: dict, course: dict) -> dict:
    """Validate the LLM JSON; backfill with deterministic helpers and safe defaults."""
    out = {
        "level": _coerce_enum(raw.get("level"), ALLOWED["level"], "intermediate"),
        "min_years_experience": int(raw.get("min_years_experience") or 0) if str(raw.get("min_years_experience", "0")).lstrip("-").isdigit() else 0,
        "requires_coding": bool(raw.get("requires_coding", False)),
        "requires_quant": bool(raw.get("requires_quant", False)),
        "max_weekly_hours": int(raw.get("max_weekly_hours") or 12) if str(raw.get("max_weekly_hours", "12")).lstrip("-").isdigit() else 12,
        "format": _coerce_enum(raw.get("format"), ALLOWED["format"], "online"),
        "schedule": _coerce_enum(raw.get("schedule"), ALLOWED["schedule"], "weekend_cohort"),
        "budget_bucket": _coerce_enum(raw.get("budget_bucket"), ALLOWED["budget_bucket"]),
        "language": "english",
        "primary_outcome": _coerce_enum(raw.get("primary_outcome"), ALLOWED["primary_outcome"], "skill_up"),
        "vibe": _coerce_list_enum(raw.get("vibe"), VIBE_TAGS) or ["applied"],
        "best_for_personas": [s for s in (raw.get("best_for_personas") or []) if isinstance(s, str)][:6],
        "domain_focus": [s for s in (raw.get("domain_focus") or []) if isinstance(s, str)][:6],
        "prestige_signal": _coerce_enum(raw.get("prestige_signal"), ALLOWED["prestige_signal"]),
        "one_line_pitch": (raw.get("one_line_pitch") or "").strip() or None,
    }

    # Deterministic overrides where we trust regex more than the LLM.
    deterministic_bucket = compute_fee_bucket(course.get("fee_inr_total"), course.get("emi_starts_from_inr"))
    if deterministic_bucket:
        out["budget_bucket"] = deterministic_bucket
    if not out["prestige_signal"]:
        out["prestige_signal"] = infer_prestige_signal_from_slug(
            course.get("slug", ""), course.get("provider"), course.get("co_brand")
        ) or "none"
    return out


def enrich_one(course: dict, client: OpenAI | None = None, *, retries: int = 1) -> dict:
    """Call the enrich model and return a normalized enrichment dict."""
    client = client or _client()
    model = os.getenv("OPENAI_MODEL_ENRICH", "gpt-4o")
    summary = _course_summary_for_prompt(course)

    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                response_format={"type": "json_object"},
                temperature=0.2,
                messages=[
                    {"role": "system", "content": ENRICH_SCHEMA_NOTE},
                    {"role": "user", "content": summary},
                ],
            )
            raw = json.loads(resp.choices[0].message.content or "{}")
            return _normalize_enrichment(raw, course)
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.0 + attempt)
            continue

    # Final fallback: deterministic-only enrichment.
    fallback = _normalize_enrichment({}, course)
    fallback["_enrich_error"] = str(last_err) if last_err else "unknown"
    return fallback


# ---------- embeddings ----------------------------------------------------------

def embedding_input(course: dict) -> str:
    """Build the embedding input string per spec §3.2."""
    parts: list[str] = []
    if course.get("title"):
        parts.append(course["title"].strip())
    if course.get("hero_tagline"):
        parts.append(course["hero_tagline"].strip())
    if course.get("one_line_pitch"):
        parts.append(course["one_line_pitch"].strip())
    module_names = [m.get("name") for m in (course.get("modules") or []) if m.get("name")]
    if module_names:
        parts.append("Modules: " + ", ".join(module_names))
    tools = course.get("tools") or []
    if tools:
        parts.append("Tools: " + ", ".join(tools[:30]))
    return ". ".join(parts)


def embed_batch(texts: list[str], client: OpenAI | None = None, *, batch_size: int = 96) -> np.ndarray:
    """Embed a list of strings; returns an (N, 1536) float32 matrix aligned to input order."""
    if not texts:
        return np.zeros((0, 1536), dtype=np.float32)
    client = client or _client()
    model = os.getenv("OPENAI_MODEL_EMBED", "text-embedding-3-small")
    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        chunk = texts[i : i + batch_size]
        resp = client.embeddings.create(model=model, input=chunk)
        chunk_sorted = sorted(resp.data, key=lambda d: d.index)
        vectors.extend(d.embedding for d in chunk_sorted)
    return np.array(vectors, dtype=np.float32)


def main() -> None:
    import argparse
    from pathlib import Path

    ap = argparse.ArgumentParser(description="Enrich a single parsed course JSON (printed to stdout).")
    ap.add_argument("course_json", help="Path to a parsed course JSON file (output of `python -m scraper.parse`).")
    args = ap.parse_args()

    course = json.loads(Path(args.course_json).read_text(encoding="utf-8"))
    enriched = enrich_one(course)
    enriched["embedding_input_preview"] = embedding_input({**course, **enriched})
    print(json.dumps(enriched, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
