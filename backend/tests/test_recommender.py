import json
import re
from types import SimpleNamespace

import pytest

from backend.chat.recommender import recommend, hard_filter
from backend.models import Base, Course, CourseTag, get_session_factory
from sqlalchemy import create_engine


# ---------- fixtures ------------------------------------------------------------

def _seed_course(**kwargs) -> Course:
    defaults = dict(
        slug="x", url="https://www.upgrad.com/x/", title="X",
        provider="ProvCo", co_brand=None, programme_type="Certificate",
        category="Machine Learning and AI",
        duration_weeks=20, duration_label="20 Weeks", weekly_hours=9.0,
        start_date=None, admission_deadline=None,
        emi_starts_from_inr=None, fee_inr_total=None, fee_usd_total=None,
        fee_bucket="1-3L",
        format="online", schedule="weekend_cohort", level="intermediate",
        min_years_exp=2, min_degree="Bachelor's", min_marks_pct=50,
        requires_coding=1, requires_quant=1,
        prestige_signal="iiit",
        hero_tagline="Build production AI",
        one_line_pitch="Master applied AI in 5 months.",
        raw_html_path=None, last_scraped_at=None,
    )
    defaults.update(kwargs)
    return Course(**defaults)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = get_session_factory(engine)
    with factory() as s:
        s.add_all([
            _seed_course(slug="iiitb-applied-ai", title="Applied AI IIITB", level="executive", min_years_exp=3),
            _seed_course(slug="iim-mba", title="MBA from IIM", fee_bucket="5-10L", min_degree="Bachelor's",
                         programme_type="MBA", level="advanced", min_years_exp=3, format="hybrid",
                         requires_coding=0, requires_quant=1, prestige_signal="iim"),
            _seed_course(slug="ljmu-msc", title="MSc Data Science", fee_bucket="3-5L", min_degree="Bachelor's",
                         programme_type="Masters", level="advanced", min_years_exp=1,
                         prestige_signal="global_uni"),
            _seed_course(slug="cert-gen-ai", title="GenAI Certificate", fee_bucket="<1L", min_degree="12th",
                         programme_type="Certificate", level="beginner", min_years_exp=0,
                         requires_coding=0, prestige_signal="industry_only"),
        ])
        s.commit()
        yield s


class FakeOpenAI:
    """Stub for the OpenAI client used in recommender (chat + embeddings)."""

    def __init__(self, picks: list[dict]):
        self.picks = picks
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat_create))
        self.embeddings = SimpleNamespace(create=self._emb_create)

    def _chat_create(self, **kwargs):
        body = {"picks": self.picks}
        msg = SimpleNamespace(content=json.dumps(body))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    def _emb_create(self, **kwargs):
        # tiny deterministic embedding per input
        n = len(kwargs.get("input") or [])
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1] * 1536, index=i) for i in range(n)])


# ---------- hard filter --------------------------------------------------------

def test_hard_filter_drops_courses_user_cant_take(session):
    # user is a fresh grad with 0 yrs experience, can't code
    slots = {"years_experience": 0, "can_code": False, "min_marks_pct_est": 55,
             "weekly_hours": 12, "format_preference": "online"}
    candidates = hard_filter(session, slots)
    slugs = {c.slug for c in candidates}
    # executive PGP requires 3 yrs → out
    assert "iiitb-applied-ai" not in slugs
    # MBA / MSc require coding=0 only the MBA, but also higher min_years_exp
    assert "iim-mba" not in slugs
    # GenAI cert and LJMU (min_years_exp=1, but coding required) — LJMU should be out
    assert "ljmu-msc" not in slugs
    # cert-gen-ai: requires_coding=0, min_years_exp=0 — passes
    assert "cert-gen-ai" in slugs


def test_hard_filter_respects_budget(session):
    slots = {"years_experience": 5, "min_marks_pct_est": 80, "weekly_hours": 12,
             "format_preference": "online", "budget_bucket": "1-3L"}
    candidates = hard_filter(session, slots)
    slugs = {c.slug for c in candidates}
    assert "iim-mba" not in slugs  # 5-10L > 1-3L
    assert "ljmu-msc" not in slugs  # 3-5L > 1-3L


# ---------- end-to-end recommend -----------------------------------------------

def test_recommend_returns_three_picks_with_required_fields(session):
    slots = {
        "years_experience": 4, "can_code": True, "min_marks_pct_est": 70,
        "weekly_hours": 12, "format_preference": "online",
        "budget_bucket": "5-10L", "education_level": "bachelors",
        "career_goal": "switch", "vibe_preference": ["applied"],
    }
    fake_picks = [
        {"slug": "iiitb-applied-ai", "why_this_fits": "Matches your 4 yrs and switch-into-AI ambition."},
        {"slug": "ljmu-msc", "why_this_fits": "A heavier academic option for the MSc tag if you want it."},
        {"slug": "cert-gen-ai", "why_this_fits": "Low-risk way to dip into GenAI on the side."},
    ]
    fake = FakeOpenAI(fake_picks)
    results = recommend(session, slots, messages=[], client=fake)

    assert len(results) == 3
    for r in results:
        assert r["why_this_fits"]
        assert r["course_url"].startswith("https://www.upgrad.com/")
        assert r["course_slug"]
        assert r["title"]


def test_recommend_falls_back_when_rerank_returns_nothing(session):
    slots = {"years_experience": 5, "can_code": True, "min_marks_pct_est": 80,
             "weekly_hours": 12, "format_preference": "online"}
    fake = FakeOpenAI([])  # empty picks — recommender should backfill
    results = recommend(session, slots, messages=[], client=fake)
    assert len(results) == 3
    for r in results:
        assert r["why_this_fits"]
        # new schema: fit_reasons always present (auto-generated on fallback)
        assert isinstance(r["fit_reasons"], list) and len(r["fit_reasons"]) >= 1


# ---------- filter override ----------------------------------------------------

def test_hard_filter_override_prestige(session):
    slots = {"years_experience": 5, "min_marks_pct_est": 80, "weekly_hours": 12,
             "format_preference": "online"}
    candidates = hard_filter(session, slots, filter_override={"prestige_signal": ["iim"]})
    assert {c.slug for c in candidates} == {"iim-mba"}


def test_hard_filter_override_fee_max(session):
    slots = {"years_experience": 5, "min_marks_pct_est": 80, "weekly_hours": 12,
             "format_preference": "online"}
    candidates = hard_filter(session, slots, filter_override={"fee_bucket_max": "1-3L"})
    # only courses at <=1-3L survive
    assert all(c.fee_bucket in {"<1L", "1-3L"} for c in candidates)
    assert "iim-mba" not in {c.slug for c in candidates}  # 5-10L


# ---------- pagination ---------------------------------------------------------

class EchoOpenAI:
    """Reranker stub: picks the first `n_picks` candidate slugs found in the prompt."""

    def __init__(self):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat))
        self.embeddings = SimpleNamespace(create=self._emb)

    def _chat(self, **kwargs):
        content = kwargs["messages"][-1]["content"]
        slugs = [s for s in re.findall(r'"slug":\s*"([^"]+)"', content) if s != "..."]
        m = re.search(r"picking the (\d+) best", content)
        n = int(m.group(1)) if m else 3
        picks = [
            {"slug": s, "why_this_fits": f"fits your 5 years ({s})",
             "fit_reasons": ["your 5 years"], "watch_outs": None}
            for s in slugs[:n]
        ]
        body = json.dumps({"picks": picks})
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=body))])

    def _emb(self, **kwargs):
        n = len(kwargs.get("input") or [])
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1] * 1536, index=i) for i in range(n)])


@pytest.fixture
def big_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = get_session_factory(engine)
    with factory() as s:
        # 8 permissive courses that all pass a 5-yr coder filter
        for i in range(8):
            s.add(_seed_course(
                slug=f"course-{i:02d}", title=f"Course {i}",
                min_years_exp=0, requires_coding=0, min_marks_pct=50,
                min_degree="Bachelor's", fee_bucket="<1L", format="online",
            ))
        s.commit()
        yield s


def test_recommender_pagination(big_session):
    slots = {"years_experience": 5, "can_code": True, "min_marks_pct_est": 80,
             "weekly_hours": 20, "format_preference": "online", "education_level": "bachelors"}
    fake = EchoOpenAI()
    page1 = recommend(big_session, slots, messages=[], client=fake, offset=0, limit=3)
    page2 = recommend(big_session, slots, messages=[], client=fake, offset=3, limit=3,
                      exclude_slugs={r["course_slug"] for r in page1})
    s1 = {r["course_slug"] for r in page1}
    s2 = {r["course_slug"] for r in page2}
    assert len(s1) == 3 and len(s2) == 3
    assert s1.isdisjoint(s2)  # no repeats across pages
