from dataclasses import dataclass, field
from datetime import datetime

from services.vector_store import delete_session_store


@dataclass
class SessionData:
    session_id: str
    pdf_names: list[str]
    summary: str
    warning: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionData] = {}

    def create_session(self, session: SessionData) -> None:
        self._sessions[session.session_id] = session

    def get_session(self, session_id: str) -> SessionData:
        return self._sessions[session_id]

    def has_session(self, session_id: str) -> bool:
        return session_id in self._sessions

    def clear_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        delete_session_store(session_id)


session_manager = SessionManager()

