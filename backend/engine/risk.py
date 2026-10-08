"""Deterministic gap prediction.

    action = decision(
        prerequisites,        # are the foundations weak?
        decay,                # is knowledge fading?
        pace_lag,             # is the learner behind the planned pace?
        failure_confidence    # are recent attempts trending down?
    )

Four inputs, one rule table, one output — reproducible for any student.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping

from .mastery import GATE, decay as decay_curve

#: What counts as "behind pace" (fraction of planned progress).
PACE_LAG_WARN = 0.15
PACE_LAG_RISK = 0.35
#: Concepts with mastery below this are treated as weak prerequisites.
PREREQ_WEAK = 0.5
#: Failure confidence below this pushes into redesign.
CONFIDENCE_LOW = 0.45

ACTION_MONITOR = "monitor"
ACTION_REFRESH = "auto_refresh"
ACTION_REDESIGN = "redesign"


@dataclass
class GapSignal:
    concept: str
    prereq_risk: float
    decay_risk: float
    pace_risk: float
    failure_confidence: float

    @property
    def composite(self) -> float:
        """Conservative aggregation: the worst factor dominates."""
        return max(self.prereq_risk, self.decay_risk, self.pace_risk,
                   1.0 - self.failure_confidence)


def compute_signal(concept: str, *, mastery: float, last_practiced: datetime | None,
                   planned_progress: float, actual_progress: float,
                   prereq_mastery: Iterable[float],
                   failure_confidence: float,
                   now: datetime | None = None) -> GapSignal:
    now = now or datetime.now(timezone.utc)

    prereqs = list(prereq_mastery)
    # No prereqs means no inherited risk from foundations.
    prereq_risk = (1.0 - min(prereqs)) if prereqs else 0.0

    decayed = decay_curve(mastery, last_practiced, now)
    decay_risk = 1.0 - decayed

    # Pace lag is the shortfall relative to planned progress.
    pace_lag = 0.0 if planned_progress <= 0 else \
        max(0.0, (planned_progress - actual_progress) / planned_progress)
    pace_risk = min(1.0, pace_lag * 2.5)

    return GapSignal(concept, round(prereq_risk, 4), round(decay_risk, 4),
                     round(pace_risk, 4), round(failure_confidence, 4))


def decide(signal: GapSignal) -> dict:
    """Rule table mapping a signal to the required intervention."""
    if (signal.prereq_risk > 1 - PREREQ_WEAK
            or signal.decay_risk > 1 - GATE
            or signal.failure_confidence < CONFIDENCE_LOW
            or signal.pace_risk >= PACE_LAG_RISK):
        action, why = ACTION_REDESIGN, "one or more factors above the risk threshold"
    elif (signal.pace_risk >= PACE_LAG_WARN
            or signal.decay_risk > 1 - GATE * 1.5):
        action, why = ACTION_REFRESH, "early warning — schedule a refresher"
    else:
        action, why = ACTION_MONITOR, "within normal range"

    return {
        "concept": signal.concept,
        "action": action,
        "risk": round(signal.composite, 4),
        "reason": why,
        "signals": {
            "prereq_risk": signal.prereq_risk,
            "decay_risk": signal.decay_risk,
            "pace_risk": signal.pace_risk,
            "failure_confidence": signal.failure_confidence,
        },
    }


def predict(concept: str, *, mastery: float, last_practiced: datetime | None,
            planned_progress: float, actual_progress: float,
            prereq_mastery: Mapping[str, float] | Iterable[float],
            failure_confidence: float) -> dict:
    """Full pipeline: signal -> decision."""
    prereqs = (list(prereq_mastery.values())
               if isinstance(prereq_mastery, Mapping)
               else list(prereq_mastery))
    signal = compute_signal(
        concept,
        mastery=mastery,
        last_practiced=last_practiced,
        planned_progress=planned_progress,
        actual_progress=actual_progress,
        prereq_mastery=prereqs,
        failure_confidence=failure_confidence,
    )
    return decide(signal)
