import json
import re
from typing import Any

import httpx

from services.config import settings
from services.schemas import IntentType, RichSummary, SummaryTerm


STRICT_SYSTEM_RULE = (
    "Answer using only the provided PDF context. "
    "If the answer is not present in the context, say exactly: "
    "'This information is not available in the uploaded PDF.' "
    "Do not hallucinate."
)

EXPLANATION_SYSTEM_RULE = (
    "Use the PDF context as the primary source. "
    "You may add concise general knowledge only when it helps explain the concept, "
    "but never imply that extra knowledge came from the PDF. "
    "Clearly separate 'What the PDF says', 'Additional explanation', and 'Simple example'. "
    "If the PDF does not define something clearly, say that explicitly."
)


class LLMServiceError(RuntimeError):
    pass


def is_provider_configured(provider: str) -> bool:
    provider_map = {
        "minimax": bool(settings.minimax_api_key),
        "groq": bool(settings.groq_api_key),
        "openai": bool(settings.openai_api_key),
    }
    return provider_map.get(provider, False)


def _provider_config(provider: str) -> tuple[str, str, str]:
    configs = {
        "minimax": (settings.minimax_base_url, settings.minimax_api_key, settings.minimax_model),
        "groq": (settings.groq_base_url, settings.groq_api_key, settings.groq_model),
        "openai": (settings.openai_base_url, settings.openai_api_key, settings.openai_model),
    }
    try:
        return configs[provider]
    except KeyError as exc:
        raise LLMServiceError(f"Unsupported LLM provider: {provider}") from exc


def _extract_json_block(raw_text: str) -> dict[str, Any] | None:
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


def _normalize_term_list(items: Any) -> list[SummaryTerm]:
    normalized: list[SummaryTerm] = []
    if not isinstance(items, list):
        return normalized

    for item in items:
        if isinstance(item, dict):
            term = str(item.get("term", "")).strip()
            explanation = str(item.get("explanation", "")).strip()
        else:
            term = str(item).strip()
            explanation = ""

        if term:
            normalized.append(SummaryTerm(term=term, explanation=explanation))

    return normalized


def _normalize_summary_payload(payload: dict[str, Any] | None, fallback_text: str = "") -> RichSummary:
    payload = payload or {}
    key_concepts = payload.get("key_concepts") or []
    if not isinstance(key_concepts, list):
        key_concepts = []

    return RichSummary(
        overall_summary=str(payload.get("overall_summary", fallback_text)).strip() or fallback_text,
        main_objective=str(payload.get("main_objective", "")).strip(),
        key_concepts=[str(item).strip() for item in key_concepts if str(item).strip()],
        important_terms=_normalize_term_list(payload.get("important_terms")),
        missing_but_important_terms=_normalize_term_list(payload.get("missing_but_important_terms")),
        additional_general_explanation=str(payload.get("additional_general_explanation", "")).strip(),
        final_takeaway=str(payload.get("final_takeaway", "")).strip(),
    )


async def _openai_compatible_chat(
    *,
    provider: str,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
) -> str:
    base_url, api_key, model = _provider_config(provider)
    if not api_key:
        raise LLMServiceError(f"Missing API key for the selected LLM provider: {provider}.")

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code >= 400:
        raise LLMServiceError(f"LLM request failed for {provider}: {response.text}")

    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


async def call_provider(prompt: str, system_prompt: str, provider: str, temperature: float = 0.2) -> str:
    return await _openai_compatible_chat(
        provider=provider,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
    )


async def call_auxiliary_model(prompt: str, system_prompt: str, temperature: float = 0.2) -> str:
    for provider in ("groq", "openai", "minimax"):
        if is_provider_configured(provider):
            return await call_provider(prompt, system_prompt, provider, temperature)
    raise LLMServiceError("No configured LLM provider is available for auxiliary tasks.")


def _heuristic_intent(question: str) -> IntentType | None:
    lowered = question.lower().strip()

    summary_terms = ("summary", "summarize", "overview", "recap", "main points")
    comparison_terms = ("compare", "difference", "advantages", "disadvantages", "pros", "cons", "versus", "vs")
    example_terms = ("example", "sample", "use case", "scenario")
    explanation_terms = (
        "explain",
        "meaning",
        "important",
        "importance",
        "why",
        "how does",
        "how do",
        "benefit",
        "drawback",
        "define",
        "concept",
    )
    strict_terms = ("what does", "which", "when", "who", "where", "according to", "state the", "mention")

    if any(term in lowered for term in summary_terms):
        return "summary"
    if any(term in lowered for term in comparison_terms):
        return "comparison"
    if any(term in lowered for term in example_terms):
        return "example"
    if any(term in lowered for term in explanation_terms):
        return "explanation"
    if any(term in lowered for term in strict_terms):
        return "strict_pdf"
    return None


async def detect_intent(question: str) -> IntentType:
    heuristic = _heuristic_intent(question)
    if heuristic:
        return heuristic

    prompt = (
        "Classify the user's question into one of these labels only: "
        "strict_pdf, explanation, summary, comparison, example, unknown.\n"
        "Return valid JSON with one key named 'intent'.\n\n"
        f"Question: {question}"
    )
    raw = await call_auxiliary_model(
        prompt,
        system_prompt="You classify user intent for a PDF chatbot routing graph.",
        temperature=0.0,
    )
    payload = _extract_json_block(raw) or {}
    intent = str(payload.get("intent", "unknown")).strip().lower()
    if intent in {"strict_pdf", "explanation", "summary", "comparison", "example", "unknown"}:
        return intent  # type: ignore[return-value]
    return "unknown"


async def generate_rich_summary(combined_context: str, provider: str) -> RichSummary:
    prompt = (
        "Create a rich educational summary from the PDF context. "
        "Return valid JSON with these keys only: "
        "overall_summary, main_objective, key_concepts, important_terms, "
        "missing_but_important_terms, additional_general_explanation, final_takeaway.\n"
        "For important_terms and missing_but_important_terms, return arrays of objects "
        "with keys 'term' and 'explanation'.\n"
        "Base the summary on the PDF. If the PDF leaves something unclear but that concept "
        "is important for understanding, put it under missing_but_important_terms and "
        "additional_general_explanation. Do not invent fake PDF claims.\n\n"
        f"PDF Context:\n{combined_context}"
    )
    raw = await call_provider(
        prompt,
        system_prompt=(
            "You create educational PDF summaries. "
            "Stay grounded in the PDF and clearly separate any extra general explanation."
        ),
        provider=provider,
        temperature=0.5,
    )
    payload = _extract_json_block(raw)
    return _normalize_summary_payload(payload, fallback_text=raw.strip())


async def rewrite_question(question: str) -> str:
    prompt = (
        "Rewrite this user question so it becomes easier for semantic retrieval against a PDF. "
        "Keep the meaning unchanged and output only the rewritten question.\n\n"
        f"Question: {question}"
    )
    return await call_auxiliary_model(
        prompt,
        system_prompt="You rewrite questions for vector retrieval.",
        temperature=0.1,
    )


async def check_relevance(question: str, context: str) -> bool:
    prompt = (
        "Return valid JSON with a single key 'relevant' set to true or false. "
        "Mark true only if the context is reasonably sufficient to answer the question.\n\n"
        f"Question: {question}\n\nContext:\n{context[:7000]}"
    )
    raw = await call_auxiliary_model(
        prompt,
        system_prompt="You judge retrieval quality for a RAG system.",
        temperature=0.0,
    )
    payload = _extract_json_block(raw)
    return bool(payload and payload.get("relevant"))


def format_summary_for_chat(summary: RichSummary) -> str:
    important_terms = "\n".join(
        f"- {item.term}: {item.explanation}" for item in summary.important_terms
    ) or "- None highlighted."
    missing_terms = "\n".join(
        f"- {item.term}: {item.explanation}" for item in summary.missing_but_important_terms
    ) or "- None highlighted."
    key_concepts = "\n".join(f"- {concept}" for concept in summary.key_concepts) or "- None extracted."

    return (
        f"Overall summary\n{summary.overall_summary or 'No summary available.'}\n\n"
        f"Main objective\n{summary.main_objective or 'Not clearly stated.'}\n\n"
        f"Key concepts\n{key_concepts}\n\n"
        f"Important terms\n{important_terms}\n\n"
        f"Terms not clearly explained in the PDF but useful for understanding\n{missing_terms}\n\n"
        f"Additional general explanation\n{summary.additional_general_explanation or 'No extra explanation needed.'}\n\n"
        f"Final takeaway\n{summary.final_takeaway or 'No final takeaway available.'}"
    )


async def answer_with_context(
    *,
    question: str,
    context: str,
    simple_language: bool,
    provider: str,
    intent: IntentType,
    strict_mode: bool,
) -> str:
    style = "Use simple language." if simple_language else "Use clear educational language."

    if strict_mode:
        prompt = (
            f"{style}\n"
            "Answer the question strictly from the PDF context.\n\n"
            f"Question: {question}\n\n"
            f"PDF Context:\n{context}"
        )
        return await call_provider(prompt, STRICT_SYSTEM_RULE, provider, temperature=0.2)

    intent_instructions = {
        "explanation": "Explain the meaning, importance, and intuition behind the idea.",
        "comparison": "Compare the ideas carefully and highlight similarities and differences.",
        "example": "Include a simple, beginner-friendly example.",
        "unknown": "Answer helpfully using the PDF first, then brief additional explanation if useful.",
        "summary": "Provide a concise educational summary.",
        "strict_pdf": "Answer carefully from the PDF.",
    }
    prompt = (
        f"{style}\n"
        f"{intent_instructions.get(intent, intent_instructions['unknown'])}\n"
        "Format the answer with these section headings exactly:\n"
        "What the PDF says\n"
        "Additional explanation\n"
        "Simple example\n\n"
        "If the PDF does not directly define the concept, say so in 'What the PDF says'. "
        "Only use outside knowledge in 'Additional explanation'. "
        "If an example is unnecessary, say 'Simple example: Not needed.'\n\n"
        f"Question: {question}\n\n"
        f"PDF Context:\n{context if context.strip() else 'No strong PDF context was retrieved.'}"
    )
    return await call_provider(prompt, EXPLANATION_SYSTEM_RULE, provider, temperature=0.5)


async def generate_action_content(action: str, context: str, provider: str, extra_instruction: str | None = None) -> str:
    prompts = {
        "simple_explain": "Explain the PDF content in very simple language for a beginner.",
        "key_points": "Generate concise key points from the PDF content.",
        "mcqs": "Generate 10 multiple-choice questions from the PDF with four options and mark the correct answer.",
        "flashcards": "Generate useful flashcards from the PDF in 'Front: ... / Back: ...' format.",
        "rewrite": "Rewrite the PDF content into a cleaner, easier-to-read study note format.",
        "compare": (
            "Compare the uploaded PDFs or sections using the context first. "
            "Clearly label any extra explanation if needed."
        ),
    }
    prompt = f"{prompts[action]}\n\n"
    if extra_instruction:
        prompt += f"User instruction: {extra_instruction}\n\n"
    prompt += f"PDF Context:\n{context[:16000]}"

    return await call_provider(
        prompt,
        system_prompt=(
            "Use the PDF context as the primary source. "
            "Do not invent fake PDF claims. "
            "If you add general explanation, label it clearly."
        ),
        provider=provider,
        temperature=0.5,
    )


async def generate_multi_pdf_comparison(
    *,
    grouped_context: str,
    provider: str,
    pdf_names: list[str],
    compare_instruction: str | None = None,
) -> str:
    instruction_block = f"User instruction: {compare_instruction}\n\n" if compare_instruction else ""
    prompt = (
        "You are comparing multiple uploaded PDFs. "
        "Use the grouped context from each PDF. "
        "Do not compare only one document. "
        "If a point appears in one PDF but not another, clearly mention that.\n\n"
        "Structure the answer with these headings exactly:\n"
        "Overview of each PDF\n"
        "Similarities\n"
        "Differences\n"
        "Key concepts compared\n"
        "Strengths / focus area of each PDF\n"
        "Final conclusion\n\n"
        f"PDF names: {', '.join(pdf_names)}\n\n"
        f"{instruction_block}"
        f"Grouped PDF context:\n{grouped_context[:22000]}"
    )
    return await call_provider(
        prompt,
        system_prompt=(
            "Compare the PDFs using the provided grouped context. "
            "Do not invent missing claims. "
            "If a document lacks information on a point, say that clearly."
        ),
        provider=provider,
        temperature=0.5,
    )
