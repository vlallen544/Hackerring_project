"""Tutor agent — personalised lesson generation for one student."""

from __future__ import annotations

from backend.engine import effective_mastery
from .base import agent, run

SCHEMA_HINT = """Return JSON:
{
  "lesson_id": str,
  "level": "beginner" | "intermediate" | "advanced",
  "language": "en" | "hi" | "kn",
  "sections": [{"heading": str, "body": str, "format": str}],
  "diagram_prompt": str,       // English prompt for agnes-image-2.5-flash
  "practice": [{"q": str, "answer": str, "concept": str}],
  "est_minutes": int,
  "prerequisite_note": str     // what to revise first, if anything
}"""


async def _handle(state: dict) -> dict:
    plan = state.get("plan")
    student = state.get("student_profile", {})
    mastery_raw = state.get("mastery", {})

    # Apply forgetting before generating so stale knowledge shapes the lesson.
    mastery = {
        c: effective_mastery(score, state.get("last_practiced", {}).get(c))
        for c, score in mastery_raw.items()
    }

    concept = state.get("focus_concept", "")
    weak = sorted(mastery.items(), key=lambda kv: kv[1])[:3]
    language = student.get("language", "en")
    style = student.get("style", "visual")

    result = await run(
        state,
        instructions=(
            "Generate a personalised lesson for this single student.\n"
            f"FOCUS CONCEPT: {concept}\n"
            f"STUDENT STYLE: {style} | LANGUAGE: {language}\n"
            f"WEAKEST CONCEPTS (mastery): {weak}\n"
            f"PLAN ITEM: {plan}\n\n"
            "Adapt difficulty, language and format. Provide an English "
            "`diagram_prompt` when the concept is visual.\n"
            f"{SCHEMA_HINT}"
        ),
        json_mode=True,
    )

    # A diagram is only requested for visual learners.
    if style != "visual":
        result["diagram_prompt"] = ""

    return {"lesson": result}


node = agent("tutor", _handle)
