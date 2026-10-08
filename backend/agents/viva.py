"""Viva agent — spoken student goal -> prerequisite/difficulty questions."""

from __future__ import annotations

from backend.models import VivaResult
from .base import agent, run

SCHEMA_HINT = """Return JSON:
{
  "questions": [{"q": str, "target_concept": str, "level": "basic"|"deep"}],
  "anticipated_gaps": [str],
  "rubric": [{"concept": str, "pass_score": int}]
}"""


async def _handle(state: dict) -> dict:
    transcript = state.get("viva_transcript", "")
    concepts = state.get("concepts", [])
    student = state.get("student_profile", {})
    language = student.get("language", "en")

    if not transcript:
        return {"viva": None}

    result = await run(
        state,
        instructions=(
            "This student dictated what they already know about the subject. "
            "Design a short spoken viva (5-7 questions) that establishes their "
            "prerequisite knowledge and depth of understanding.\n\n"
            f"STUDENT GOAL:\n{transcript}\n\n"
            f"CONCEPTS: {concepts}\n"
            f"QUESTION LANGUAGE: {language}\n{SCHEMA_HINT}"
        ),
        json_mode=True,
    )

    return {
        "viva_questions": result.get("questions", []),
        "anticipated_gaps": result.get("anticipated_gaps", []),
        "rubric": result.get("rubric", []),
        "viva": VivaResult(
            transcript=transcript,
            misconceptions=result.get("anticipated_gaps", []),
            confidence=0.0,
        ),
    }


node = agent("viva", _handle)
