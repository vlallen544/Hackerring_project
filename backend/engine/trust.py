"""Deterministic trust model for source conflict resolution.

    trust = 0.30 * recency + 0.30 * authority + 0.25 * agreement + 0.15 * specificity

Every input is scored 0.0–1.0 by an explicit rule. No LLM call touches the
number — the model is allowed to *argue*, the engine decides.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Sequence

WEIGHTS = {
    "recency": 0.30,
    "authority": 0.30,
    "agreement": 0.25,
    "specificity": 0.15,
}

#: Rough "how much has this discipline moved since publication" in years.
DEFAULT_HALF_LIFE = {
    "textbook": 6.0,
    "notes": 4.0,
    "slides": 3.0,
    "paper": 2.0,
    "jd": 2.0,
    "url": 1.5,
    "unknown": 4.0,
}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def recency_score(published: datetime | None, kind: str = "unknown",
                   today: datetime | None = None) -> float:
    """Exponential decay against a per-kind half-life, in years."""
    if published is None:
        return 0.5  # undated sources are treated as neutral
    today = today or datetime.now(timezone.utc)
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    years = max(0.0, (today - published).total_seconds() / (365.25 * 24 * 3600))
    half_life = DEFAULT_HALF_LIFE.get(kind, DEFAULT_HALF_LIFE["unknown"])
    return _clamp(0.5 ** (years / half_life))


def authority_score(authority: float) -> float:
    """Direct mapping — callers supply a 0.0–1.0 authority value."""
    return _clamp(authority)


def specificity_score(text: str) -> float:
    """Vague claims score low; named, quantified claims score high."""
    if not text:
        return 0.0
    signals = 0.0
    if any(ch.isdigit() for ch in text):
        signals += 0.4
    if len(text.split()) >= 8:
        signals += 0.3
    # Hedge words reduce specificity.
    hedges = ("maybe", "probably", "generally", "sometimes", "I think", "around")
    if any(h in text.lower() for h in hedges):
        signals -= 0.3
    return _clamp(signals + 0.3)


def agreement_score(claim: str, peers: Sequence[str]) -> float:
    """Fraction of peer claims containing meaningful overlap with `claim`."""
    if not peers:
        return 1.0  # uncontested claim
    claim_terms = _terms(claim)
    if not claim_terms:
        return 0.0
    hits = 0
    for peer in peers:
        overlap = claim_terms & _terms(peer)
        if overlap and len(overlap) >= max(1, len(claim_terms) // 3):
            hits += 1
    return _clamp(hits / len(peers))


def _terms(text: str) -> set[str]:
    return {w for w in "".join(
        c.lower() if c.isalnum() else " " for c in text).split() if len(w) > 3}


def trust_score(*, recency: float, authority: float, agreement: float,
                specificity: float) -> float:
    """Weighted combination of the four dimensions."""
    return _clamp(
        WEIGHTS["recency"] * recency
        + WEIGHTS["authority"] * authority
        + WEIGHTS["agreement"] * agreement
        + WEIGHTS["specificity"] * specificity
    )


def score_claim(claim_text: str, peers: Iterable[str], *, published: datetime | None,
                kind: str, authority: float) -> float:
    """Convenience wrapper computing trust for a single claim."""
    peers = list(peers)
    return trust_score(
        recency=recency_score(published, kind),
        authority=authority_score(authority),
        agreement=agreement_score(claim_text, peers),
        specificity=specificity_score(claim_text),
    )


def resolve(a: dict, b: dict, margin: float = 0.05) -> dict:
    """Pick the higher-trust claim; flag ties for faculty review."""
    if abs(a["trust"] - b["trust"]) < margin:
        return {"winner": None, "action": "faculty_override",
                "reason": "trust too close to auto-resolve"}
    winner = a if a["trust"] > b["trust"] else b
    return {"winner": winner, "action": "adopt_winner",
            "reason": f"trust {winner['trust']:.2f} > "
                      f"{(b if winner is a else a)['trust']:.2f}"}
