"""Pydantic request / response schemas for the FastAPI app."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class RecommendRequest(BaseModel):
    session_id: str
    offset: int = 0
    limit: int = 3
    filter_override: dict[str, Any] | None = None


class Recommendation(BaseModel):
    course_slug: str
    course_url: str
    title: str
    provider: str | None = None
    programme_type: str | None = None
    duration_label: str | None = None
    level: str | None = None
    format: str | None = None
    fee_bucket: str | None = None
    why_this_fits: str
    fit_reasons: list[str] = Field(default_factory=list)
    watch_outs: str | None = None
    faculty: list[dict[str, str]] = Field(default_factory=list)


class SessionDump(BaseModel):
    session_id: str
    slot_values: dict[str, Any]
    asked_history: list[str]
    attempts: dict[str, int]
    message_count: int


class CourseDetail(BaseModel):
    slug: str
    url: str
    title: str
    provider: str | None = None
    co_brand: str | None = None
    programme_type: str | None = None
    category: str | None = None
    duration_weeks: int | None = None
    duration_label: str | None = None
    weekly_hours: float | None = None
    start_date: str | None = None
    admission_deadline: str | None = None
    emi_starts_from_inr: int | None = None
    fee_inr_total: int | None = None
    fee_bucket: str | None = None
    format: str | None = None
    schedule: str | None = None
    level: str | None = None
    prestige_signal: str | None = None
    hero_tagline: str | None = None
    one_line_pitch: str | None = None
    tags: dict[str, list[str]] = Field(default_factory=dict)
    modules: list[dict[str, Any]] = Field(default_factory=list)
