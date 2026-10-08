"""Planner agent — brief + knowledge base -> sequenced learning plan."""

from __future__ import annotations

from backend.engine import diff_plan
from backend.models import LearningPlan, PlanItem
from .base import agent, run

SCHEMA_HINT = """Return JSON:
{
  "items": [{
    "concept": str,
    "format": "text" | "diagram" | "video" | "quiz" | "live",
    "est_minutes": int,
    "objective": str,
    "depends_on": [str]
  }]
}
Order items so every prerequisite appears before its dependents."""


async def _handle(state: dict) -> dict:
    brief = state.get("brief")
    concepts = list(getattr(brief, "concepts", []) or state.get("kb_outline", []))
    constraints = state.get("constraints", {})
    students = state.get("students", [])
    style = state.get("style", "balanced")

    # Per-student personalisation hooks the tutor will refine later.
    profiles = {s.get("student_id"): s.get("style") for s in students}

    result = await run(
        state,
        instructions=(
            "Design a sequenced learning plan for this brief.\n"
            f"BRIEF: {getattr(brief, 'aim', '')}\n"
            f"CONCEPTS: {concepts}\n"
            f"STYLE: {style}\n"
            f"CONSTRAINTS: {constraints}\n"
            f"STUDENT STYLES: {profiles}\n\n"
            f"{SCHEMA_HINT}"
        ),
        json_mode=True,
    )

    plan = LearningPlan(
        plan_id=state.get("plan_id", ""),
        version=state.get("plan_version", 1),
        items=[
            PlanItem(
                concept=i.get("concept", ""),
                format=i.get("format", "text"),
                details={
                    "est_minutes": i.get("est_minutes", 10),
                    "objective": i.get("objective", ""),
                    "depends_on": i.get("depends_on", []),
                },
            )
            for i in result.get("items", [])
        ],
    )

    # Report what changed relative to the previous plan version.
    changes = diff_plan({"items": state.get("plan_items", [])},
                        {"items": [i.model_dump() for i in plan.items]})

    return {"plan": plan, "plan_items": [i.model_dump() for i in plan.items],
            "changes": changes, "plan_version": plan.version}


node = agent("planner", _handle)
