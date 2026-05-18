"""SQLAlchemy 2.x declarative models matching docs/SCHEMA.md."""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)


DB_PATH = Path(os.getenv("COURSES_DB", "data/courses.sqlite"))


class Base(DeclarativeBase):
    pass


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    url: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)

    provider: Mapped[str | None] = mapped_column(String)
    co_brand: Mapped[str | None] = mapped_column(String)
    programme_type: Mapped[str | None] = mapped_column(String)
    category: Mapped[str | None] = mapped_column(String, index=True)

    duration_weeks: Mapped[int | None] = mapped_column(Integer)
    duration_label: Mapped[str | None] = mapped_column(String)
    weekly_hours: Mapped[float | None] = mapped_column()

    start_date: Mapped[date | None] = mapped_column(Date)
    admission_deadline: Mapped[date | None] = mapped_column(Date)

    emi_starts_from_inr: Mapped[int | None] = mapped_column(Integer)
    fee_inr_total: Mapped[int | None] = mapped_column(Integer)
    fee_usd_total: Mapped[int | None] = mapped_column(Integer)
    fee_bucket: Mapped[str | None] = mapped_column(String)

    format: Mapped[str | None] = mapped_column(String, index=True)
    schedule: Mapped[str | None] = mapped_column(String)
    level: Mapped[str | None] = mapped_column(String, index=True)
    min_years_exp: Mapped[int | None] = mapped_column(Integer)
    min_degree: Mapped[str | None] = mapped_column(String)
    min_marks_pct: Mapped[int | None] = mapped_column(Integer)
    requires_coding: Mapped[int | None] = mapped_column(Integer)
    requires_quant: Mapped[int | None] = mapped_column(Integer)
    prestige_signal: Mapped[str | None] = mapped_column(String)

    hero_tagline: Mapped[str | None] = mapped_column(Text)
    one_line_pitch: Mapped[str | None] = mapped_column(Text)
    raw_html_path: Mapped[str | None] = mapped_column(String)
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime)

    tags: Mapped[list["CourseTag"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    modules: Mapped[list["CourseModule"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="CourseModule.position",
        lazy="selectin",
    )


class CourseTag(Base):
    __tablename__ = "course_tags"

    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True
    )
    tag_type: Mapped[str] = mapped_column(String, primary_key=True)
    tag_value: Mapped[str] = mapped_column(String, primary_key=True)

    course: Mapped[Course] = relationship(back_populates="tags")


class CourseModule(Base):
    __tablename__ = "course_modules"

    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String)
    weeks: Mapped[int | None] = mapped_column(Integer)
    topics: Mapped[str | None] = mapped_column(Text)

    course: Mapped[Course] = relationship(back_populates="modules")


Index("idx_tags_value", CourseTag.tag_type, CourseTag.tag_value)


def get_engine(db_path: Path | str | None = None):
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", future=True)


def get_session_factory(engine=None) -> sessionmaker[Session]:
    return sessionmaker(bind=engine or get_engine(), expire_on_commit=False, future=True)


def init_db(engine=None) -> None:
    Base.metadata.create_all(engine or get_engine())
