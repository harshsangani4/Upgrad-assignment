"""Lead capture endpoint — the PII firewall (Phase 13.3).

Contract:
  1. Receives raw PII (name/email/phone) from the in-chat form.
  2. Validates and persists to leads.sqlite + leads.xlsx.
  3. Optionally fires a CRM webhook (fire-and-forget).
  4. Marks the session lead-captured and appends only a redacted marker to history.
  5. NEVER calls OpenAI. NEVER appends the payload to chat history.
"""

from __future__ import annotations

import logging
import os
import re

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.chat.lead_templates import pick_confirm, pick_declined_reply
from backend.chat.redaction import REDACTION_TOKEN
from backend.leads.store import insert_lead
from backend.store import get_session

router = APIRouter(prefix="/api/leads", tags=["leads"])
_log = logging.getLogger(__name__)

PHONE_RE = re.compile(r"^(\+?\d{1,3}[- ]?)?\d{10}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class LeadCreate(BaseModel):
    session_id: str
    form_id: str
    name: str = Field(min_length=1, max_length=80)
    email: str
    phone: str
    course_slug: str | None = None
    consent: bool

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip()
        if not EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        cleaned = v.strip().replace(" ", "").replace("-", "")
        if not PHONE_RE.match(cleaned):
            raise ValueError("Phone must be 10 digits, optionally prefixed with +<country>")
        return cleaned

    @field_validator("consent")
    @classmethod
    def _consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Consent is required")
        return v


class LeadDismiss(BaseModel):
    session_id: str
    form_id: str | None = None


def _fire_webhook(payload: dict) -> None:
    url = os.getenv("LEAD_WEBHOOK_URL")
    if not url:
        return
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(url, json=payload)
    except Exception as e:  # best-effort; lead is already persisted
        _log.warning("lead webhook failed: %r", e)


@router.post("")
def create_lead(payload: LeadCreate) -> dict:
    lead_id, duplicate = insert_lead(
        form_id=payload.form_id,
        session_id=payload.session_id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        course_slug=payload.course_slug,
    )

    # Update session in memory only; the LLM only ever sees the redaction marker.
    session = get_session(payload.session_id)
    if session is not None:
        session.lead_captured = True
        session.lead_id = lead_id
        session.lead_first_name = payload.name.split()[0] if payload.name.strip() else None
        if not duplicate:
            session.messages.append({"role": "user", "content": REDACTION_TOKEN, "redacted": True})

    if not duplicate:
        _log.info("lead_captured session=%s course=%s", payload.session_id, payload.course_slug)
        _fire_webhook({
            "lead_id": lead_id,
            "name": payload.name,
            "email": payload.email,
            "phone": payload.phone,
            "course_slug": payload.course_slug,
            "source": "chat",
        })

    return {"status": "ok", "lead_id": lead_id, "duplicate": duplicate, "message": pick_confirm()}


@router.post("/dismiss")
def dismiss_lead(payload: LeadDismiss) -> dict:
    session = get_session(payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    session.user_declined_lead = True
    session.turns_since_last_lead_offer = 0
    _log.info("lead_offer_dismissed session=%s", payload.session_id)
    return {"status": "ok", "message": pick_declined_reply()}
