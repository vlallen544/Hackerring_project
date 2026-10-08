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
    is_absolute: bool = Field(description="True only for sweeping generalisations (always, never, every, in all cases); "
                                          "a plain factual statement, even a negative one, is not absolute")


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
    feedback: str = Field(description="1-2 encouraging sentences for the student")
    follow_up_question: str | None = Field(
        description="If verdict is vague or partial: one probing question on the SAME concept. Otherwise null")


class QuestionReview(BaseModel):
    concept_id: str
    gives_away: str | None = Field(
        description="Quote the exact words that state, presuppose or hint at an expected point "
                    "(including naming the correct choice or saying something fails / is not allowed), or null")
    question: str = Field(description="The original question if gives_away is null, otherwise the rewritten question")


class QuestionReviews(BaseModel):
    reviews: list[QuestionReview]


# ---------- Tutor agent ----------
class LessonSegment(BaseModel):
    heading: str | None = Field(description="Short sub-heading when this segment starts a new part of the lesson "
                                            "(e.g. 'How it works', 'When to use it'), otherwise null")
    text: str = Field(description="One full paragraph of explanation (3-6 sentences)")
    origin: Literal["material", "ai"] = Field(
        description="material: restates facts from the given TRUSTED CLAIMS (cite them). "
                    "ai: your own explanation, analogy or example")
    claim_ids: list[str] = Field(description="ids of the trusted claims this segment is based on (empty if origin is ai)")


class LessonDiagram(BaseModel):
    title: str = Field(description="What the diagram shows")
    mermaid: str = Field(description="Valid Mermaid code starting with 'flowchart TD', 'flowchart LR', 'sequenceDiagram' "
                                     "or 'stateDiagram-v2'. Put labels with brackets or symbols in quotes: A[\"push(5)\"]")
    caption: str = Field(description="1-2 sentences explaining the diagram")


class WalkthroughStep(BaseModel):
    step: str = Field(description="What happens in this step")
    state: str | None = Field(description="The data after this step, e.g. 'stack = [5, 10]' or a small table, or null")


class CodeExample(BaseModel):
    title: str = Field(description="What this example shows, e.g. 'Stack using a Python list'")
    language: str = Field(description="Code language in lower case: python, sql, java, cpp or javascript")
    code: str = Field(description="Complete, correct, runnable code (8-40 lines) with short English comments")
    explanation: str = Field(description="2-4 sentences on how the code works")
    output: str | None = Field(description="What the code prints or returns when run, or null")


class ComplexityRow(BaseModel):
    operation: str
    time: str = Field(description="Time complexity in Big-O, e.g. O(1) or O(n log n)")
    space: str = Field(description="Extra space in Big-O")


class PracticeQuestion(BaseModel):
    question: str
    answer: str = Field(description="Model answer, 1-4 sentences or a short piece of code")


class TutorLesson(BaseModel):
    title: str
    overview: str = Field(description="2-3 sentences: what the student will learn and why it matters")
    segments: list[LessonSegment] = Field(description="The full explanation: 6-12 segments grouped under sub-headings")
    diagrams: list[LessonDiagram] = Field(description="1-3 diagrams that show how the concept works")
    walkthrough_title: str = Field(description="Title of the worked example, e.g. 'Pushing 5, 10, 15 and popping twice'")
    walkthrough: list[WalkthroughStep] = Field(description="Step-by-step trace on a small concrete example (4-8 steps)")
    code_examples: list[CodeExample] = Field(description="1-3 code examples implementing or using the concept")
    complexity: list[ComplexityRow] = Field(description="Time/space of the main operations if the topic has them, else empty")
    common_mistakes: list[str] = Field(description="2-4 typical mistakes students make with this topic")
    key_points: list[str] = Field(description="4-6 key takeaways to remember")
    misconception_fix: str | None = Field(description="If misconceptions are given: a short correction. Otherwise null")
    audio_script: str | None = Field(description="For audio format: the lesson as a friendly spoken script. Otherwise null")
    practice: list[PracticeQuestion] = Field(description="3-4 practice questions, from easier to harder")


# ---------- Gap Predictor agent ----------
class GapNudge(BaseModel):
    student_message: str = Field(
        description="2-3 friendly sentences to the student explaining what was added to their path and why")
    faculty_note: str = Field(description="One sentence for the faculty summarising the predicted gap and action, in English")


# ---------- Doubt Assistant ----------
class DoubtAnswer(BaseModel):
    answerable: bool = Field(description="True only if the TRUSTED FACTS contain what is needed to answer")
    answer: str = Field(description="If answerable: a clear explanation in 1-3 short paragraphs. "
                                    "If not: one or two sentences saying it is not covered by the course material")
    claim_ids: list[str] = Field(description="ids of the trusted facts the answer is based on (empty if not answerable)")
    concept_id: str | None = Field(description="id of the course concept the question is about, or null")
    example: str | None = Field(description="A short example (a few lines of code or a worked example) if it helps, else null")
    closest_topic: str | None = Field(description="If not answerable: the closest course concept id to study instead, else null")
    follow_ups: list[str] = Field(description="2-3 short follow-up questions the student could ask next")


# ---------- Class-Ready Kit (faculty) ----------
class OutlinePoint(BaseModel):
    point: str = Field(description="What to teach at this step, as a short heading")
    details: str = Field(description="1-2 sentences on how to teach it (example, board work, question to ask)")
    minutes: int = Field(description="Minutes to spend on this point")


class HandoutItem(BaseModel):
    heading: str | None = Field(description="Short sub-heading when this starts a new part, otherwise null")
    text: str = Field(description="1-3 sentences for students")
    origin: Literal["material", "ai"] = Field(
        description="material: restates trusted facts (list their ids). ai: your own explanation or example")
    claim_ids: list[str] = Field(description="ids of the trusted facts used (empty if origin is ai)")


class ClassMistake(BaseModel):
    mistake: str = Field(description="A mistake students make with this topic, in their words")
    correction: str = Field(description="The short correct explanation")
    from_class_data: bool = Field(description="True if it comes from the CLASS MISCONCEPTIONS given")


class QuizQuestion(BaseModel):
    question: str
    kind: Literal["mcq", "short"] = Field(description="mcq: multiple choice with 4 options; short: short written answer")
    options: list[str] = Field(description="4 options for mcq, empty for short answers")
    answer: str = Field(description="For mcq: exactly one of the options. For short: the model answer")
    explanation: str = Field(description="One sentence on why this is the answer")
    difficulty: Literal["easy", "medium", "hard"]
    targets_misconception: bool = Field(description="True if this question checks one of the class misconceptions")


class AssignmentTask(BaseModel):
    title: str
    task: str = Field(description="The practical task, interview style, with any data or starter code needed")
    industry_link: str | None = Field(description="Which industry requirement this reflects, or null")
    deliverable: str = Field(description="What the student submits")
    rubric: list[str] = Field(description="3-4 grading criteria")
    solution_outline: str = Field(description="A short outline of a good solution, for the teacher")


class ClassKit(BaseModel):
    title: str
    outline: list[OutlinePoint] = Field(description="5-8 teaching points in order")
    handout_title: str
    handout: list[HandoutItem] = Field(description="One page for students: 6-10 items")
    common_mistakes: list[ClassMistake] = Field(description="2-4 mistakes; put the class misconceptions first")
    quiz: list[QuizQuestion] = Field(description="5-8 questions mixing easy, medium and hard")
    assignment: list[AssignmentTask] = Field(description="1-2 practical tasks")
