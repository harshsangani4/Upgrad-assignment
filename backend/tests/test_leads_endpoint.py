"""Integration tests for POST /api/leads (Phase 13.3): persistence, idempotency, validation."""

import backend.leads.store as store
from backend.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def _isolate_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "LEADS_DB", tmp_path / "leads.sqlite")
    monkeypatch.setattr(store, "LEADS_XLSX", tmp_path / "leads.xlsx")


def test_lead_persists_and_idempotent(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    payload = {
        "session_id": "s1", "form_id": "f1",
        "name": "Astha M", "email": "a@x.com",
        "phone": "+91-9876543210", "course_slug": "applied-ai-iiitb",
        "consent": True,
    }
    r1 = client.post("/api/leads", json=payload)
    assert r1.status_code == 200
    assert r1.json()["duplicate"] is False
    assert r1.json()["message"]  # server-templated confirmation

    r2 = client.post("/api/leads", json=payload)
    assert r2.status_code == 200
    assert r2.json()["duplicate"] is True


def test_lead_rejects_bad_phone(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    r = client.post("/api/leads", json={
        "session_id": "s2", "form_id": "f2", "name": "X",
        "email": "x@y.com", "phone": "123", "consent": True,
    })
    assert r.status_code == 422


def test_lead_requires_consent(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    r = client.post("/api/leads", json={
        "session_id": "s3", "form_id": "f3", "name": "X",
        "email": "x@y.com", "phone": "9876543210", "consent": False,
    })
    assert r.status_code == 422


def test_lead_rejects_bad_email(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    r = client.post("/api/leads", json={
        "session_id": "s4", "form_id": "f4", "name": "X",
        "email": "not-an-email", "phone": "9876543210", "consent": True,
    })
    assert r.status_code == 422


def test_dismiss_returns_reply(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    r = client.post("/api/leads/dismiss", json={"session_id": "nope", "form_id": "f5"})
    # session not found → 404 (no session created in this isolated test)
    assert r.status_code == 404
