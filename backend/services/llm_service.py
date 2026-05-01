import json

import httpx

from services.config import settings


SYSTEM_RULE = (
    "Answer using only the provided PDF context. "
    "If the answer is not present in the context, say exactly: "
    "'This information is not available in the uploaded PDF.' "
    "Do not hallucinate."
)


class LLMServiceError(RuntimeError):
    pass


async def _openai_compatible_chat(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
) -> str:
    if not api_key:
        raise LLMServiceError("Missing API key for the selected LLM provider.")

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code >= 400:
        raise LLMServiceError(f"LLM request failed: {response.text}")

    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


async def call_minimax(prompt: str, system_prompt: str = SYSTEM_RULE, temperature: float = 0.2) -> str:
    return await _openai_compatible_chat(
        base_url=settings.minimax_base_url,
        api_key=settings.minimax_api_key,
        model=settings.minimax_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
    )


async def call_groq(prompt: str, system_prompt: str, temperature: float = 0.2) -> str:
    return await _openai_compatible_chat(
        base_url=settings.groq_base_url,
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
    )


async def generate_summary(combined_context: str) -> str:
    prompt = (
        "Summarize this PDF content in 6 to 8 sentences for a user who just uploaded it. "
        "Mention the main topic, major sections, and what kinds of questions it can answer.\n\n"
        f"PDF Context:\n{combined_context[:12000]}"
    )
    return await call_groq(
        prompt,
        system_prompt="Create grounded summaries from PDF text only. Do not invent missing details.",
        temperature=0.3,
    )


async def rewrite_question(question: str) -> str:
    prompt = (
        "Rewrite this user question so it becomes easier for semantic retrieval against a PDF. "
        "Keep the meaning unchanged and output only the rewritten question.\n\n"
        f"Question: {question}"
    )
    return await call_groq(
        prompt,
        system_prompt="You rewrite questions for vector retrieval.",
        temperature=0.1,
    )


async def check_relevance(question: str, context: str) -> bool:
    prompt = (
        "Return valid JSON with a single key 'relevant' set to true or false. "
        "Mark true only if the context is sufficient to answer the question.\n\n"
        f"Question: {question}\n\nContext:\n{context[:5000]}"
    )
    raw = await call_groq(
        prompt,
        system_prompt="You judge retrieval quality for a RAG system.",
        temperature=0.0,
    )
    try:
        return bool(json.loads(raw).get("relevant"))
    except json.JSONDecodeError:
        return False


async def answer_with_context(question: str, context: str, simple_language: bool, provider: str) -> str:
    style = "Explain in simple language." if simple_language else "Answer clearly and precisely."
    prompt = (
        f"{style}\n\n"
        f"Question: {question}\n\n"
        f"PDF Context:\n{context}"
    )
    if provider == "groq":
        return await call_groq(prompt, system_prompt=SYSTEM_RULE, temperature=0.2)
    return await call_minimax(prompt, system_prompt=SYSTEM_RULE, temperature=0.2)


async def generate_action_content(action: str, context: str, provider: str, extra_instruction: str | None = None) -> str:
    prompts = {
        "simple_explain": "Explain the PDF content in very simple language for a beginner.",
        "key_points": "Generate concise key points from the PDF content.",
        "mcqs": "Generate 10 multiple-choice questions from the PDF with four options and mark the correct answer.",
        "flashcards": "Generate useful flashcards from the PDF in 'Front: ... / Back: ...' format.",
        "rewrite": "Rewrite the PDF content into a cleaner, easier-to-read study note format.",
        "compare": (
            "Compare the uploaded PDFs or sections using only the context. "
            "Highlight similarities, differences, and any missing basis for comparison."
        ),
    }
    prompt = f"{prompts[action]}\n\n"
    if extra_instruction:
        prompt += f"User instruction: {extra_instruction}\n\n"
    prompt += f"PDF Context:\n{context[:14000]}"

    if provider == "groq":
        return await call_groq(prompt, system_prompt=SYSTEM_RULE, temperature=0.3)
    return await call_minimax(prompt, system_prompt=SYSTEM_RULE, temperature=0.3)

