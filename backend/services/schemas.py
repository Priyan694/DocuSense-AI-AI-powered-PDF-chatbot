from typing import Literal

from pydantic import BaseModel, Field


Provider = Literal["minimax", "groq"]
ActionType = Literal[
    "simple_explain",
    "key_points",
    "mcqs",
    "flashcards",
    "rewrite",
    "compare",
]


class SourceReference(BaseModel):
    pdf_name: str
    page_number: int
    chunk_id: str
    relevance_score: float | None = None


class UploadResponse(BaseModel):
    status: str
    session_id: str
    summary: str
    warning: str | None = None
    pdf_names: list[str]
    chunk_count: int


class AskRequest(BaseModel):
    session_id: str
    question: str = Field(min_length=1)
    llm_provider: Provider = "minimax"
    simple_language: bool = False


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceReference]
    confidence: float
    weak_context: bool
    rewritten_question: str | None = None


class ActionRequest(BaseModel):
    session_id: str
    action: ActionType
    llm_provider: Provider = "minimax"
    compare_instruction: str | None = None


class ActionResponse(BaseModel):
    action: ActionType
    content: str
    sources: list[SourceReference]


class ResetRequest(BaseModel):
    session_id: str


class StatusResponse(BaseModel):
    status: str
    message: str

