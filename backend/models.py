"""Pydantic schemas for the VidyaPath API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class StatusEnum(str, Enum):
    draft = "draft"
    approved = "approved"
    locked = "locked"
    completed = "completed"


class LanguageEnum(str, Enum):
    en = "en"
    hi = "hi"
    kn = "kn"


class RoleEnum(str, Enum):
    student = "student"
    faculty = "faculty"
    placement = "placement"


# --- Brief -------------------------------------------------------------

class Source(BaseModel):
    kind: str
    url: Optional[str] = None
    name: str = ""
    authority: float = 0.0


class Chunk(BaseModel):
    source: Source
    page: int
    text: str
    quote: str = ""


class Claim(BaseModel):
    concept: str
    statement: str
    source: Source
    page: int
    quote: str
    trust_score: float = 0.0
    status: str = "pending"


class Conflict(BaseModel):
    claim_a: Claim
    claim_b: Claim
    resolution: str
    reason: str
    faculty_override: bool = False


class TeachingBriefPayload(BaseModel):
    subject: str
    title: str
    aim: str
    material: List[Chunk]
    language: LanguageEnum = LanguageEnum.en
    role: RoleEnum = RoleEnum.student


class TeachingBrief(BaseModel):
    brief_id: str
    subject: str
    title: str
    aim: str
    language: LanguageEnum
    sources: List[Source]
    chunks: List[Chunk]
    concepts: List[str]
    prerequisites: List[tuple[str, str]]
    claims: List[Claim]
    conflicts: List[Conflict]
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --- Plan --------------------------------------------------------------

class PlanItem(BaseModel):
    concept: str
    status: StatusEnum = StatusEnum.draft
    format: str = "text"
    assets: List[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class LearningPlan(BaseModel):
    plan_id: str
    version: int = 1
    items: List[PlanItem]
    status: str = "draft"
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# --- Student / mastery -------------------------------------------------
class StudentProfile(BaseModel):
    student_id: str
    name: str = ""
    language: LanguageEnum = LanguageEnum.en
    style: str = "visual"
    pace: float = 1.0


class MasteryRecord(BaseModel):
    student_id: str
    concept: str
    score: float = 0.0
    last_practiced: Optional[datetime] = None
    attempts: int = 0


class Attempt(BaseModel):
    student_id: str
    concept: str
    correct: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class VivaResult(BaseModel):
    transcript: str
    misconceptions: List[str]
    confidence: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# --- Doubt / risk ------------------------------------------------------

class Doubt(BaseModel):
    student_id: str
    concept: str
    question: str
    answer: str
    sources: List[Source]


class RiskEvent(BaseModel):
    student_id: str
    concept: str
    risk: float
    action: str
    reason: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChangeDiff(BaseModel):
    added: List[str]
    removed: List[str]
    modified: List[str]
    unchanged: List[str]
