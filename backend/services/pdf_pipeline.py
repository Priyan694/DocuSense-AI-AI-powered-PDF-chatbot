import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from langchain_core.documents import Document

from services.chunker import split_documents
from services.config import BASE_DIR, settings
from services.llm_service import LLMServiceError, generate_summary
from services.pdf_processor import extract_documents_from_pdf
from services.schemas import UploadResponse
from services.session_store import SessionData, session_manager
from services.vector_store import index_documents


TEMP_DIR = BASE_DIR / "temp_uploads"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


async def _save_upload(upload: UploadFile) -> Path:
    if upload.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail=f"{upload.filename} is not a PDF.")

    content = await upload.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"{upload.filename} exceeds the {settings.max_upload_size_mb} MB limit.",
        )

    file_path = TEMP_DIR / f"{uuid.uuid4()}_{upload.filename}"
    file_path.write_bytes(content)
    return file_path


async def process_uploaded_pdfs(files: list[UploadFile], llm_provider: str) -> UploadResponse:
    session_id = uuid.uuid4().hex
    all_documents: list[Document] = []
    pdf_names: list[str] = []
    warnings: list[str] = []

    for upload in files:
        file_path = await _save_upload(upload)
        pdf_name = upload.filename or file_path.name
        pdf_names.append(pdf_name)
        documents, warning = extract_documents_from_pdf(file_path, pdf_name)
        if warning:
            warnings.append(f"{pdf_name}: {warning}")
        all_documents.extend(documents)
        file_path.unlink(missing_ok=True)

    if not all_documents:
        raise HTTPException(status_code=400, detail="No readable text found in the uploaded PDFs.")

    chunked_docs = split_documents(all_documents)
    for index, doc in enumerate(chunked_docs):
        doc.metadata["chunk_id"] = f"chunk-{index + 1}"

    chunk_count = index_documents(session_id, chunked_docs)
    combined_context = "\n\n".join(doc.page_content for doc in all_documents[:12])

    try:
        summary = await generate_summary(combined_context)
    except LLMServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    session_manager.create_session(
        SessionData(
            session_id=session_id,
            pdf_names=pdf_names,
            summary=summary,
            warning=" | ".join(warnings) if warnings else None,
        )
    )

    return UploadResponse(
        status="ok",
        session_id=session_id,
        summary=summary,
        warning=" | ".join(warnings) if warnings else None,
        pdf_names=pdf_names,
        chunk_count=chunk_count,
    )

