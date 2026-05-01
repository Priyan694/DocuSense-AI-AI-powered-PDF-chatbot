from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.chat_routes import router as chat_router
from routes.pdf_routes import router as pdf_router
from services.config import settings


app = FastAPI(
    title="PDF Chatbot RAG API",
    version="1.0.0",
    description="Session-based PDF chatbot using RAG, LangChain, LangGraph, ChromaDB, MiniMax, Groq, and OpenAI.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pdf_router)
app.include_router(chat_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
