"""Doubt agent — explain a student's question in their language."""

from __future__ import annotations

from backend.tools.quote_verifier import find_quote
from .base import agent, run

SCHEMA_HINT = """Return JSON:
{
  "concept": str,
  "answer": str,
  "analogies": [str],
  "quoted": str,     // verbatim excerpt from the source material
  "follow_up": str
}"""


async def _handle(state: dict) -> dict:
    question = state.get("question", "")
    if not question:
        return {"doubt": None}

    student = state.get("student_profile", {})
    language = student.get("language", "en")
    level = student.get("level", "intermediate")

    result = await run(
        state,
        instructions=(
            "Answer this student's doubt. Use simple language, a real-world "
            "analogy, and ground it in the source material.\n\n"
            f"QUESTION: {question}\n"
            f"LEVEL: {level} | LANGUAGE: {language}\n\n"
            "The `quoted` field must be copied VERBATIM from SOURCE MATERIAL "
            "above; if none applies, use an empty string.\n"
            f"{SCHEMA_HINT}"
        ),
        json_mode=True,
    )

    # Verify the citation actually exists — drop it otherwise.
    quote = result.get("quoted", "")
    if quote:
        found, _ = find_quote(quote, state.get("chunks", []))
        if not found:
            result["quoted"] = ""

    return {"doubt": result}


node = agent("doubt", _handle)
