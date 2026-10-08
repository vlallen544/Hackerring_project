"""Deterministic mastery model.

Mastery rises with correct practice, decays over time, and is gated by
prerequisites — a concept cannot be mastered before its prerequisites are.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Mapping

#: Daily decay while unpracticed (e.g. 0.97 ** days -> ~half-life ~23 days).
DAILY_DECAY = 0.97
#: Minimum score before a prerequisite unblocks its dependents.
GATE = 0.6
#: Cap on reward for repeated attempts at the same concept.
PRACTICE_CAP = 8
BONUS = 0.18
PENALTY = 0.12


def _days_since(when: datetime | None, now: datetime) -> float:
    if when is None:
        return 0.0
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (now - when).total_seconds() / 86400.0)


def apply_attempt(score: float, correct: bool, attempts: int) -> float:
    """One practice event. Repeated attempts have diminishing returns."""
    factor = 1.0 / (1.0 + attempts / PRACTICE_CAP)
    delta = (BONUS if correct else -PENALTY) * factor
    return max(0.0, min(1.0, score + delta))


def decay(score: float, last_practiced: datetime | None, now: datetime) -> float:
    """Exponential forgetting curve applied to an unpracticed concept."""
    return score * (DAILY_DECAY ** _days_since(last_practiced, now))


def effective_mastery(score: float, last_practiced: datetime | None,
                      now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    return round(decay(score, last_practiced, now), 4)


def is_prerequisite_met(concept: str, mastery: Mapping[str, float],
                        prerequisites: Iterable[tuple[str, str]]) -> bool:
    """True when every prereq of `concept` clears the mastery gate."""
    for prereq, dependent in prerequisites:
        if dependent == concept and mastery.get(prereq, 0.0) < GATE:
            return False
    return True


def unlocked_concepts(concepts: Iterable[str], mastery: Mapping[str, float],
                      prerequisites: Iterable[tuple[str, str]]) -> list[str]:
    """All concepts whose prerequisites are satisfied right now."""
    prereqs = list(prerequisites)
    return [c for c in concepts
            if is_prerequisite_met(c, mastery, prereqs)]


def readiness(students: int, readiness_scores: Iterable[float]) -> dict:
    """Class-level readiness aggregate for the faculty forecast."""
    scores = [s for s in readiness_scores]
    ready = sum(1 for s in scores if s >= GATE)
    return {
        "students": students,
        "ready": ready,
        "at_risk": students - ready,
        "avg_mastery": round(sum(scores) / len(scores), 3) if scores else 0.0,
    }
