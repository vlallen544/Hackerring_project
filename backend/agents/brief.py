"""Brief agent — voice/spoken goal -> structured teaching brief."""

from __future__ import annotations

from backend.models import TeachingBrief
from .base import agent, run

SCHEMA_HINT = """Return JSON with exactly these keys:
{
  "subject": str,
  "title": str,
  "aim": str,                 // one sentence, measurable
  "audience": str,            // e.g. "3rd-year CSE"
  "concepts": [str],          // ordered, 8-15 items
  "prerequisites": [[str, str]], // [prereq, dependent]
  "language": "en" | "hi" | "kn",
  "tone": str                 // e.g. conversational, exam-focused
}"""


async def _handle(state: dict) -> dict:
    transcript = state.get("transcript", "")
    language = state.get("language", "en")

    result = await run(
        state,
        instructions=(
            "The faculty member dictated the following teaching goal, possibly "
            "rough and half-finished. Clean it up into a structured brief.\n\n"
            f"SPOKEN GOAL:\n{transcript}\n\n"
            f"Output language: {language}\n{SCHEMA_HINT}"
        ),
        json_mode=True,
    )

    brief = TeachingBrief(
        brief_id=state.get("brief_id", ""),
        subject=result.get("subject", ""),
        title=result.get("title", ""),
        aim=result.get("aim", ""),
        language=language,
        sources=state.get("sources", []),
        chunks=state.get("chunks", []),
        concepts=result.get("concepts", []),
        prerequisites=[tuple(p) for p in result.get("prerequisites", [])]
        if isinstance(result.get("prerequisites"), list) else [],
        claims=state.get("claims", []),
        conflicts=state.get("conflicts", []),
    )
    return {"brief": brief, **result}


node = agent("brief", _handle)
