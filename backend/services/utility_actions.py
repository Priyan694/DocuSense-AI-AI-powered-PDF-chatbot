from services.compare_service import compare_uploaded_pdfs
from services.llm_service import generate_action_content
from services.schemas import ActionRequest, ActionResponse, SourceReference
from services.vector_store import retrieve_documents


async def run_pdf_action(payload: ActionRequest) -> ActionResponse:
    if payload.action == "compare":
        result = await compare_uploaded_pdfs(
            session_id=payload.session_id,
            llm_provider=payload.llm_provider,
            compare_instruction=payload.compare_instruction,
        )
        return ActionResponse(
            action=payload.action,
            content=result.content,
            sources=result.sources,
        )

    query_map = {
        "simple_explain": "Explain the main idea of this PDF in simple language.",
        "key_points": "List the main key points from this PDF.",
        "mcqs": "Generate 10 MCQs from this PDF.",
        "flashcards": "Create flashcards from this PDF.",
        "rewrite": "Rewrite the PDF into better study notes.",
    }

    retrieved = retrieve_documents(payload.session_id, query_map[payload.action], top_k=7)
    context = "\n\n".join(
        f"[{doc.metadata['pdf_name']} - page {doc.metadata['page_number']}]\n{doc.page_content}"
        for doc, _ in retrieved
    )
    content = await generate_action_content(
        action=payload.action,
        context=context,
        provider=payload.llm_provider,
        extra_instruction=payload.compare_instruction,
    )

    return ActionResponse(
        action=payload.action,
        content=content,
        sources=[
            SourceReference(
                pdf_name=doc.metadata["pdf_name"],
                page_number=doc.metadata["page_number"],
                chunk_id=doc.metadata["chunk_id"],
                relevance_score=round(score, 3),
            )
            for doc, score in retrieved
        ],
    )
