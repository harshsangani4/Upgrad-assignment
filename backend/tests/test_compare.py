"""Tests for build_comparison (Task 9.5).

Uses lightweight fakes — no real DB or OpenAI calls.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


def _make_course(slug: str, title: str) -> MagicMock:
    c = MagicMock()
    c.slug = slug
    c.title = title
    c.provider = "upGrad"
    c.duration_label = "10 months"
    c.format = "online"
    c.level = "Advanced"
    c.fee_bucket = "3-5L"
    c.emi_starts_from_inr = 6000
    c.min_years_exp = 3
    c.min_degree = "Bachelor's"
    c.tags = [
        MagicMock(tag_type="tool", tag_value="Python"),
        MagicMock(tag_type="target_role", tag_value="Data Scientist"),
    ]
    return c


def _fake_db(courses: list[MagicMock]) -> MagicMock:
    db = MagicMock()
    slug_map = {c.slug: c for c in courses}

    def _query_filter_one(slug: str):
        return slug_map.get(slug)

    # Chain: db.query(Course).filter(...).one_or_none()
    q = MagicMock()
    q.filter.return_value.one_or_none.side_effect = lambda: None
    db.query.return_value = q

    # Patch per-slug
    def side_effect(model):
        inner = MagicMock()
        def filt(*args, **kwargs):
            f2 = MagicMock()
            # Capture the slug from the BinaryExpression args if possible.
            # Simpler: always return both courses; test just checks counts.
            f2.one_or_none.return_value = None
            return f2
        inner.filter = filt
        return inner

    db.query.side_effect = side_effect
    return db


class TestBuildComparison:
    def test_empty_slugs_returns_empty_courses(self) -> None:
        from backend.chat.recommender import build_comparison
        db = MagicMock()
        db.query.return_value.filter.return_value.one_or_none.return_value = None
        result = build_comparison([], {}, db)
        assert result["courses"] == []
        assert "comparison_id" in result

    def test_result_has_required_keys(self) -> None:
        from backend.chat.recommender import build_comparison

        course_a = _make_course("slug-a", "Course A")
        course_b = _make_course("slug-b", "Course B")

        db = MagicMock()
        call_count = [0]

        def query_side(model):
            inner = MagicMock()
            courses_list = [course_a, course_b]

            def filt(*args, **kwargs):
                f2 = MagicMock()
                idx = call_count[0]
                call_count[0] += 1
                f2.one_or_none.return_value = courses_list[idx] if idx < len(courses_list) else None
                return f2

            inner.filter = filt
            return inner

        db.query.side_effect = query_side

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "Course A suits career switchers. Course B fits those with 5+ years."
        mock_client.chat.completions.create.return_value = mock_resp

        result = build_comparison(["slug-a", "slug-b"], {"years_experience": 3}, db, client=mock_client)

        assert "comparison_id" in result
        assert "courses" in result
        assert "summary" in result
        assert len(result["courses"]) == 2

    def test_course_row_has_required_fields(self) -> None:
        from backend.chat.recommender import build_comparison

        course_a = _make_course("slug-a", "Course A")

        db = MagicMock()
        db.query.return_value.filter.return_value.one_or_none.return_value = course_a

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "A good fit overall."
        mock_client.chat.completions.create.return_value = mock_resp

        result = build_comparison(["slug-a"], {}, db, client=mock_client)
        row = result["courses"][0]

        for field in ("slug", "title", "provider", "duration_label", "format", "level", "fee_bucket",
                      "emi_starts_from_inr", "min_years_exp", "min_degree", "top_tools", "target_roles_top"):
            assert field in row, f"Missing field {field!r} in comparison row"
