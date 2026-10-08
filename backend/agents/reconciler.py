"""Reconciler agent — resolves conflicting claims across sources.

The LLM identifies *what* conflicts and proposes wording; the deterministic
trust model decides *which* claim wins and flags close calls for faculty.
"""

from __future__ import annotations

from backend.engine import trust_score, resolve_conflict
from backend.engine.trust import agreement_score, authority_score, recency_score, specificity_score
from backend.models import Claim, Conflict
from .base import agent, run

SCHEMA_HINT = """Return JSON:
{
  "conflicts": [{
    "concept": str,
    "claim_index_a": int,   // index into the claims array given to you
    "claim_index_b": int,
    "explanation": str      // why they disagree, in one sentence
  }]
}"""


def score_claim(claim: Claim, peers: list[Claim], published=None) -> dict:
    """Apply the four trust dimensions to one claim."""
    statements = [c.statement for c in peers if c is not claim]
    return {
        "claim": claim,
        "trust": trust_score(
            recency=recency_score(published, claim.source.kind),
            authority=authority_score(claim.source.authority),
            agreement=agreement_score(claim.statement, statements),
            specificity=specificity_score(claim.statement),
        ),
    }


async def _handle(state: dict) -> dict:
    claims: list[Claim] = state.get("claims", [])
    verified = [c for c in claims if c.status == "verified"]
    if len(verified) < 2:
        return {"conflicts": []}

    numbered = "\n".join(f"[{i}] {c.concept}: {c.statement} ({c.source.name}, p{c.page})"
                         for i, c in enumerate(verified))

    result = await run(
        state,
        instructions=(
            "These claims come from different faculty sources. Identify pairs "
            f"that genuinely contradict each other (not merely complementary).\n\n"
            f"CLAIMS:\n{numbered}\n\n{SCHEMA_HINT}"
        ),
        json_mode=True,
    )

    scored = [score_claim(c, verified) for c in verified]
    conflicts: list[Conflict] = []

    for raw in result.get("conflicts", []):
        try:
            a = verified[int(raw["claim_index_a"])]
            b = verified[int(raw["claim_index_b"])]
        except (IndexError, ValueError, KeyError):
            continue

        scored_a = next(s for s in scored if s["claim"] is a)
        scored_b = next(s for s in scored if s["claim"] is b)
        verdict = resolve_conflict(
            {"trust": scored_a["trust"], "claim": a},
            {"trust": scored_b["trust"], "claim": b},
        )

        winner = verdict["winner"]["claim"] if verdict["winner"] else a
        conflicts.append(Conflict(
            claim_a=a,
            claim_b=b,
            resolution=winner.statement,
            reason=verdict["reason"],
            faculty_override=verdict["action"] == "faculty_override",
        ))

    return {"conflicts": conflicts}


node = agent("reconciler", _handle)
