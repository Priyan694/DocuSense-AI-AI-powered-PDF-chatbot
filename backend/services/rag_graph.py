from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from services.llm_service import LLMServiceError, answer_with_context, check_relevance, rewrite_question
from services.schemas import AskRequest, AskResponse, SourceReference
from services.vector_store import retrieve_documents


class GraphState(TypedDict, total=False):
    session_id: str
    question: str
    rewritten_question: str | None
    simple_language: bool
    llm_provider: str
    retrieved: list
    context: str
    relevant: bool
    answer: str
    confidence: float
    weak_context: bool


def _build_context(retrieved: list) -> tuple[str, float]:
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


def retrieve_node(state: GraphState) -> GraphState:
    query = state.get("rewritten_question") or state["question"]
    retrieved = retrieve_documents(state["session_id"], query, top_k=4)
    context, confidence = _build_context(retrieved)
    return {"retrieved": retrieved, "context": context, "confidence": confidence}


async def relevance_node(state: GraphState) -> GraphState:
    if not state["context"].strip():
        return {"relevant": False, "weak_context": True}

    relevant = await check_relevance(state["question"], state["context"])
    weak_context = state["confidence"] < 0.45
    return {"relevant": relevant, "weak_context": weak_context}


async def rewrite_node(state: GraphState) -> GraphState:
    rewritten = await rewrite_question(state["question"])
    return {"rewritten_question": rewritten}


async def answer_node(state: GraphState) -> GraphState:
    if not state["context"].strip() or not state["relevant"]:
        return {
            "answer": "This information is not available in the uploaded PDF.",
        }

    answer = await answer_with_context(
        question=state["question"],
        context=state["context"],
        simple_language=state["simple_language"],
        provider=state["llm_provider"],
    )
    return {"answer": answer}


def route_after_relevance(state: GraphState) -> str:
    if state["relevant"] or state.get("rewritten_question"):
        return "generate_answer"
    return "rewrite"


def route_after_rewrite(_: GraphState) -> str:
    return "retrieve_again"


graph = StateGraph(GraphState)
graph.add_node("retrieve", retrieve_node)
graph.add_node("relevance", relevance_node)
graph.add_node("rewrite", rewrite_node)
graph.add_node("retrieve_again", retrieve_node)
graph.add_node("relevance_again", relevance_node)
graph.add_node("generate_answer", answer_node)
graph.add_edge(START, "retrieve")
graph.add_edge("retrieve", "relevance")
graph.add_conditional_edges(
    "relevance",
    route_after_relevance,
    {"rewrite": "rewrite", "generate_answer": "generate_answer"},
)
graph.add_conditional_edges(
    "rewrite",
    route_after_rewrite,
    {"retrieve_again": "retrieve_again"},
)
graph.add_edge("retrieve_again", "relevance_again")
graph.add_conditional_edges(
    "relevance_again",
    lambda _: "generate_answer",
    {"generate_answer": "generate_answer"},
)
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
    )
