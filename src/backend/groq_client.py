from __future__ import annotations

import json
import re
from typing import Any

from groq import Groq

from src.utils.logger import get_logger
from src.utils.resilience import (
    RetryConfig,
    groq_circuit_breaker,
    retry_with_backoff,
)

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a senior research scientist. Given a research question, produce a structured JSON response with these exact keys:
- "executive_summary": A 2-3 paragraph summary of findings (markdown)
- "key_takeaways": An array of 3-5 concise bullet-point takeaways
- "sections": An array of objects, each with "title" (section heading), "content" (markdown body), and "citations" (array of inline citation strings like "[Author et al. YEAR]")
- "references": An array of full reference strings (APA style)

Rules:
- Be thorough and scholarly. Write at least 4-6 sections.
- Each section should be 2-4 paragraphs with substantive content.
- Include plausible citations (authors, year, title/venue).
- Return ONLY valid JSON, no markdown fences, no extra text."""


def _clean_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _call_groq_api(question: str, api_key: str) -> dict[str, Any]:
    """Internal function to call Groq API (for retry logic)."""
    client = Groq(api_key=api_key)

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Research question: {question}"},
        ],
        temperature=0.7,
        max_tokens=8192,
        response_format={"type": "json_object"},
    )

    raw = resp.choices[0].message.content or "{}"
    cleaned = _clean_json(raw)
    return json.loads(cleaned)


async def generate_research(question: str, api_key: str) -> dict[str, Any]:
    """Generate research report using Groq API with retry and circuit breaker."""
    retry_config = RetryConfig(
        max_attempts=3,
        base_delay=1.0,
        max_delay=15.0,
        retryable_exceptions=(ConnectionError, TimeoutError, Exception),
    )

    try:
        data = await retry_with_backoff(
            _call_groq_api,
            question,
            api_key,
            config=retry_config,
            circuit_breaker=groq_circuit_breaker,
        )
    except Exception as e:
        logger.error(f"Groq API failed after retries: {e}")
        raise

    sections = data.get("sections", [])
    if isinstance(sections, list):
        for s in sections:
            if isinstance(s.get("citations"), list):
                s["citations"] = [str(c) for c in s["citations"]]

    references = data.get("references", [])
    key_takeaways = data.get("key_takeaways", [])
    executive_summary = data.get("executive_summary", "")

    report_md = _build_markdown(question, executive_summary, key_takeaways, sections, references)

    return {
        "question": question,
        "executive_summary": executive_summary,
        "key_takeaways": key_takeaways,
        "references": references,
        "sections": sections,
        "report_markdown": report_md,
        "report": data,
    }


def _build_markdown(
    question: str,
    executive_summary: str,
    key_takeaways: list[str],
    sections: list[dict],
    references: list[str],
) -> str:
    lines = [f"# Research Report: {question}", ""]
    if executive_summary:
        lines.append("## Executive Summary")
        lines.append("")
        lines.append(executive_summary)
        lines.append("")
    if key_takeaways:
        lines.append("## Key Takeaways")
        for t in key_takeaways:
            lines.append(f"- {t}")
        lines.append("")
    if sections:
        for s in sections:
            title = s.get("title", "Section")
            content = s.get("content", "")
            lines.append(f"## {title}")
            lines.append("")
            lines.append(content)
            lines.append("")
    if references:
        lines.append("## References")
        for i, r in enumerate(references, 1):
            lines.append(f"[{i}] {r}")
        lines.append("")
    return "\n".join(lines)
