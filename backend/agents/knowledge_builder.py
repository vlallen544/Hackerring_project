"""Knowledge Builder agent — parsed chunks -> structured knowledge base."""

from __future__ import annotations

from backend.tools.quote_verifier import verify_claims
from backend.models import Claim, Source
from .base import agent, run

SCHEMA_HINT = """Return JSON:
{
  "concepts": [{"name": str, "definition": str, "chapter": str}],
  "claims": [{"concept": str, "statement": str, "quote": str,
              "source_name": str, "page": int}],
  "gaps": [str],       // topics referenced but not explained in the material
  "outline": [str]     // recommended teaching order
}"""


async def _handle(state: dict) -> dict:
    chunks = state.get("chunks", [])
    material = state.get("material_chunks", [])
    if not material:
        return {"claims": [], "kb_concepts": []}

    result = await run(
        state,
        instructions=(
            "Build a structured knowledge base from the source material.\n"
            "Every claim MUST include a `quote` copied verbatim from the "
            "material — it will be verified against the original text.\n"
            f"{SCHEMA_HINT}"
        ),
        json_mode=True,
    )

    sources = {s.name: s for s in state.get("sources", [Source(kind="notes")])}
    claims = [
        Claim(
            concept=c.get("concept", ""),
            statement=c.get("statement", ""),
            source=sources.get(c.get("source_name", ""), Source(kind="unknown")),
            page=int(c.get("page", 0)),
            quote=c.get("quote", ""),
        )
        for c in result.get("claims", [])
    ]

    # Reject any claim whose quote does not literally appear in the material.
    claims = verify_claims(claims, chunks)

    return {
        "claims": claims,
        "kb_concepts": result.get("concepts", []),
        "kb_outline": result.get("outline", []),
        "kb_gaps": result.get("gaps", []),
    }


node = agent("knowledge_builder", _handle)
