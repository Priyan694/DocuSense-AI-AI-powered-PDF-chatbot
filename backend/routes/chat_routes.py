from fastapi import APIRouter, HTTPException, Query

from services.compare_service import compare_uploaded_pdfs
from services.llm_service import LLMServiceError
from services.rag_graph import run_rag_query
from services.schemas import (
    ActionRequest,
    ActionResponse,
    AskRequest,
    AskResponse,
    CompareRequest,
    CompareResponse,
    ResetRequest,
    StatusResponse,
    UploadedPDFListResponse,
)
from services.session_store import session_manager
from services.utility_actions import run_pdf_action


router = APIRouter(tags=["chat"])


@router.post("/ask", response_model=AskResponse)
async def ask_question(payload: AskRequest) -> AskResponse:
    if not session_manager.has_session(payload.session_id):
        raise HTTPException(status_code=404, detail="No active PDF session found. Upload a PDF first.")

    try:
        return await run_rag_query(payload)
    except (RuntimeError, LLMServiceError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/action", response_model=ActionResponse)
async def run_action(payload: ActionRequest) -> ActionResponse:
    if not session_manager.has_session(payload.session_id):
        raise HTTPException(status_code=404, detail="No active PDF session found. Upload a PDF first.")

    try:
        return await run_pdf_action(payload)
    except LLMServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/reset", response_model=StatusResponse)
async def reset_session(payload: ResetRequest) -> StatusResponse:
    if not session_manager.has_session(payload.session_id):
        return StatusResponse(status="ok", message="Session already cleared.")

    session_manager.clear_session(payload.session_id)
    return StatusResponse(status="ok", message="PDF session reset successfully.")


@router.get("/uploaded-pdfs", response_model=UploadedPDFListResponse)
async def get_uploaded_pdfs(session_id: str = Query(...)) -> UploadedPDFListResponse:
    if not session_manager.has_session(session_id):
        raise HTTPException(status_code=404, detail="No active PDF session found. Upload a PDF first.")

    session = session_manager.get_session(session_id)
    return UploadedPDFListResponse(
        session_id=session_id,
        uploaded_pdfs=session_manager.list_uploaded_pdfs(session_id),
        uploaded_pdf_count=len(session.uploaded_pdfs),
        chunk_count=len(session.chunk_documents),
    )


@router.post("/compare", response_model=CompareResponse)
async def compare_pdfs(payload: CompareRequest) -> CompareResponse:
    if not session_manager.has_session(payload.session_id):
        raise HTTPException(status_code=404, detail="No active PDF session found. Upload a PDF first.")

    try:
        return await compare_uploaded_pdfs(
            session_id=payload.session_id,
            llm_provider=payload.llm_provider,
            compare_instruction=payload.compare_instruction,
        )
    except LLMServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
