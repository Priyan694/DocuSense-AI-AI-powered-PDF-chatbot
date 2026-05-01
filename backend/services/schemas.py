from typing import Literal

from pydantic import BaseModel, Field


Provider = Literal["minimax", "groq", "openai"]
IntentType = Literal["strict_pdf", "explanation", "summary", "comparison", "example", "unknown"]
AnswerModePreference = Literal["auto", "strict_pdf", "explanation"]
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


class SummaryTerm(BaseModel):
    term: str
    explanation: str


class UploadedPDFInfo(BaseModel):
    pdf_id: str
    pdf_name: str
    chunk_count: int = 0


class RichSummary(BaseModel):
    overall_summary: str = ""
    main_objective: str = ""
    key_concepts: list[str] = Field(default_factory=list)
    important_terms: list[SummaryTerm] = Field(default_factory=list)
    missing_but_important_terms: list[SummaryTerm] = Field(default_factory=list)
    additional_general_explanation: str = ""
    final_takeaway: str = ""


class UploadResponse(BaseModel):
    status: str
    session_id: str
    summary: str
    summary_details: RichSummary | None = None
    key_concepts: list[str] = Field(default_factory=list)
    warning: str | None = None
    pdf_names: list[str]
    uploaded_pdfs: list[UploadedPDFInfo] = Field(default_factory=list)
    uploaded_pdf_count: int = 0
    chunk_count: int


class AskRequest(BaseModel):
    session_id: str
    question: str = Field(min_length=1)
    llm_provider: Provider = "minimax"
    simple_language: bool = False
    answer_mode_preference: AnswerModePreference = "auto"


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceReference]
    confidence: float
    weak_context: bool
    rewritten_question: str | None = None
    intent: IntentType = "unknown"
    answer_mode: Literal["strict_pdf", "explanation"] = "strict_pdf"


class ActionRequest(BaseModel):
    session_id: str
    action: ActionType
    llm_provider: Provider = "minimax"
    compare_instruction: str | None = None


class ActionResponse(BaseModel):
    action: ActionType
    content: str
    sources: list[SourceReference]


class CompareRequest(BaseModel):
    session_id: str
    llm_provider: Provider = "minimax"
    compare_instruction: str | None = None


class CompareResponse(BaseModel):
    content: str
    sources: list[SourceReference]
    uploaded_pdf_count: int
    uploaded_pdfs: list[UploadedPDFInfo] = Field(default_factory=list)


class UploadedPDFListResponse(BaseModel):
    session_id: str
    uploaded_pdfs: list[UploadedPDFInfo]
    uploaded_pdf_count: int
    chunk_count: int


class ResetRequest(BaseModel):
    session_id: str


class StatusResponse(BaseModel):
    status: str
    message: str
