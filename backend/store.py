"""In-memory session store + DB session factory."""

from __future__ import annotations

import threading
import uuid
from typing import Iterator

from sqlalchemy.orm import Session

from backend.chat.planner import SessionState
from backend.models import get_engine, get_session_factory


_sessions: dict[str, SessionState] = {}
_lock = threading.Lock()


def get_or_create_session(session_id: str | None) -> SessionState:
    """Look up an existing session or mint a new one."""
    with _lock:
        if session_id and session_id in _sessions:
            return _sessions[session_id]
        sid = session_id or str(uuid.uuid4())
        state = SessionState(session_id=sid)
        _sessions[sid] = state
        return state


def get_session(session_id: str) -> SessionState | None:
    return _sessions.get(session_id)


def reset_sessions() -> None:
    """Test-only: wipe the in-memory store."""
    with _lock:
        _sessions.clear()


# DB session factory (singleton)
_engine = None
_factory = None


def db_session() -> Iterator[Session]:
    global _engine, _factory
    if _factory is None:
        _engine = get_engine()
        _factory = get_session_factory(_engine)
    s = _factory()
    try:
        yield s
    finally:
        s.close()
