# Pydantic schemas shared across the backend (the "shapes" of data agents must return)
from typing import Literal

from pydantic import BaseModel, Field

# ---------- Knowledge Builder output ----------
class Concept(BaseModel):
    id: str = Field(description="snake_case id, e.g. 'window_functions'. Same id for the same idea in every source.")
    name: str = Field(description="Human-readable name, e.g. 'Window Functions'")
    description: str = Field(description="One-sentence description of the concept")

class Claim(BaseModel):
    concept_id: str = Field(description="id of the concept this claim is about")
    statement: str = Field(description="The claim in one short sentence, in your own words")
    quote: str = Field(description="EXACT text copied from the source page that supports the claim (8-30 words)")
    source_id: str = Field(description="Source id from the <<SOURCE id | PAGE n>> header")
    page: int = Field(description="Page number from the <<SOURCE id | PAGE n>> header")
    claim_type: Literal["definition", "fact", "rule", "requirement", "opinion"]

class Prerequisite(BaseModel):
    before: str = Field(description="concept id that must be learned first")
    after: str = Field(description="concept id that depends on it")
    reason: str = Field(description="Why 'before' is needed for 'after'")

class ConceptPrerequisites(BaseModel):
    concept_id: str
    needs: list[str] = Field(description="ids of concepts a student must understand BEFORE this one. Direct "
                                         "prerequisites only. Empty list if this concept is foundational")
    reason: str = Field(description="One short sentence on why these are needed, or 'foundational'")


class PrerequisiteMap(BaseModel):
    concepts: list[ConceptPrerequisites] = Field(description="One entry for EVERY concept given, in the same order")


class KnowledgeExtraction(BaseModel):
    concepts: list[Concept]
    claims: list[Claim]
    prerequisites: list[Prerequisite]

# ---------- Source Reconciler output ----------
class ConflictSide(BaseModel):
    label: str = Field(description="Short summary of this side's position, e.g. 'MySQL supports window functions'")
    claim_ids: list[str] = Field(description="ids of the claims that take this position")
    is_specific: bool = Field(description="True if these claims give versions, dates or reasons")
    is_absolute: bool = Field(description="True if these claims use absolute words like always, never, every")


class DetectedConflict(BaseModel):
    concept_id: str
    topic: str = Field(description="What the disagreement is about, in a few words")
    conflict_type: Literal["contradiction", "outdated", "unreliable"] = Field(
        description="contradiction: sources disagree; outdated: one side was true earlier but is no longer; "
                    "unreliable: a single claim that is misleading or over-generalised (one side only)")
    sides: list[ConflictSide] = Field(description="2 sides for contradiction/outdated, 1 side for unreliable")
    summary: str = Field(description="One sentence describing the disagreement. Do NOT say who is right.")


class IndustrySkill(BaseModel):
    skill: str = Field(description="A database/SQL skill employers ask for, e.g. 'Window functions'")
    concept_id: str | None = Field(description="Matching concept id, or null if none")
    demanded_by: list[str] = Field(description="source ids of the job descriptions asking for it")
    faculty_coverage: Literal["covered", "partial", "outdated", "missing"] = Field(
        description="How the FACULTY NOTES handle this skill")
    note: str = Field(description="One short sentence explaining the coverage rating")


class ReconcilerOutput(BaseModel):
    conflicts: list[DetectedConflict]
    industry_skills: list[IndustrySkill]


# ---------- Viva agent ----------
class VivaQuestion(BaseModel):
    concept_id: str
    question: str = Field(description="One spoken-style interview question, answerable in 2-4 sentences")
    expected_points: list[str] = Field(description="2-3 key points a good answer should contain")


class VivaOpeners(BaseModel):
    questions: list[VivaQuestion]


class AnswerEvaluation(BaseModel):
    score: float = Field(description="0.0 (wrong or no answer) to 1.0 (complete and correct)")
    verdict: Literal["correct", "partial", "vague", "incorrect"]
    misconception: str | None = Field(
        description="If the answer shows a specific wrong belief, describe it in one short sentence; otherwise null")
    missing_prerequisite: str | None = Field(
        description="concept id of a prerequisite the student clearly does not understand, or null")
    feedback: str = Field(description="1-2 encouraging sentences for the student, in the student's language")
    follow_up_question: str | None = Field(
        description="If verdict is vague or partial: one probing question on the SAME concept. Otherwise null")


class QuestionReview(BaseModel):
    concept_id: str
    gives_away: str | None = Field(
        description="Quote the exact words that state, presuppose or hint at an expected point "
                    "(including naming the correct choice or saying something fails / is not allowed), or null")
    question: str = Field(description="The original question if gives_away is null and the language is right, "
                                      "otherwise the rewritten question")


class QuestionReviews(BaseModel):
    reviews: list[QuestionReview]


# ---------- Tutor agent ----------
class LessonSegment(BaseModel):
    text: str = Field(description="One short paragraph or bullet of the lesson, in the student's language")
    origin: Literal["material", "ai"] = Field(
        description="material: restates facts from the given TRUSTED CLAIMS (cite them). "
                    "ai: your own explanation, analogy or example")
    claim_ids: list[str] = Field(description="ids of the trusted claims this segment is based on (empty if origin is ai)")


class PracticeQuestion(BaseModel):
    question: str
    answer: str = Field(description="Model answer, 1-3 sentences")


class TutorLesson(BaseModel):
    title: str
    segments: list[LessonSegment] = Field(description="The lesson body, 4-8 segments")
    misconception_fix: str | None = Field(description="If misconceptions are given: a short correction. Otherwise null")
    diagram_mermaid: str | None = Field(description="For visual format: a simple Mermaid flowchart. Otherwise null")
    audio_script: str | None = Field(description="For audio format: the lesson as a friendly spoken script. Otherwise null")
    practice: list[PracticeQuestion] = Field(description="2-3 practice questions")


# ---------- Gap Predictor agent ----------
class GapNudge(BaseModel):
    student_message: str = Field(
        description="2-3 friendly sentences to the student explaining what was added to their path and why, "
                    "in the student's language")
    faculty_note: str = Field(description="One sentence for the faculty summarising the predicted gap and action, in English")
