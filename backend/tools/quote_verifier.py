"""Quote verifier — every generated claim must be backed by source material.

Hallucination defence: an LLM may only assert what it can point at. If the
quote is not literally present in the parsed chunks, the claim is rejected.
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence

from backend.models import Claim, Chunk


def _normalise(text: str) -> str:
    """Lowercase, collapse whitespace, unify quotes/dashes."""
    text = text.lower().replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", text).strip()


def find_quote(quote: str, chunks: Sequence[Chunk]) -> tuple[bool, Chunk | None]:
    """Locate a verbatim quote across parsed chunks.

    Returns (found, the_chunk_it_came_from). Matching is whitespace-insensitive
    so PDF line breaks never fail a legitimate citation.
    """
    target = _normalise(quote)
    if not target:
        return False, None
    for chunk in chunks:
        if target in _normalise(chunk.text):
            return True, chunk
    return False, None


def verify_claim(claim: Claim, chunks: Sequence[Chunk]) -> Claim:
    """Stamp `status = 'verified' | 'rejected'` based on quote presence."""
    found, chunk = find_quote(claim.quote, chunks)
    if found and chunk is not None:
        claim.status = "verified"
        claim.page = chunk.page
        claim.source = chunk.source
    else:
        claim.status = "rejected"
    return claim


def verify_claims(claims: Iterable[Claim], chunks: Sequence[Chunk]) -> list[Claim]:
    return [verify_claim(c, chunks) for c in claims]


def summary(claims: Iterable[Claim]) -> dict:
    verified = [c for c in claims if c.status == "verified"]
    rejected = [c for c in claims if c.status == "rejected"]
    return {
        "total": len(verified) + len(rejected),
        "verified": len(verified),
        "rejected": len(rejected),
        "coverage": round(len(verified) / max(1, len(verified) + len(rejected)), 3),
    }
