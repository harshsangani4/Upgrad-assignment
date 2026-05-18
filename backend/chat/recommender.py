"""3-stage hybrid recommender: SQL hard filter → embedding similarity → LLM rerank → 3 picks."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
from openai import OpenAI
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.models import Course


RERANK_PROMPT_TEMPLATE = """\
You are picking the 3 best upGrad courses for this user.

Inputs:
- User profile (filled slots): {profile_json}
- Recent conversation: {last_6_messages}
- 8 candidate courses (already pre-filtered for hard constraints): {candidates_json}

Pick exactly 3. Optimize for fit, not variety. If two courses are similarly good, prefer the one whose vibe and prestige_signal match the user's vibe_preference and prestige_preference.

Output STRICT JSON only:
{{
  "picks": [
    {{"slug": "...", "why_this_fits": "one sentence, 18 words max, in the same warm tone as the chat"}},
    ...
  ]
}}

The "why_this_fits" sentence must reference something concrete from the user's situation. No marketing speak.
"""


EMB_PATH = Path("data/course_embeddings.npy")
EMB_INDEX_PATH = Path("data/course_embeddings.index.json")


BUDGET_ORDER = {"<1L": 0, "1-3L": 1, "3-5L": 2, "5-10L": 3, "10L+": 4}
DEGREE_ORDER = {"12th": 0, "diploma": 1, "bachelors": 2, "masters": 3, "phd": 4}
FORMAT_COMPAT = {
    "online": {"online", "hybrid"},
    "offline": {"offline", "hybrid"},
    "hybrid": {"online", "offline", "hybrid"},
}


# ---------- Stage 1: SQL hard filter ---------------------------------------------

def _build_sql_filters(slot_values: dict[str, Any]) -> list:
    f: list = []
    if isinstance(slot_values.get("years_experience"), int):
        f.append(or_(Course.min_years_exp.is_(None), Course.min_years_exp <= slot_values["years_experience"]))
    if slot_values.get("can_code") is False:
        f.append(or_(Course.requires_coding.is_(None), Course.requires_coding == 0))
    if isinstance(slot_values.get("min_marks_pct_est"), int):
        f.append(or_(Course.min_marks_pct.is_(None), Course.min_marks_pct <= slot_values["min_marks_pct_est"]))
    if isinstance(slot_values.get("weekly_hours"), int):
        f.append(or_(Course.weekly_hours.is_(None), Course.weekly_hours <= slot_values["weekly_hours"]))
    fp = slot_values.get("format_preference")
    if fp in FORMAT_COMPAT:
        allowed = list(FORMAT_COMPAT[fp])
        f.append(or_(Course.format.is_(None), Course.format.in_(allowed)))
    return f


def _passes_python_filters(course: Course, slot_values: dict[str, Any]) -> bool:
    # budget bucket: course bucket must be ≤ user budget bucket
    user_budget = slot_values.get("budget_bucket")
    if user_budget in BUDGET_ORDER and course.fee_bucket in BUDGET_ORDER:
        if BUDGET_ORDER[course.fee_bucket] > BUDGET_ORDER[user_budget]:
            return False
    # education level: user must have at least the required degree
    user_edu = slot_values.get("education_level")
    if user_edu in DEGREE_ORDER and course.min_degree:
        c_key = course.min_degree.lower().replace("'", "").replace(" ", "")
        # map "bachelor's" → "bachelors", "master's" → "masters" etc.
        if "12th" in c_key:
            req = 0
        elif "diploma" in c_key:
            req = 1
        elif "bachelors" in c_key:
            req = 2
        elif "masters" in c_key:
            req = 3
        elif "phd" in c_key:
            req = 4
        else:
            req = None
        if req is not None and DEGREE_ORDER[user_edu] < req:
            return False
    return True


def hard_filter(session: Session, slot_values: dict[str, Any]) -> list[Course]:
    q = session.query(Course)
    for cond in _build_sql_filters(slot_values):
        q = q.filter(cond)
    candidates = q.all()
    return [c for c in candidates if _passes_python_filters(c, slot_values)]


# ---------- Stage 2: embedding similarity ---------------------------------------

def _profile_text(slot_values: dict[str, Any]) -> str:
    parts: list[str] = []
    if slot_values.get("current_role"):
        parts.append(f"Currently a {slot_values['current_role']}.")
    if slot_values.get("years_experience") is not None:
        parts.append(f"{slot_values['years_experience']} years of experience.")
    if slot_values.get("education_level"):
        parts.append(f"Education: {slot_values['education_level']}.")
    if slot_values.get("career_goal"):
        parts.append(f"Goal: {slot_values['career_goal']}.")
    domain = slot_values.get("domain_interest")
    if domain:
        parts.append("Interested in " + (", ".join(domain) if isinstance(domain, list) else str(domain)) + ".")
    if slot_values.get("weekly_hours"):
        parts.append(f"Can give {slot_values['weekly_hours']} hours per week.")
    if slot_values.get("format_preference"):
        parts.append(f"Format: {slot_values['format_preference']}.")
    if slot_values.get("schedule_preference"):
        parts.append(f"Schedule: {slot_values['schedule_preference']}.")
    if slot_values.get("budget_bucket"):
        parts.append(f"Budget: {slot_values['budget_bucket']}.")
    if slot_values.get("vibe_preference"):
        vibe = slot_values["vibe_preference"]
        parts.append("Vibe: " + (", ".join(vibe) if isinstance(vibe, list) else str(vibe)) + ".")
    return " ".join(parts) or "An aspiring upGrad learner."


def _load_embeddings() -> tuple[np.ndarray | None, dict[str, int] | None]:
    if not EMB_PATH.exists() or not EMB_INDEX_PATH.exists():
        return None, None
    matrix = np.load(EMB_PATH)
    index = json.loads(EMB_INDEX_PATH.read_text(encoding="utf-8"))
    return matrix, {str(k): int(v) for k, v in index.items()}


def _embed_user_profile(text: str, client: OpenAI) -> np.ndarray | None:
    model = os.getenv("OPENAI_MODEL_EMBED", "text-embedding-3-small")
    try:
        resp = client.embeddings.create(model=model, input=[text])
        return np.array(resp.data[0].embedding, dtype=np.float32)
    except Exception:
        return None


def top_n_by_similarity(
    candidates: list[Course],
    slot_values: dict[str, Any],
    n: int = 8,
    client: OpenAI | None = None,
    matrix: np.ndarray | None = None,
    index: dict[str, int] | None = None,
) -> list[Course]:
    if len(candidates) <= n:
        return candidates
    if matrix is None or index is None:
        matrix, index = _load_embeddings()
    if matrix is None or index is None or matrix.size == 0:
        return candidates[:n]

    client = client or OpenAI()
    profile_vec = _embed_user_profile(_profile_text(slot_values), client)
    if profile_vec is None:
        return candidates[:n]

    profile_norm = np.linalg.norm(profile_vec) or 1.0
    scores: list[tuple[float, Course]] = []
    for c in candidates:
        row = index.get(str(c.id))
        if row is None:
            scores.append((0.0, c))
            continue
        v = matrix[row]
        v_norm = np.linalg.norm(v) or 1.0
        scores.append((float(np.dot(profile_vec, v) / (profile_norm * v_norm)), c))
    scores.sort(key=lambda t: t[0], reverse=True)
    return [c for _, c in scores[:n]]


# ---------- Stage 3: LLM rerank --------------------------------------------------

def _faculty_for(course: Course, limit: int = 4) -> list[dict[str, str]]:
    """Pull `Name|Title` pairs stored under tag_type='faculty'."""
    out: list[dict[str, str]] = []
    for t in course.tags:
        if t.tag_type != "faculty":
            continue
        name, _, title = t.tag_value.partition("|")
        out.append({"name": name.strip(), "title": title.strip()})
        if len(out) >= limit:
            break
    return out


def _candidate_summary(c: Course) -> dict[str, Any]:
    return {
        "slug": c.slug,
        "title": c.title,
        "provider": c.provider,
        "co_brand": c.co_brand,
        "programme_type": c.programme_type,
        "duration_label": c.duration_label,
        "level": c.level,
        "format": c.format,
        "schedule": c.schedule,
        "fee_bucket": c.fee_bucket,
        "prestige_signal": c.prestige_signal,
        "one_line_pitch": c.one_line_pitch,
        "faculty": _faculty_for(c),
    }


def _last_6_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    return messages[-6:]


def _course_to_card(c: Course, why: str) -> dict[str, Any]:
    return {
        "course_slug": c.slug,
        "course_url": c.url,
        "title": c.title,
        "provider": c.provider,
        "duration_label": c.duration_label,
        "fee_bucket": c.fee_bucket,
        "why_this_fits": why,
        "faculty": _faculty_for(c, limit=4),
    }


def rerank_and_format(
    candidates: list[Course],
    slot_values: dict[str, Any],
    messages: list[dict[str, str]],
    client: OpenAI | None = None,
) -> list[dict[str, Any]]:
    """Call the rerank LLM; return 3 (or fewer) result cards."""
    if not candidates:
        return []
    client = client or OpenAI()
    model = os.getenv("OPENAI_MODEL_RERANK", "gpt-4o")

    payload = RERANK_PROMPT_TEMPLATE.format(
        profile_json=json.dumps(slot_values, ensure_ascii=False),
        last_6_messages=json.dumps(_last_6_messages(messages), ensure_ascii=False),
        candidates_json=json.dumps([_candidate_summary(c) for c in candidates], ensure_ascii=False),
    )

    by_slug = {c.slug: c for c in candidates}
    picks: list[dict[str, Any]] = []
    try:
        resp = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            temperature=0.3,
            messages=[{"role": "user", "content": payload}],
        )
        raw = json.loads(resp.choices[0].message.content or "{}")
        for pick in (raw.get("picks") or [])[:3]:
            slug = pick.get("slug")
            why = (pick.get("why_this_fits") or "").strip()
            if slug in by_slug and why:
                picks.append(_course_to_card(by_slug[slug], why))
    except Exception:
        picks = []

    # Fallback: if rerank fails or returns < 3, pad with embedding-order top picks.
    if len(picks) < 3:
        seen = {p["course_slug"] for p in picks}
        for c in candidates:
            if c.slug in seen:
                continue
            picks.append(_course_to_card(c, c.one_line_pitch or "A solid fit for what you described."))
            if len(picks) == 3:
                break

    return picks[:3]


# ---------- top-level entry points ----------------------------------------------

def recommend(
    session: Session,
    slot_values: dict[str, Any],
    messages: list[dict[str, str]],
    client: OpenAI | None = None,
) -> list[dict[str, Any]]:
    candidates = hard_filter(session, slot_values)
    top_8 = top_n_by_similarity(candidates, slot_values, n=8, client=client)
    return rerank_and_format(top_8, slot_values, messages, client=client)


PRESTIGE_WEIGHT = {"iit": 4, "iim": 4, "iiit": 3, "global_uni": 2, "industry_only": 1, "none": 0}


def browse_top(
    session: Session,
    slot_values: dict[str, Any] | None = None,
    n: int = 8,
) -> list[dict[str, Any]]:
    """Round-robin pick across categories so the user sees a diverse slice."""
    slot_values = slot_values or {}
    candidates = hard_filter(session, slot_values) if slot_values else session.query(Course).all()
    if not candidates:
        candidates = session.query(Course).all()

    by_cat: dict[str, list[Course]] = {}
    for c in candidates:
        cat = c.category or "Other"
        by_cat.setdefault(cat, []).append(c)
    for cat, lst in by_cat.items():
        lst.sort(key=lambda c: (-PRESTIGE_WEIGHT.get(c.prestige_signal or "none", 0), c.slug))

    picks: list[Course] = []
    while len(picks) < n:
        added = False
        for cat in list(by_cat.keys()):
            if not by_cat[cat]:
                continue
            picks.append(by_cat[cat].pop(0))
            added = True
            if len(picks) >= n:
                break
        if not added:
            break

    return [
        _course_to_card(c, c.one_line_pitch or f"{c.programme_type or 'Course'} from {c.provider or 'upGrad'}.")
        for c in picks[:n]
    ]
