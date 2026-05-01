from dataclasses import dataclass, field
from datetime import datetime

from langchain_core.documents import Document

from services.schemas import RichSummary, UploadedPDFInfo
from services.vector_store import delete_session_store


@dataclass
class UploadedPDFRecord:
    pdf_id: str
    pdf_name: str
    chunk_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SessionData:
    session_id: str
    pdf_names: list[str]
    summary: str
    uploaded_pdfs: list[UploadedPDFRecord] = field(default_factory=list)
    summary_details: RichSummary | None = None
    key_concepts: list[str] = field(default_factory=list)
    chunk_documents: list[Document] = field(default_factory=list)
    warning: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionData] = {}

    def create_session(self, session: SessionData) -> None:
        self._sessions[session.session_id] = session

    def upsert_session(self, session: SessionData) -> None:
        self._sessions[session.session_id] = session

    def get_session(self, session_id: str) -> SessionData:
        return self._sessions[session_id]

    def has_session(self, session_id: str) -> bool:
        return session_id in self._sessions

    def list_uploaded_pdfs(self, session_id: str) -> list[UploadedPDFInfo]:
        session = self.get_session(session_id)
        return [
            UploadedPDFInfo(
                pdf_id=record.pdf_id,
                pdf_name=record.pdf_name,
                chunk_count=record.chunk_count,
            )
            for record in session.uploaded_pdfs
        ]

    def clear_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        delete_session_store(session_id)


session_manager = SessionManager()
