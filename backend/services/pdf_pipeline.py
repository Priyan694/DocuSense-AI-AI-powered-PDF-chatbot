import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from langchain_core.documents import Document

from services.chunker import split_documents
from services.config import BASE_DIR, settings
from services.llm_service import LLMServiceError, generate_rich_summary
from services.pdf_processor import extract_documents_from_pdf
from services.schemas import UploadResponse
from services.session_store import SessionData, UploadedPDFRecord, session_manager
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


async def process_uploaded_pdfs(
    files: list[UploadFile],
    llm_provider: str,
    session_id: str | None = None,
) -> UploadResponse:
    existing_session = (
        session_manager.get_session(session_id)
        if session_id and session_manager.has_session(session_id)
        else None
    )
    session_id = existing_session.session_id if existing_session else uuid.uuid4().hex
    new_documents: list[Document] = []
    warnings: list[str] = list(existing_session.warning.split(" | ")) if existing_session and existing_session.warning else []
    uploaded_records = list(existing_session.uploaded_pdfs) if existing_session else []

    for upload in files:
        file_path = await _save_upload(upload)
        pdf_name = upload.filename or file_path.name
        pdf_id = uuid.uuid4().hex
        documents, warning = extract_documents_from_pdf(file_path, pdf_name)
        if warning:
            warnings.append(f"{pdf_name}: {warning}")
        for document in documents:
            document.metadata["pdf_id"] = pdf_id
        new_documents.extend(documents)
        file_path.unlink(missing_ok=True)

        uploaded_records.append(
            UploadedPDFRecord(
                pdf_id=pdf_id,
                pdf_name=pdf_name,
            )
        )

    if not new_documents:
        raise HTTPException(status_code=400, detail="No readable text found in the uploaded PDFs.")

    chunked_docs = split_documents(new_documents)
    existing_chunk_count = len(existing_session.chunk_documents) if existing_session else 0
    for index, doc in enumerate(chunked_docs, start=1):
        pdf_id = doc.metadata["pdf_id"]
        doc.metadata["chunk_id"] = f"{pdf_id}-chunk-{existing_chunk_count + index}"

    chunk_count = index_documents(session_id, chunked_docs)
    chunk_count_total = existing_chunk_count + chunk_count

    for record in uploaded_records:
        record.chunk_count = sum(1 for doc in chunked_docs if doc.metadata["pdf_id"] == record.pdf_id) + (
            record.chunk_count if existing_session and any(existing.pdf_id == record.pdf_id for existing in existing_session.uploaded_pdfs) else 0
        )

    all_session_documents = [
        *(existing_session.chunk_documents if existing_session else []),
        *chunked_docs,
    ]
    pdf_names = [record.pdf_name for record in uploaded_records]
    combined_context = "\n\n".join(
        f"[{doc.metadata['pdf_name']} - page {doc.metadata['page_number']}]\n{doc.page_content}"
        for doc in all_session_documents[:24]
    )[:22000]

    try:
        summary_details = await generate_rich_summary(combined_context, llm_provider)
    except LLMServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    summary = summary_details.overall_summary

    session_manager.create_session(
        SessionData(
            session_id=session_id,
            pdf_names=pdf_names,
            summary=summary,
            uploaded_pdfs=uploaded_records,
            summary_details=summary_details,
            key_concepts=summary_details.key_concepts,
            chunk_documents=all_session_documents,
            warning=" | ".join(warnings) if warnings else None,
        )
    )

    return UploadResponse(
        status="ok",
        session_id=session_id,
        summary=summary,
        summary_details=summary_details,
        key_concepts=summary_details.key_concepts,
        warning=" | ".join(warnings) if warnings else None,
        pdf_names=pdf_names,
        uploaded_pdfs=session_manager.list_uploaded_pdfs(session_id),
        uploaded_pdf_count=len(uploaded_records),
        chunk_count=chunk_count_total,
    )
