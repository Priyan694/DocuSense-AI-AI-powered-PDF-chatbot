from collections import defaultdict

from langchain_core.documents import Document

from services.llm_service import generate_multi_pdf_comparison
from services.schemas import CompareResponse, SourceReference
from services.session_store import session_manager
from services.vector_store import retrieve_documents


COMPARE_MESSAGE = "Please upload at least one more PDF to compare."


def _keyword_fallback_for_pdf(session_id: str, pdf_id: str, query: str, limit: int = 3) -> list[tuple[Document, float]]:
    session = session_manager.get_session(session_id)
    query_terms = [term for term in query.lower().split() if len(term) > 2]
    scored: list[tuple[Document, float]] = []

    for document in session.chunk_documents:
        if document.metadata.get("pdf_id") != pdf_id:
            continue
        content = document.page_content.lower()
        overlap = sum(1 for term in query_terms if term in content)
        if not overlap:
            continue
        score = round(min(0.9, 0.3 + (overlap / max(len(query_terms), 1)) * 0.55), 3)
        scored.append((document, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:limit]


def _merge_results(
    primary: list[tuple[Document, float]],
    fallback: list[tuple[Document, float]],
    top_k: int,
) -> list[tuple[Document, float]]:
    merged: dict[str, tuple[Document, float]] = {}
    for document, score in [*primary, *fallback]:
        chunk_id = str(document.metadata["chunk_id"])
        existing = merged.get(chunk_id)
        if not existing or score > existing[1]:
            merged[chunk_id] = (document, score)
    ranked = sorted(merged.values(), key=lambda item: item[1], reverse=True)
    return ranked[:top_k]


def build_grouped_compare_context(
    session_id: str,
    compare_instruction: str | None = None,
    top_k_per_pdf: int = 5,
) -> tuple[str, list[SourceReference]]:
    session = session_manager.get_session(session_id)
    compare_query = compare_instruction or "Compare the uploaded PDFs, their topics, concepts, focus areas, strengths, and differences."
    grouped_context_blocks: list[str] = []
    all_sources: list[SourceReference] = []

    for uploaded_pdf in session.uploaded_pdfs:
        primary = retrieve_documents(
            session_id,
            compare_query,
            top_k=top_k_per_pdf,
            metadata_filter={"pdf_id": uploaded_pdf.pdf_id},
        )
        average_score = round(sum(score for _, score in primary) / len(primary), 3) if primary else 0.0
        fallback = _keyword_fallback_for_pdf(
            session_id,
            uploaded_pdf.pdf_id,
            compare_query,
            limit=2,
        ) if len(primary) < top_k_per_pdf or average_score < 0.45 else []
        combined = _merge_results(primary, fallback, top_k_per_pdf)

        pdf_block = [f"PDF: {uploaded_pdf.pdf_name}"]
        for document, score in combined:
            pdf_block.append(
                f"[page {document.metadata['page_number']} - {document.metadata['chunk_id']}]\n{document.page_content}"
            )
            all_sources.append(
                SourceReference(
                    pdf_name=document.metadata["pdf_name"],
                    page_number=document.metadata["page_number"],
                    chunk_id=document.metadata["chunk_id"],
                    relevance_score=round(score, 3),
                )
            )

        grouped_context_blocks.append("\n\n".join(pdf_block))

    return "\n\n".join(grouped_context_blocks), all_sources


async def compare_uploaded_pdfs(
    session_id: str,
    llm_provider: str,
    compare_instruction: str | None = None,
) -> CompareResponse:
    session = session_manager.get_session(session_id)
    uploaded_pdfs = session_manager.list_uploaded_pdfs(session_id)
    if len(uploaded_pdfs) < 2:
        return CompareResponse(
            content=COMPARE_MESSAGE,
            sources=[],
            uploaded_pdf_count=len(uploaded_pdfs),
            uploaded_pdfs=uploaded_pdfs,
        )

    grouped_context, sources = build_grouped_compare_context(
        session_id=session_id,
        compare_instruction=compare_instruction,
        top_k_per_pdf=5,
    )
    content = await generate_multi_pdf_comparison(
        grouped_context=grouped_context,
        provider=llm_provider,
        compare_instruction=compare_instruction,
        pdf_names=[pdf.pdf_name for pdf in session.uploaded_pdfs],
    )
    return CompareResponse(
        content=content,
        sources=sources,
        uploaded_pdf_count=len(uploaded_pdfs),
        uploaded_pdfs=uploaded_pdfs,
    )
