"""Tests for course_qa.py (Task 9.4).

Uses lightweight fakes — no real DB or OpenAI calls.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from backend.chat.course_qa import build_course_context_message


def _make_course(n_modules: int = 3) -> MagicMock:
    """Build a minimal fake Course ORM object."""
    course = MagicMock()
    course.title = "Applied AI Certificate"
    course.provider = "IIIT Bangalore"
    course.programme_type = "PG Certificate"
    course.duration_label = "11 months"
    course.weekly_hours = 10.0
    course.min_degree = "Bachelor's"
    course.emi_starts_from_inr = 5631
    course.format = "online"
    course.schedule = "weekend_cohort"
    course.level = "Advanced"

    # Modules
    modules = []
    for i in range(1, n_modules + 1):
        m = MagicMock()
        m.position = i
        m.name = f"Module {i}"
        m.topics = json.dumps([f"Topic {i}A", f"Topic {i}B"])
        modules.append(m)
    course.modules = modules

    # Tags
    tags = [
        MagicMock(tag_type="tool", tag_value="Python"),
        MagicMock(tag_type="tool", tag_value="TensorFlow"),
        MagicMock(tag_type="faculty", tag_value="Dr. Smith|Professor"),
        MagicMock(tag_type="target_role", tag_value="ML Engineer"),
        MagicMock(tag_type="hiring_company", tag_value="Google"),
    ]
    course.tags = tags

    return course


class TestBuildCourseContextMessage:
    def test_title_in_context(self) -> None:
        course = _make_course()
        ctx = build_course_context_message(course)
        assert "Applied AI Certificate" in ctx

    def test_module_count_in_context(self) -> None:
        course = _make_course(n_modules=4)
        ctx = build_course_context_message(course)
        assert "4 total" in ctx

    def test_module_names_in_context(self) -> None:
        course = _make_course(n_modules=2)
        ctx = build_course_context_message(course)
        assert "Module 1" in ctx
        assert "Module 2" in ctx

    def test_emi_in_context(self) -> None:
        course = _make_course()
        ctx = build_course_context_message(course)
        assert "5631" in ctx

    def test_faculty_in_context(self) -> None:
        course = _make_course()
        ctx = build_course_context_message(course)
        assert "Dr. Smith" in ctx

    def test_tools_in_context(self) -> None:
        course = _make_course()
        ctx = build_course_context_message(course)
        assert "Python" in ctx
        assert "TensorFlow" in ctx

    def test_no_modules_shows_unavailable(self) -> None:
        course = _make_course(n_modules=0)
        ctx = build_course_context_message(course)
        assert "not available" in ctx

    def test_context_is_string(self) -> None:
        course = _make_course()
        ctx = build_course_context_message(course)
        assert isinstance(ctx, str)
        assert len(ctx) > 50
