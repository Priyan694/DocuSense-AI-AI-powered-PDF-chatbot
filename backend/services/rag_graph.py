import re
from typing import TypedDict

from langchain_core.documents import Document
from langgraph.graph import END, START, StateGraph

from services.llm_service import (
    LLMServiceError,
    answer_with_context,
    check_relevance,
    detect_intent,
    format_summary_for_chat,
    rewrite_question,
)
from services.compare_service import COMPARE_MESSAGE, compare_uploaded_pdfs
from services.schemas import AskRequest, AskResponse, IntentType, SourceReference
from services.session_store import session_manager
from services.vector_store import retrieve_documents


class GraphState(TypedDict, total=False):
    session_id: str
    question: str
    rewritten_question: str | None
    simple_language: bool
    llm_provider: str
    answer_mode_preference: str
    intent: IntentType
    answer_mode: str
    retrieved: list[tuple[Document, float]]
    context: str
    relevant: bool
    answer: str
    confidence: float
    weak_context: bool
    retrieval_attempts: int


STOPWORDS = {
    "the",
    "and",
    "for",
    "that",
    "with",
    "this",
    "from",
    "what",
    "when",
    "where",
    "which",
    "who",
    "does",
    "about",
    "into",
    "your",
    "their",
    "there",
    "have",
    "would",
    "could",
    "should",
}


def _build_context(retrieved: list[tuple[Document, float]]) -> tuple[str, float]:
    blocks: list[str] = []
    scores: list[float] = []
    for document, score in retrieved:
        blocks.append(
            f"[{document.metadata['pdf_name']} - page {document.metadata['page_number']} - {document.metadata['chunk_id']}]\n"
            f"{document.page_content}"
        )
        scores.append(score)
    confidence = round(sum(scores) / len(scores), 3) if scores else 0.0
    return "\n\n".join(blocks), confidence


def _tokenize(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower())
        if token not in STOPWORDS
    ]


def _keyword_fallback_search(session_id: str, query: str, limit: int = 3) -> list[tuple[Document, float]]:
    session = session_manager.get_session(session_id)
    query_terms = _tokenize(query)
    if not query_terms:
        return []

    scored: list[tuple[Document, float]] = []
    for document in session.chunk_documents:
        content = document.page_content.lower()
        overlap = sum(1 for term in query_terms if term in content)
        if not overlap:
            continue
        density = overlap / max(len(query_terms), 1)
        score = round(min(0.92, 0.25 + density * 0.6), 3)
        scored.append((document, score))

    scored.sort(
        key=lambda item: (
            item[1],
            -int(item[0].metadata.get("page_number", 0)),
        ),
        reverse=True,
    )
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

    ranked = sorted(
        merged.values(),
        key=lambda item: item[1],
        reverse=True,
    )
    return ranked[:top_k]


async def detect_intent_node(state: GraphState) -> GraphState:
    intent = await detect_intent(state["question"])
    preference = state.get("answer_mode_preference", "auto")
    if preference in {"strict_pdf", "explanation"}:
        answer_mode = preference
    else:
        answer_mode = "strict_pdf" if intent == "strict_pdf" else "explanation"
    return {"intent": intent, "answer_mode": answer_mode, "retrieval_attempts": 0}


def summary_response_node(state: GraphState) -> GraphState:
    session = session_manager.get_session(state["session_id"])
    if session.summary_details:
        answer = format_summary_for_chat(session.summary_details)
    else:
        answer = session.summary
    return {"answer": answer, "confidence": 1.0, "weak_context": False}


async def compare_response_node(state: GraphState) -> GraphState:
    session = session_manager.get_session(state["session_id"])
    if len(session.uploaded_pdfs) < 2:
        return {
            "answer": COMPARE_MESSAGE,
            "confidence": 1.0,
            "weak_context": False,
            "retrieved": [],
        }

    result = await compare_uploaded_pdfs(
        session_id=state["session_id"],
        llm_provider=state["llm_provider"],
        compare_instruction=state["question"],
    )
    retrieved = []
    for source in result.sources:
        for document in session.chunk_documents:
            if document.metadata.get("chunk_id") == source.chunk_id:
                retrieved.append((document, source.relevance_score or 0.0))
                break
    return {
        "answer": result.content,
        "confidence": 1.0,
        "weak_context": False,
        "retrieved": retrieved,
    }


def retrieve_node(state: GraphState) -> GraphState:
    query = state.get("rewritten_question") or state["question"]
    vector_results = retrieve_documents(state["session_id"], query, top_k=5)
    average_vector_score = round(
        sum(score for _, score in vector_results) / len(vector_results), 3
    ) if vector_results else 0.0
    should_fallback = len(vector_results) < 5 or average_vector_score < 0.45
    fallback_results = _keyword_fallback_search(state["session_id"], query, limit=3) if should_fallback else []
    retrieved = _merge_results(vector_results, fallback_results, top_k=7)
    context, confidence = _build_context(retrieved)
    return {
        "retrieved": retrieved,
        "context": context,
        "confidence": confidence,
        "retrieval_attempts": state.get("retrieval_attempts", 0) + 1,
    }


async def relevance_node(state: GraphState) -> GraphState:
    if not state["context"].strip():
        return {"relevant": False, "weak_context": True}

    relevant = await check_relevance(state["question"], state["context"])
    weak_context = state["confidence"] < 0.42 or len(state.get("retrieved", [])) < 2
    return {"relevant": relevant, "weak_context": weak_context}


async def rewrite_node(state: GraphState) -> GraphState:
    rewritten = await rewrite_question(state["question"])
    return {"rewritten_question": rewritten}


async def answer_node(state: GraphState) -> GraphState:
    strict_mode = state["answer_mode"] == "strict_pdf"
    if strict_mode and (not state["context"].strip() or not state["relevant"]):
        return {"answer": "This information is not available in the uploaded PDF."}

    answer = await answer_with_context(
        question=state["question"],
        context=state.get("context", ""),
        simple_language=state["simple_language"],
        provider=state["llm_provider"],
        intent=state["intent"],
        strict_mode=strict_mode,
    )
    return {"answer": answer}


def route_after_intent(state: GraphState) -> str:
    if state.get("answer_mode_preference", "auto") == "auto" and state["intent"] == "summary":
        return "summary_response"
    if state["intent"] == "comparison":
        return "compare_response"
    return "retrieve"


def route_after_relevance(state: GraphState) -> str:
    if state["relevant"]:
        return "generate_answer"
    if state.get("retrieval_attempts", 0) >= 2:
        return "generate_answer"
    return "rewrite"


graph = StateGraph(GraphState)
graph.add_node("detect_intent", detect_intent_node)
graph.add_node("summary_response", summary_response_node)
graph.add_node("compare_response", compare_response_node)
graph.add_node("retrieve", retrieve_node)
graph.add_node("relevance", relevance_node)
graph.add_node("rewrite", rewrite_node)
graph.add_node("generate_answer", answer_node)
graph.add_edge(START, "detect_intent")
graph.add_conditional_edges(
    "detect_intent",
    route_after_intent,
    {
        "summary_response": "summary_response",
        "compare_response": "compare_response",
        "retrieve": "retrieve",
    },
)
graph.add_edge("summary_response", END)
graph.add_edge("compare_response", END)
graph.add_edge("retrieve", "relevance")
graph.add_conditional_edges(
    "relevance",
    route_after_relevance,
    {"rewrite": "rewrite", "generate_answer": "generate_answer"},
)
graph.add_edge("rewrite", "retrieve")
graph.add_edge("generate_answer", END)
compiled_graph = graph.compile()


async def run_rag_query(payload: AskRequest) -> AskResponse:
    try:
        state = await compiled_graph.ainvoke(
            {
                "session_id": payload.session_id,
                "question": payload.question,
                "simple_language": payload.simple_language,
                "llm_provider": payload.llm_provider,
                "answer_mode_preference": payload.answer_mode_preference,
                "rewritten_question": None,
            }
        )
    except LLMServiceError as exc:
        raise RuntimeError(str(exc)) from exc

    sources = [
        SourceReference(
            pdf_name=doc.metadata["pdf_name"],
            page_number=doc.metadata["page_number"],
            chunk_id=doc.metadata["chunk_id"],
            relevance_score=round(score, 3),
        )
        for doc, score in state.get("retrieved", [])
    ]

    return AskResponse(
        answer=state["answer"],
        sources=sources,
        confidence=state.get("confidence", 0.0),
        weak_context=state.get("weak_context", False),
        rewritten_question=state.get("rewritten_question"),
        intent=state.get("intent", "unknown"),
        answer_mode=state.get("answer_mode", "strict_pdf"),
    )
