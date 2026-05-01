# DocuSense AI

DocuSense AI is a full-stack PDF learning assistant that uses RAG, LangChain, LangGraph, ChromaDB, and multiple LLM providers to help users upload PDFs, generate rich educational summaries, and ask both factual and explanatory questions.

## Highlights

- Upload one or more PDFs in a temporary session.
- Extract page-wise text with PyMuPDF.
- Chunk content with overlap and preserve page metadata.
- Store embeddings in local embedded ChromaDB.
- Use MiniMax, Groq, or OpenAI as the selected answer model.
- Route questions with LangGraph using intent detection:
  - `strict_pdf`
  - `explanation`
  - `summary`
  - `comparison`
  - `example`
  - `unknown`
- Generate richer summaries with:
  - overall summary
  - main objective
  - key concepts
  - important terms
  - missing but useful terms
  - additional explanation
  - final takeaway
- Support quick actions for key points, MCQs, flashcards, rewrite, and compare.

## Project Structure

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

Use Python 3.12 for the backend.

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
cp .env.example .env
```

If your machine defaults to Python 3.14:

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
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-mini
OPENAI_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
VECTOR_DB_PATH=./backend/chroma_db
FRONTEND_ORIGIN=http://localhost:5173
MAX_UPLOAD_SIZE_MB=20
```

Run the backend:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend:

```text
http://localhost:5173
```

Backend docs:

```text
http://localhost:8000/docs
```

## ChromaDB Setup

This project uses local embedded ChromaDB, so you do not need a separate Chroma server.

Chroma persists inside:

```bash
backend/chroma_db/
```

Create the folder if needed:

```bash
mkdir -p backend/chroma_db
```

The backend creates a separate session-scoped collection automatically for each upload session.

## External Connections

### MiniMax

Put your MiniMax API key in `backend/.env` and keep:

```env
MINIMAX_BASE_URL=https://api.minimaxi.chat/v1
```

### Groq

Put your Groq API key in `backend/.env` and keep:

```env
GROQ_BASE_URL=https://api.groq.com/openai/v1
```

### OpenAI

Put your OpenAI API key in `backend/.env` and keep:

```env
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4.1-mini
```

## Useful API Tests

Health check:

```bash
curl http://localhost:8000/health
```

Upload a PDF:

```bash
curl -X POST http://localhost:8000/upload-pdf \
  -F "files=@/absolute/path/to/your.pdf" \
  -F "llm_provider=openai"
```

Ask a question:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "paste-session-id-here",
    "question": "Explain the main concept in simple words.",
    "llm_provider": "openai"
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

- API keys stay in the backend only.
- This app uses temporary session storage and no permanent user database.
- If a PDF contains little or no readable text, the backend returns a warning that OCR may be required.
- Strict PDF mode never fabricates PDF content.
- Explanation mode can add general knowledge, but labels it clearly as additional explanation.
