"""Gap Predictor agent — risk scoring + auto-redesign.

The numeric risk comes from `engine.risk` (never the LLM). The agent decides
*what to teach next* from that risk and the prerequisite graph.
"""

from __future__ import annotations

from backend.engine import predict_gap
from .base import agent, run

SCHEMA_HINT = """Return JSON:
{
  "refresher": {"concepts": [str], "est_minutes": int, "rationale": str},
  "reorder": [{"concept": str, "position": int}],
  "note": str   // one sentence the faculty member will see in the feed
}"""


async def _handle(state: dict) -> dict:
    student = state.get("student_profile", {})
    mastery = state.get("mastery", {})
    prereqs = state.get("prerequisites", [])
    concept = state.get("focus_concept", "")

    prereq_scores = [mastery.get(p, 0.0) for p, dep in prereqs if dep == concept]

    # Deterministic verdict — reproducible for any student.
    verdict = predict_gap(
        concept,
        mastery=mastery.get(concept, 0.0),
        last_practiced=state.get("last_practiced", {}).get(concept),
        planned_progress=state.get("planned_progress", 1.0),
        actual_progress=state.get("actual_progress", 1.0),
        prereq_mastery=prereq_scores,
        failure_confidence=state.get("failure_confidence", 1.0),
    )

    if verdict["action"] == "monitor":
        return {"risk": verdict, "refresher": None, "gap_note": "No intervention needed."}

    weak_prereqs = [p for p, dep in prereqs
                    if dep == concept and mastery.get(p, 0.0) < 0.5]
    targets = weak_prereqs or [concept]

    result = await run(
        state,
        instructions=(
            "A gap was detected by the deterministic risk model.\n"
            f"VERDICT: {verdict}\n"
            f"WEAK PREREQUISITES: {weak_prereqs}\n"
            f"CONCEPT: {concept}\n\n"
            "Plan the smallest intervention that fixes it (refresher or "
            f"reorder). Keep it to the detected concepts.\n{SCHEMA_HINT}"
        ),
        json_mode=True,
    )
    result.setdefault("refresher", {}).setdefault("concepts", targets)

    return {"risk": verdict, "refresher": result.get("refresher"),
            "gap_note": result.get("note", "")}


node = agent("gap_predictor", _handle)
