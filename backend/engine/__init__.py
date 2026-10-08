"""Deterministic logic for VidyaPath.

Every module here is pure Python: given the same inputs it returns the same
outputs. Trust, mastery, risk and plan diffs are *never* delegated to an LLM.
"""

from .trust import trust_score, resolve as resolve_conflict
from .mastery import apply_attempt, effective_mastery, is_prerequisite_met
from .risk import predict as predict_gap
from .diff import diff, diff_plan

__all__ = [
    "trust_score",
    "resolve_conflict",
    "apply_attempt",
    "effective_mastery",
    "is_prerequisite_met",
    "predict_gap",
    "diff",
    "diff_plan",
]
