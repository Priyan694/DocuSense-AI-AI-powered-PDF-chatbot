import shutil
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document

from services.config import settings
from services.embeddings import get_embedding_function


VECTOR_ROOT = Path(settings.vector_db_path)
VECTOR_ROOT.mkdir(parents=True, exist_ok=True)


def get_session_store(session_id: str) -> Chroma:
    persist_directory = VECTOR_ROOT / session_id
    persist_directory.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=f"pdf_session_{session_id}",
        persist_directory=str(persist_directory),
        embedding_function=get_embedding_function(),
    )


def index_documents(session_id: str, documents: list[Document]) -> int:
    store = get_session_store(session_id)
    ids = [doc.metadata["chunk_id"] for doc in documents]
    store.add_documents(documents=documents, ids=ids)
    return len(documents)


def retrieve_documents(session_id: str, query: str, top_k: int = 4) -> list[tuple[Document, float]]:
    store = get_session_store(session_id)
    return store.similarity_search_with_relevance_scores(query, k=top_k)


def delete_session_store(session_id: str) -> None:
    persist_directory = VECTOR_ROOT / session_id
    if persist_directory.exists():
        shutil.rmtree(persist_directory, ignore_errors=True)

