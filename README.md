<<<<<<< HEAD
# PDF Chatbot with RAG, LangChain, LangGraph, ChromaDB, MiniMax, and Groq

This project is a full-stack PDF chatbot that lets a user upload one or more PDFs, generate an automatic summary, ask grounded questions, and run extra actions like generating MCQs, rewriting the content, comparing documents, and creating flashcards.

## Features

- Upload one or more PDFs in a temporary session.
- Extract page-wise text with PyMuPDF.
- Split text into semantic chunks with `RecursiveCharacterTextSplitter`.
- Create embeddings with `sentence-transformers/all-MiniLM-L6-v2`.
- Store embeddings in session-scoped ChromaDB collections.
- Run a LangGraph RAG workflow with retrieval, relevance check, optional question rewrite, and answer generation.
- Choose either `MiniMax` or `Groq Llama` as the answer-generation model.
- Show answer confidence, weak-context warning, and page references.
- Use quick actions for simple explanation, key points, 10 MCQs, flashcards, rewrite, and compare.
- Reset the session without using any permanent user database.

## Folder Structure

```text
backend/
  main.py
  routes/
  services/
  temp_uploads/
  chroma_db/
frontend/
  src/
    components/
```

## Backend Setup

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
cp .env.example .env
```

If your machine defaults to Python 3.14, install Python 3.12 first:

```bash
brew install python@3.12
```

Update `backend/.env`:

```env
MINIMAX_API_KEY=your_minimax_api_key
MINIMAX_MODEL=minimax-text-01
MINIMAX_BASE_URL=https://api.minimaxi.chat/v1
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_BASE_URL=https://api.groq.com/openai/v1
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
VECTOR_DB_PATH=./backend/chroma_db
FRONTEND_ORIGIN=http://localhost:5173
MAX_UPLOAD_SIZE_MB=20
```

Run the API:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:5173` and calls the FastAPI backend on `http://localhost:8000`.

## External Connections and Commands

### 1. ChromaDB local vector storage

No external cloud connection and no separate ChromaDB server are required for this project. Chroma runs in embedded local mode and persists into:

```bash
backend/chroma_db/
```

The backend creates a separate session folder automatically for each upload session.

If the folder does not exist yet, create it with:

```bash
mkdir -p backend/chroma_db
```

### 2. HuggingFace embedding model download

The first embedding request downloads the sentence-transformer model locally. This is automatic after dependencies are installed.

Optional pre-download check:

```bash
cd backend
python3 -c "from langchain_huggingface import HuggingFaceEmbeddings; HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2')"
```

### 3. MiniMax connection

Put your MiniMax API key in `backend/.env`. The backend sends requests through the configured OpenAI-compatible base URL:

```env
MINIMAX_API_KEY=...
MINIMAX_BASE_URL=https://api.minimaxi.chat/v1
```

If your MiniMax account uses a different endpoint or model name, update `MINIMAX_BASE_URL` and `MINIMAX_MODEL`.

### 4. Groq connection

Put your Groq API key in `backend/.env`:

```env
GROQ_API_KEY=...
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_MODEL=llama-3.3-70b-versatile
```

Groq is used for summary generation, relevance checking, question rewriting, and can also be selected as the answer model.

### 5. Test the API connections

Health check:

```bash
curl http://localhost:8000/health
```

Upload a PDF:

```bash
curl -X POST http://localhost:8000/upload-pdf \
  -F "files=@/absolute/path/to/your.pdf" \
  -F "llm_provider=minimax"
```

Ask a question:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "paste-session-id-here",
    "question": "What is the document about?",
    "llm_provider": "minimax"
  }'
```

Run an action:

```bash
curl -X POST http://localhost:8000/action \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "paste-session-id-here",
    "action": "mcqs",
    "llm_provider": "groq"
  }'
```

Reset the session:

```bash
curl -X POST http://localhost:8000/reset \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "paste-session-id-here"
  }'
```

## Notes

- This app uses temporary session storage only. There is no login and no permanent chat database.
- If a PDF has little or no readable text, the backend returns a warning that OCR may be required.
- The answering prompt is restricted to the retrieved PDF context and returns the required fallback sentence when context is missing.
=======
# DocuSense-AI-AI-powered-PDF-chatbot
**DocuSense AI** is an AI-powered PDF chatbot that uses RAG, vector search, and LLMs to deliver instant document understanding, smart summaries, and context-aware Q&amp;A. Upload any PDF, extract insights, and interact with content using LangChain, LangGraph, and advanced semantic retrieval.
>>>>>>> 13f2eef68f0586c4838399c94bbb0e397fa7e457
