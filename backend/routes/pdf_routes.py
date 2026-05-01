from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from services.pdf_pipeline import process_uploaded_pdfs
from services.schemas import UploadResponse


router = APIRouter(tags=["pdf"])


@router.post("/upload-pdf", response_model=UploadResponse)
async def upload_pdf(
    files: list[UploadFile] = File(...),
    llm_provider: str = Form("minimax"),
    session_id: str | None = Form(default=None),
) -> UploadResponse:
    if not files:
        raise HTTPException(status_code=400, detail="At least one PDF file is required.")

    return await process_uploaded_pdfs(files=files, llm_provider=llm_provider, session_id=session_id)
