"""
Standalone DocuSense AI runner.

This script mirrors the standalone notebook flow in a server-friendly Python file.
It can:
- create temporary sample PDFs if none are provided
- index one or more PDFs into a temporary ChromaDB
- generate a rich summary
- answer strict and explanation-style questions
- compare multiple PDFs
- print CPU utilization metrics for the run

Usage:
    python main_server.py
    python main_server.py --provider groq
    python main_server.py --pdf Testing/"Research paper - Ai.pdf" --pdf Testing/"Reseacrh paper - cloud.pdf"
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import time
import uuid
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional, TypedDict, Union

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import fitz
import httpx
from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langgraph.graph import END, START, StateGraph

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except Exception:  # pragma: no cover - graceful fallback if package/model is unavailable
    HuggingFaceEmbeddings = None

try:
    import psutil
except Exception:  # pragma: no cover - optional dependency
    psutil = None

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / "backend" / ".env")
load_dotenv(PROJECT_ROOT / ".env")

logging.getLogger("chromadb").setLevel(logging.ERROR)
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)
logging.getLogger("chromadb.telemetry.product").setLevel(logging.CRITICAL)
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)
logging.getLogger("posthog").setLevel(logging.CRITICAL)
warnings.filterwarnings(
    "ignore",
    message=r"Number of requested results .* updating n_results",
)

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_MODEL = os.getenv("MINIMAX_MODEL", "minimax-text-01")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.chat/v1")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-nano")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
VECTOR_ROOT = Path(tempfile.mkdtemp(prefix="docu_sense_server_"))
SAMPLE_DIR = VECTOR_ROOT / "sample_pdfs"
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

Provider = Literal["minimax", "groq", "openai"]
IntentType = Literal["strict_pdf", "explanation", "summary", "comparison", "example", "unknown"]
AnswerModePreference = Literal["auto", "strict_pdf", "explanation"]

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
}


@dataclass
class UploadedPDFRecord:
    pdf_id: str
    pdf_name: str
    chunk_count: int = 0


@dataclass
class NotebookSession:
    session_id: str
    summary: str = ""
    summary_details: dict[str, Any] = field(default_factory=dict)
    key_concepts: list[str] = field(default_factory=list)
    uploaded_pdfs: list[UploadedPDFRecord] = field(default_factory=list)
    chunk_documents: list[Document] = field(default_factory=list)
    warning: Optional[str] = None


@dataclass
class RunMetrics:
    wall_seconds: float
    cpu_seconds: float
    cpu_percent_single_core: float
    cpu_count: int
    load_average: Optional[tuple[float, float, float]]


class HashEmbeddings:
    """Deterministic local fallback embeddings that require no model download."""

    def __init__(self, dimension: int = 256) -> None:
        self.dimension = dimension

    def _encode(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = re.findall(r"[a-zA-Z0-9_-]+", text.lower())
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for index in range(0, min(len(digest), self.dimension // 8)):
                bucket = (digest[index] + index * 31) % self.dimension
                sign = 1.0 if digest[-(index + 1)] % 2 == 0 else -1.0
                vector[bucket] += sign
        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._encode(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._encode(text)


SESSIONS: dict[str, NotebookSession] = {}
_EMBEDDINGS: Any = None


def get_embeddings() -> Any:
    global _EMBEDDINGS
    if _EMBEDDINGS is not None:
        return _EMBEDDINGS

    force_hash = os.getenv("DOCUSENSE_FORCE_HASH_EMBEDDINGS", "0") == "1"
    allow_download = os.getenv("DOCUSENSE_ALLOW_MODEL_DOWNLOAD", "0") == "1"
    if not force_hash and HuggingFaceEmbeddings is not None:
        try:
            model_kwargs = {}
            if not allow_download:
                model_kwargs["local_files_only"] = True
            _EMBEDDINGS = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL,
                model_kwargs=model_kwargs,
            )
            print(f"Using HuggingFace embeddings: {EMBEDDING_MODEL}")
            return _EMBEDDINGS
        except Exception as exc:
            print(f"Falling back to local hash embeddings because HuggingFace embeddings failed: {exc}")

    _EMBEDDINGS = HashEmbeddings()
    print("Using local hash embeddings fallback.")
    return _EMBEDDINGS


def provider_config(provider: Provider) -> tuple[str, str, str]:
    configs = {
        "minimax": (MINIMAX_BASE_URL, MINIMAX_API_KEY, MINIMAX_MODEL),
        "groq": (GROQ_BASE_URL, GROQ_API_KEY, GROQ_MODEL),
        "openai": (OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL),
    }
    return configs[provider]


def provider_available(provider: Provider) -> bool:
    _, api_key, _ = provider_config(provider)
    return bool(api_key)


def get_store(session_id: str) -> Chroma:
    persist_dir = VECTOR_ROOT / session_id
    persist_dir.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=f"docu_sense_session_{session_id}",
        persist_directory=str(persist_dir),
        embedding_function=get_embeddings(),
    )


def clean_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_documents_from_pdf(file_path: Path, pdf_name: str, pdf_id: str) -> list[Document]:
    documents: list[Document] = []
    with fitz.open(file_path) as pdf:
        for page_number, page in enumerate(pdf, start=1):
            text = clean_text(page.get_text("text"))
            if len(text) < 30:
                continue
            documents.append(
                Document(
                    page_content=text,
                    metadata={
                        "pdf_id": pdf_id,
                        "pdf_name": pdf_name,
                        "page_number": page_number,
                    },
                )
            )
    return documents


def split_documents(documents: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(documents)


def tokenize(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower())
        if token not in STOPWORDS
    ]


def extract_json_block(raw_text: str) -> Optional[dict[str, Any]]:
    fenced_match = re.search(r"```json\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if fenced_match:
        try:
            return json.loads(fenced_match.group(1))
        except json.JSONDecodeError:
            return None
    object_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if object_match:
        try:
            return json.loads(object_match.group(0))
        except json.JSONDecodeError:
            return None
    return None


async def chat_completion(
    provider: Provider,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
) -> str:
    base_url, api_key, model = provider_config(provider)
    if not api_key:
        raise RuntimeError(f"No API key configured for {provider}.")

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
            },
        )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def mock_summary(context: str) -> dict[str, Any]:
    lines = [line.strip() for line in context.splitlines() if line.strip() and not line.startswith("[")]
    key_concepts: list[str] = []
    for token in re.findall(r"\b[A-Z][a-zA-Z-]{3,}\b", context):
        if token not in key_concepts:
            key_concepts.append(token)
    key_concepts = key_concepts[:6] or ["Document understanding", "RAG", "Embeddings"]
    return {
        "overall_summary": " ".join(lines[:3]) or "Mock summary generated from sample PDF content.",
        "main_objective": lines[0] if lines else "Explain the main topic covered in the uploaded PDFs.",
        "key_concepts": key_concepts,
        "important_terms": [
            {"term": concept, "explanation": f"Important concept related to {concept}."}
            for concept in key_concepts[:4]
        ],
        "missing_but_important_terms": [
            {
                "term": "Semantic search",
                "explanation": "Often needed to understand RAG-based QA.",
            }
        ],
        "additional_general_explanation": "This is a mock educational explanation because no live LLM key is configured.",
        "final_takeaway": "The uploaded PDFs can be indexed and queried in a session-based RAG workflow.",
    }


def mock_strict_answer(question: str, context: str) -> str:
    question_terms = tokenize(question)
    best_line = ""
    best_score = 0
    for line in context.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("[") or stripped.startswith("PDF:"):
            continue
        score = sum(1 for token in question_terms if token in line.lower())
        if score > best_score:
            best_score = score
            best_line = stripped
    return best_line or "This information is not available in the uploaded PDF."


def mock_explanation_answer(question: str, context: str) -> str:
    strict = mock_strict_answer(question, context)
    return (
        f"What the PDF says\n{strict}\n\n"
        "Additional explanation\nThis is a mock explanation generated locally without a live LLM key.\n\n"
        "Simple example\nImagine a user uploads notes, stores chunks in Chroma, and asks questions against retrieved context."
    )


def mock_compare_answer(grouped_context: str, uploaded_pdfs: list[UploadedPDFRecord]) -> str:
    overview_lines = "\n".join(
        f"- {pdf.pdf_name}: representative context retrieved for comparison."
        for pdf in uploaded_pdfs
    )
    return (
        f"Overview of each PDF\n{overview_lines}\n\n"
        "Similarities\n- The PDFs share overlapping topics based on the retrieved chunks.\n\n"
        "Differences\n- Each PDF emphasizes different sections or examples.\n\n"
        "Key concepts compared\n- Core concepts were grouped per PDF before comparison.\n\n"
        "Strengths / focus area of each PDF\n- Each document contributes its own focus area from retrieved context.\n\n"
        "Final conclusion\n- This is a local mock comparison. Add API keys to generate a richer LLM comparison."
    )


async def rich_summary_from_context(context: str, provider: Provider) -> dict[str, Any]:
    if not provider_available(provider):
        return mock_summary(context)
    prompt = (
        "Create a rich educational summary from the PDF context. Return valid JSON with keys: "
        "overall_summary, main_objective, key_concepts, important_terms, missing_but_important_terms, "
        "additional_general_explanation, final_takeaway. For term lists, use objects with term and explanation.\n\n"
        f"PDF Context:\n{context[:18000]}"
    )
    raw = await chat_completion(provider, "You create educational PDF summaries.", prompt, temperature=0.5)
    payload = extract_json_block(raw)
    return payload or mock_summary(context)


async def answer_with_context(question: str, context: str, provider: Provider, mode: str) -> str:
    if not provider_available(provider):
        return mock_strict_answer(question, context) if mode == "strict_pdf" else mock_explanation_answer(question, context)
    if mode == "strict_pdf":
        system_prompt = (
            "Answer using only the provided PDF context. If the answer is not present, say exactly: "
            "'This information is not available in the uploaded PDF.'"
        )
        return await chat_completion(
            provider,
            system_prompt,
            f"Question: {question}\n\nPDF Context:\n{context}",
            temperature=0.2,
        )
    system_prompt = (
        "Use the PDF context as the primary source. You may add concise general knowledge only when helpful, "
        "but clearly separate it from the PDF."
    )
    prompt = (
        "Format the answer with these exact headings:\nWhat the PDF says\nAdditional explanation\nSimple example\n\n"
        f"Question: {question}\n\nPDF Context:\n{context or 'No strong PDF context was retrieved.'}"
    )
    return await chat_completion(provider, system_prompt, prompt, temperature=0.5)


def classify_intent(question: str) -> IntentType:
    lowered = question.lower().strip()
    if any(term in lowered for term in ("summary", "summarize", "overview", "recap")):
        return "summary"
    if any(term in lowered for term in ("compare", "difference", "advantages", "disadvantages", "vs", "versus")):
        return "comparison"
    if any(term in lowered for term in ("example", "sample", "use case")):
        return "example"
    if any(term in lowered for term in ("explain", "why", "how", "meaning", "importance", "define")):
        return "explanation"
    if any(term in lowered for term in ("what does", "which", "when", "who", "according to")):
        return "strict_pdf"
    return "unknown"


def build_context(results: list[tuple[Document, float]]) -> tuple[str, float]:
    blocks: list[str] = []
    scores: list[float] = []
    for document, score in results:
        blocks.append(
            f"[{document.metadata['pdf_name']} - page {document.metadata['page_number']} - {document.metadata['chunk_id']}]\n"
            f"{document.page_content}"
        )
        scores.append(score)
    return "\n\n".join(blocks), round(sum(scores) / len(scores), 3) if scores else 0.0


def keyword_fallback(
    session_id: str,
    query: str,
    pdf_id: Optional[str] = None,
    limit: int = 3,
) -> list[tuple[Document, float]]:
    session = SESSIONS[session_id]
    query_terms = tokenize(query)
    scored: list[tuple[Document, float]] = []
    for doc in session.chunk_documents:
        if pdf_id and doc.metadata.get("pdf_id") != pdf_id:
            continue
        overlap = sum(1 for token in query_terms if token in doc.page_content.lower())
        if overlap:
            score = round(min(0.92, 0.25 + (overlap / max(len(query_terms), 1)) * 0.6), 3)
            scored.append((doc, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:limit]


def merge_results(
    primary: list[tuple[Document, float]],
    fallback: list[tuple[Document, float]],
    top_k: int = 7,
) -> list[tuple[Document, float]]:
    merged: dict[str, tuple[Document, float]] = {}
    for doc, score in [*primary, *fallback]:
        chunk_id = doc.metadata["chunk_id"]
        if chunk_id not in merged or score > merged[chunk_id][1]:
            merged[chunk_id] = (doc, score)
    return sorted(merged.values(), key=lambda item: item[1], reverse=True)[:top_k]


def distance_to_relevance(distance: float) -> float:
    safe_distance = max(distance, 0.0)
    return round(1.0 / (1.0 + safe_distance), 3)


def vector_search(
    store: Chroma,
    query: str,
    limit: int,
    metadata_filter: Optional[dict[str, Any]] = None,
) -> list[tuple[Document, float]]:
    search_kwargs: dict[str, Any] = {"k": max(1, limit)}
    if metadata_filter:
        search_kwargs["filter"] = metadata_filter
    raw_results = store.similarity_search_with_score(query, **search_kwargs)
    return [(doc, distance_to_relevance(distance)) for doc, distance in raw_results]


def retrieve(session_id: str, query: str, top_k: int = 5) -> list[tuple[Document, float]]:
    store = get_store(session_id)
    session = SESSIONS[session_id]
    limit = min(top_k, max(1, len(session.chunk_documents)))
    primary = vector_search(store, query, limit=limit)
    avg_score = round(sum(score for _, score in primary) / len(primary), 3) if primary else 0.0
    fallback = keyword_fallback(session_id, query, limit=3) if len(primary) < top_k or avg_score < 0.45 else []
    return merge_results(primary, fallback, top_k=7)


async def compare_pdfs(
    session_id: str,
    provider: Provider = "groq",
    compare_instruction: Optional[str] = None,
) -> dict[str, Any]:
    session = SESSIONS[session_id]
    if len(session.uploaded_pdfs) < 2:
        return {"content": "Please upload at least one more PDF to compare.", "sources": []}
    query = compare_instruction or "Compare the uploaded PDFs, their focus, concepts, differences, and strengths."
    grouped_blocks: list[str] = []
    sources: list[dict[str, Any]] = []
    store = get_store(session_id)
    for pdf in session.uploaded_pdfs:
        limit = min(5, max(1, pdf.chunk_count))
        primary = vector_search(store, query, limit=limit, metadata_filter={"pdf_id": pdf.pdf_id})
        avg_score = round(sum(score for _, score in primary) / len(primary), 3) if primary else 0.0
        fallback = (
            keyword_fallback(session_id, query, pdf_id=pdf.pdf_id, limit=2)
            if len(primary) < 5 or avg_score < 0.45
            else []
        )
        combined = merge_results(primary, fallback, top_k=5)
        chunk_texts = [f"PDF: {pdf.pdf_name}"]
        for doc, score in combined:
            chunk_texts.append(
                f"[page {doc.metadata['page_number']} - {doc.metadata['chunk_id']}]\n{doc.page_content}"
            )
            sources.append(
                {
                    "pdf_name": doc.metadata["pdf_name"],
                    "page_number": doc.metadata["page_number"],
                    "chunk_id": doc.metadata["chunk_id"],
                    "relevance_score": round(score, 3),
                }
            )
        grouped_blocks.append("\n\n".join(chunk_texts))
    grouped_context = "\n\n".join(grouped_blocks)
    if not provider_available(provider):
        return {"content": mock_compare_answer(grouped_context, session.uploaded_pdfs), "sources": sources}
    prompt = (
        "You are comparing multiple uploaded PDFs. Use the grouped context from each PDF. "
        "Structure the answer with these headings exactly:\nOverview of each PDF\nSimilarities\nDifferences\n"
        "Key concepts compared\nStrengths / focus area of each PDF\nFinal conclusion\n\n"
        f"Grouped PDF context:\n{grouped_context[:22000]}"
    )
    content = await chat_completion(
        provider,
        "Compare the PDFs using only the grouped context unless additional explanation is clearly labeled.",
        prompt,
        temperature=0.5,
    )
    return {"content": content, "sources": sources}


def make_sample_pdf(path: Path, title: str, sections: list[str]) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    text = title + "\n\n" + "\n\n".join(sections)
    page.insert_textbox(fitz.Rect(40, 40, 550, 780), text, fontsize=11)
    doc.save(path)
    doc.close()
    return path


def create_sample_pdfs() -> list[Path]:
    pdf_a = make_sample_pdf(
        SAMPLE_DIR / "RAG_Basics.pdf",
        "RAG Basics",
        [
            "Retrieval-Augmented Generation combines retrieval with language generation to ground answers in external knowledge.",
            "A typical pipeline loads documents, splits them into chunks, creates embeddings, stores vectors, retrieves relevant chunks, and asks the model to answer from context.",
            "RAG reduces hallucination compared with unconstrained generation by exposing the model to source text during inference.",
        ],
    )
    pdf_b = make_sample_pdf(
        SAMPLE_DIR / "Vector_Databases.pdf",
        "Vector Databases",
        [
            "Vector databases store embeddings for semantic search and similarity-based retrieval.",
            "Metadata such as document name and page number helps trace answers back to the original source.",
            "A vector database improves retrieval speed, filtering, and grouping across large document collections.",
        ],
    )
    return [pdf_a, pdf_b]


async def upload_pdfs(
    paths: list[Union[str, Path]],
    provider: Provider = "groq",
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    session_id = session_id or uuid.uuid4().hex
    session = SESSIONS.get(session_id, NotebookSession(session_id=session_id))
    new_documents: list[Document] = []
    for raw_path in paths:
        path = Path(raw_path)
        pdf_id = uuid.uuid4().hex
        docs = extract_documents_from_pdf(path, path.name, pdf_id)
        if not docs:
            continue
        session.uploaded_pdfs.append(UploadedPDFRecord(pdf_id=pdf_id, pdf_name=path.name))
        new_documents.extend(docs)
    if not new_documents:
        raise ValueError("No readable text found in the uploaded PDFs.")
    chunked_docs = split_documents(new_documents)
    existing_count = len(session.chunk_documents)
    for index, doc in enumerate(chunked_docs, start=1):
        doc.metadata["chunk_id"] = f"{doc.metadata['pdf_id']}-chunk-{existing_count + index}"
    store = get_store(session_id)
    store.add_documents(chunked_docs, ids=[doc.metadata["chunk_id"] for doc in chunked_docs])
    session.chunk_documents.extend(chunked_docs)
    for record in session.uploaded_pdfs:
        record.chunk_count = sum(
            1 for doc in session.chunk_documents if doc.metadata["pdf_id"] == record.pdf_id
        )
    combined_context = "\n\n".join(
        f"[{doc.metadata['pdf_name']} - page {doc.metadata['page_number']}]\n{doc.page_content}"
        for doc in session.chunk_documents[:24]
    )[:22000]
    session.summary_details = await rich_summary_from_context(combined_context, provider)
    session.summary = session.summary_details.get("overall_summary", "")
    session.key_concepts = session.summary_details.get("key_concepts", [])
    SESSIONS[session_id] = session
    return {
        "session_id": session_id,
        "summary": session.summary,
        "summary_details": session.summary_details,
        "uploaded_pdfs": [
            {"pdf_id": pdf.pdf_id, "pdf_name": pdf.pdf_name, "chunk_count": pdf.chunk_count}
            for pdf in session.uploaded_pdfs
        ],
        "uploaded_pdf_count": len(session.uploaded_pdfs),
        "chunk_count": len(session.chunk_documents),
    }


class GraphState(TypedDict, total=False):
    session_id: str
    question: str
    llm_provider: Provider
    answer_mode_preference: AnswerModePreference
    intent: IntentType
    answer_mode: str
    retrieved: list[tuple[Document, float]]
    context: str
    answer: str


def detect_intent_node(state: GraphState) -> GraphState:
    intent = classify_intent(state["question"])
    preference = state.get("answer_mode_preference", "auto")
    answer_mode = (
        preference
        if preference in {"strict_pdf", "explanation"}
        else ("strict_pdf" if intent == "strict_pdf" else "explanation")
    )
    return {"intent": intent, "answer_mode": answer_mode}


def route_after_intent(state: GraphState) -> str:
    if state.get("answer_mode_preference", "auto") == "auto" and state["intent"] == "summary":
        return "summary_response"
    if state["intent"] == "comparison":
        return "compare_response"
    return "retrieve"


def summary_response_node(state: GraphState) -> GraphState:
    session = SESSIONS[state["session_id"]]
    details = session.summary_details
    answer = (
        f"Overall summary\n{details.get('overall_summary', '')}\n\n"
        f"Main objective\n{details.get('main_objective', '')}\n\n"
        f"Key concepts\n- " + "\n- ".join(details.get("key_concepts", [])) + "\n\n"
        f"Final takeaway\n{details.get('final_takeaway', '')}"
    )
    return {"answer": answer}


async def compare_response_node(state: GraphState) -> GraphState:
    result = await compare_pdfs(
        state["session_id"],
        provider=state["llm_provider"],
        compare_instruction=state["question"],
    )
    return {"answer": result["content"]}


def retrieve_node(state: GraphState) -> GraphState:
    results = retrieve(state["session_id"], state["question"], top_k=5)
    context, _ = build_context(results)
    return {"retrieved": results, "context": context}


async def answer_node(state: GraphState) -> GraphState:
    answer = await answer_with_context(
        state["question"],
        state.get("context", ""),
        state["llm_provider"],
        state["answer_mode"],
    )
    return {"answer": answer}


graph = StateGraph(GraphState)
graph.add_node("detect_intent", detect_intent_node)
graph.add_node("summary_response", summary_response_node)
graph.add_node("compare_response", compare_response_node)
graph.add_node("retrieve", retrieve_node)
graph.add_node("answer_response", answer_node)
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
graph.add_edge("retrieve", "answer_response")
graph.add_edge("answer_response", END)
compiled_graph = graph.compile()


async def ask_pdf(
    session_id: str,
    question: str,
    provider: Provider = "groq",
    answer_mode_preference: AnswerModePreference = "auto",
) -> dict[str, Any]:
    state = await compiled_graph.ainvoke(
        {
            "session_id": session_id,
            "question": question,
            "llm_provider": provider,
            "answer_mode_preference": answer_mode_preference,
        }
    )
    return state


def list_uploaded_pdfs(session_id: str) -> list[dict[str, Any]]:
    session = SESSIONS[session_id]
    return [
        {"pdf_id": pdf.pdf_id, "pdf_name": pdf.pdf_name, "chunk_count": pdf.chunk_count}
        for pdf in session.uploaded_pdfs
    ]


def reset_session(session_id: str) -> None:
    SESSIONS.pop(session_id, None)
    session_dir = VECTOR_ROOT / session_id
    if session_dir.exists():
        shutil.rmtree(session_dir, ignore_errors=True)


def capture_metrics(start_wall: float, start_cpu: float) -> RunMetrics:
    wall_seconds = max(time.perf_counter() - start_wall, 1e-9)
    cpu_seconds = max(time.process_time() - start_cpu, 0.0)
    cpu_count = os.cpu_count() or 1
    cpu_percent_single_core = round((cpu_seconds / wall_seconds) * 100, 2)
    load_average = None
    if hasattr(os, "getloadavg"):
        try:
            load_average = tuple(round(value, 2) for value in os.getloadavg())
        except OSError:
            load_average = None
    return RunMetrics(
        wall_seconds=round(wall_seconds, 3),
        cpu_seconds=round(cpu_seconds, 3),
        cpu_percent_single_core=cpu_percent_single_core,
        cpu_count=cpu_count,
        load_average=load_average,
    )


def print_section(title: str, body: str) -> None:
    print(f"\n{'=' * 16} {title} {'=' * 16}")
    print(body.strip() if body.strip() else "(empty)")


def format_summary(details: dict[str, Any]) -> str:
    important_terms = "\n".join(
        f"- {item['term']}: {item['explanation']}" for item in details.get("important_terms", [])
    ) or "- None"
    missing_terms = "\n".join(
        f"- {item['term']}: {item['explanation']}"
        for item in details.get("missing_but_important_terms", [])
    ) or "- None"
    key_concepts = "\n".join(f"- {item}" for item in details.get("key_concepts", [])) or "- None"
    return (
        f"Overall summary\n{details.get('overall_summary', '')}\n\n"
        f"Main objective\n{details.get('main_objective', '')}\n\n"
        f"Key concepts\n{key_concepts}\n\n"
        f"Important terms\n{important_terms}\n\n"
        f"Terms not clearly explained in the PDF but important\n{missing_terms}\n\n"
        f"Additional general explanation\n{details.get('additional_general_explanation', '')}\n\n"
        f"Final takeaway\n{details.get('final_takeaway', '')}"
    )


def format_sources(results: list[tuple[Document, float]]) -> str:
    if not results:
        return "No sources returned."
    lines = []
    for doc, score in results:
        lines.append(
            f"- {doc.metadata['pdf_name']} | page {doc.metadata['page_number']} | "
            f"{doc.metadata['chunk_id']} | score={round(score, 3)}"
        )
    return "\n".join(lines)


def format_compare_sources(sources: list[dict[str, Any]]) -> str:
    if not sources:
        return "No compare sources returned."
    lines = []
    for item in sources:
        lines.append(
            f"- {item['pdf_name']} | page {item['page_number']} | "
            f"{item['chunk_id']} | score={item['relevance_score']}"
        )
    return "\n".join(lines)


def resolve_pdf_paths(pdf_args: list[str]) -> list[Path]:
    if pdf_args:
        return [Path(item).expanduser().resolve() for item in pdf_args]
    return create_sample_pdfs()


async def run_demo(args: argparse.Namespace) -> int:
    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    session_id: Optional[str] = None
    pdf_paths = resolve_pdf_paths(args.pdf)

    if psutil is not None:
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            pass

    provider_mode = "live" if provider_available(args.provider) else "mock"
    print(f"DocuSense standalone runner started in {provider_mode} mode with provider={args.provider}")
    print(f"Temporary vector workspace: {VECTOR_ROOT}")

    try:
        upload_result = await upload_pdfs(pdf_paths, provider=args.provider)
        session_id = upload_result["session_id"]
        print_section("Indexed PDFs", "\n".join(f"- {path.name}" for path in pdf_paths))
        print_section("Summary", format_summary(upload_result["summary_details"]))
        print_section(
            "Uploaded PDF Stats",
            json.dumps(
                {
                    "session_id": upload_result["session_id"],
                    "uploaded_pdf_count": upload_result["uploaded_pdf_count"],
                    "chunk_count": upload_result["chunk_count"],
                    "uploaded_pdfs": upload_result["uploaded_pdfs"],
                },
                indent=2,
            ),
        )

        strict_result = await ask_pdf(
            session_id,
            args.strict_question,
            provider=args.provider,
            answer_mode_preference="strict_pdf",
        )
        strict_sources = strict_result.get("retrieved", [])
        print_section("Strict PDF Answer", strict_result.get("answer", ""))
        print_section("Strict PDF Sources", format_sources(strict_sources))

        explanation_result = await ask_pdf(
            session_id,
            args.explanation_question,
            provider=args.provider,
            answer_mode_preference="explanation",
        )
        explanation_sources = explanation_result.get("retrieved", [])
        print_section("Explanation Answer", explanation_result.get("answer", ""))
        print_section("Explanation Sources", format_sources(explanation_sources))

        compare_result = await compare_pdfs(
            session_id,
            provider=args.provider,
            compare_instruction=args.compare_instruction,
        )
        print_section("Comparison", compare_result["content"])
        print_section("Comparison Sources", format_compare_sources(compare_result["sources"]))

        metrics = capture_metrics(start_wall, start_cpu)
        extra_cpu = ""
        if psutil is not None:
            try:
                extra_cpu = f"\nSystem CPU snapshot: {psutil.cpu_percent(interval=0.2)}%"
            except Exception:
                extra_cpu = ""
        load_text = (
            f"\nLoad average (1m, 5m, 15m): {metrics.load_average}"
            if metrics.load_average is not None
            else ""
        )
        print_section(
            "CPU Utilization",
            (
                f"Wall time: {metrics.wall_seconds}s\n"
                f"Process CPU time: {metrics.cpu_seconds}s\n"
                f"Approx process CPU utilization (single-core equivalent): {metrics.cpu_percent_single_core}%\n"
                f"CPU cores visible: {metrics.cpu_count}"
                f"{load_text}"
                f"{extra_cpu}"
            ),
        )
        return 0
    except Exception as exc:
        print_section("Run Failed", f"{type(exc).__name__}: {exc}")
        metrics = capture_metrics(start_wall, start_cpu)
        print_section(
            "CPU Utilization",
            (
                f"Wall time: {metrics.wall_seconds}s\n"
                f"Process CPU time: {metrics.cpu_seconds}s\n"
                f"Approx process CPU utilization (single-core equivalent): {metrics.cpu_percent_single_core}%"
            ),
        )
        return 1
    finally:
        if session_id and not args.keep_temp:
            reset_session(session_id)
        if not args.keep_temp and VECTOR_ROOT.exists():
            shutil.rmtree(VECTOR_ROOT, ignore_errors=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Standalone DocuSense AI server runner.")
    parser.add_argument(
        "--provider",
        choices=["minimax", "groq", "openai"],
        default="groq",
        help="LLM provider to use. If no API key is configured, the script falls back to mock mode.",
    )
    parser.add_argument(
        "--pdf",
        action="append",
        default=[],
        help="Path to a PDF file. Repeat this flag to upload multiple PDFs. If omitted, temporary sample PDFs are used.",
    )
    parser.add_argument(
        "--strict-question",
        default="What does the PDF say about RAG?",
        help="Question to run in strict PDF mode.",
    )
    parser.add_argument(
        "--explanation-question",
        default="Explain why vector databases are important in simple language.",
        help="Question to run in explanation mode.",
    )
    parser.add_argument(
        "--compare-instruction",
        default="Compare the uploaded PDFs, their similarities, differences, concepts, strengths, and focus areas.",
        help="Instruction used for the comparison step.",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep the temporary Chroma and sample PDF directories after the run.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(run_demo(args))


if __name__ == "__main__":
    raise SystemExit(main())
