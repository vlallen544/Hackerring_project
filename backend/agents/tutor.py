# Tutor agent: writes a personalised lesson (level and format decided in code) from TRUSTED claims only,
# marks every segment's provenance (faculty material vs AI-added), and adapts again after practice answers.
import json
import re
from datetime import date
from pathlib import Path

from backend import courses, db
from backend.engine.adapt import decide_format, decide_level, learned_style, next_step_after_check
from backend.engine.mastery import blend, confidence_to_unit
from backend.models import AnswerEvaluation, TutorLesson
from backend.tools.agnes_client import chat_json
from backend.tools.llm import heavy_json

CHECK_WEIGHT = 0.3  # one practice answer moves mastery less than a full viva

LEVEL_GUIDE = {
    "foundation": "Start from the basics and recap the prerequisite claims first. Use simple words, an everyday "
                  "analogy, small inputs in the walkthrough and short, heavily commented code.",
    "standard": "Teach the full concept: how it works internally, when to use it, a worked trace and idiomatic code.",
    "challenge": "Go deeper: internals, edge cases, trade-offs against alternatives, an optimised implementation, "
                 "and how it is used in industry and asked in interviews.",
}
FORMAT_GUIDE = {
    "text": "A complete written lesson for reading.",
    "audio": "Also fill audio_script with a friendly spoken version of the explanation (short sentences, no code "
             "symbols read aloud), in plain spoken English.",
    "visual": "Lean on visuals: give 2-3 diagrams so every major idea has one, and keep paragraphs shorter.",
    "practice": "Lean on doing: 4 practice questions that build in difficulty, including writing or fixing code.",
}

TUTOR_PROMPT = """You are the Tutor agent of VidyaPath. Write ONE thorough lesson for ONE student, like a well-written
textbook chapter made for them. Fill every part of the schema:
- overview: what they will learn and why it matters.
- segments: a FULL explanation in 6-12 paragraphs under sub-headings (what it is, how it works internally,
  when and why to use it, variations and edge cases). Each paragraph 3-6 sentences.
- diagrams: Mermaid diagrams that show how the concept works (structure, flow or state changes). Use top-to-bottom
  ('flowchart TD') for sequences of more than 5 steps, and keep each diagram under about 12 nodes.
- walkthrough: trace the concept step by step on a small concrete example, showing the data after each step.
- code_examples: complete, correct, runnable code that implements or uses the concept, with an explanation and the
  output. Write code in the language the course is taught in (for example Java for a Java course, as seen in
  the course name and trusted claims); otherwise use Python for data structures and algorithms, and SQL for
  database topics. Code comments in English.
- complexity: time/space of the main operations, if the topic has operations; otherwise an empty list.
- common_mistakes and key_points.
Rules for facts:
- The TRUSTED CLAIMS are the course's verified facts. Never contradict them.
- Each segment: origin "material" if it restates trusted claims (list their ids in claim_ids),
  origin "ai" if it is your own explanation, analogy or example (claim_ids empty).
- Cite a claim only if it directly states the fact in that segment. Never write claim ids like (claim_5) in any text.
- "ai" segments, diagrams, walkthroughs and code may use standard, well-established textbook knowledge of the topic,
  but must not contradict the trusted claims and must not state facts about specific product versions, vendors or
  statistics that are not in the trusted claims.
- INDUSTRY CONTEXT (if given) may be mentioned to show why the topic matters, but never cite it as a fact.
- Practice questions: no yes/no questions and no questions that reveal the answer. Ask the student to write
  or fix a short piece of code or query, trace an algorithm on a small input, or explain why/when something is used.
- Write everything in clear, simple English.
- Level: {level}. {level_guide}
- Format: {fmt}. {format_guide}
- If MISCONCEPTIONS are listed, fill misconception_fix with a short, kind correction and address them in the text.
"""

CHECK_PROMPT = """You are the Tutor agent of VidyaPath, checking one practice answer.
Grade against the model answer and trusted claims. Do not penalise grammar or spelling mistakes.
Write feedback in clear, simple English. Be encouraging.
Set follow_up_question to null and missing_prerequisite to null."""

MERMAID_TYPES = ("flowchart", "graph", "sequenceDiagram", "stateDiagram", "classDiagram")
SCORE_RANGE = {"correct": (0.75, 1.0), "partial": (0.40, 0.74), "vague": (0.15, 0.45), "incorrect": (0.0, 0.35)}


def _kb():
    return json.loads(courses.course_file("trusted_kb.json").read_text(encoding="utf-8"))


def _student(student_id):
    found = db.rows("SELECT * FROM students WHERE id = ?", (student_id,))
    if not found:
        raise ValueError(f"Unknown student {student_id}")
    return found[0]


def _mastery(student_id):
    return {r["concept_id"]: r for r in db.rows("SELECT * FROM mastery WHERE student_id = ?", (student_id,))}


def _direct_prereqs(kb, concept_id):
    return [p["before"] for p in kb["prerequisites"] if p["after"] == concept_id]


def _active_misconceptions(student_id, concept_id, limit=2):
    """Misconceptions recorded AFTER the student's last correct answer on this concept (fixed ones expire),
    newest first, without duplicates."""
    attempts = db.rows("SELECT correct, misconception FROM attempts WHERE student_id = ? AND concept_id = ? "
                       "ORDER BY id", (student_id, concept_id))
    active = []
    for a in attempts:
        if a["correct"] is not None and a["correct"] >= 0.75:
            active = []  # a correct answer clears earlier misconceptions
        elif a["misconception"]:
            active.append(a["misconception"])
    unique = []
    for m in reversed(active):
        if m.strip().lower() not in [u.strip().lower() for u in unique]:
            unique.append(m)
    return unique[:limit]


def _lesson_row(lesson_id):
    found = db.rows("SELECT * FROM lessons WHERE id = ?", (lesson_id,))
    if not found:
        raise ValueError(f"Unknown lesson {lesson_id}")
    row = found[0]
    return {**row, "content": json.loads(row["content"]), "adaptation": json.loads(row["adaptation"])}


# --------------------------------------------------------------------------- #
# Lesson generation
# --------------------------------------------------------------------------- #
def generate_lesson(student_id, concept_id, level=None, fmt=None, reason=None):
    kb = _kb()
    if concept_id not in kb["concepts"]:
        raise ValueError(f"Unknown concept {concept_id}")
    student = _student(student_id)
    mastery = _mastery(student_id)
    prereqs = _direct_prereqs(kb, concept_id)

    # ---- 1. Decide level and format IN CODE, with reasons ----
    concept_m = mastery[concept_id]["score"] if concept_id in mastery else None
    prereq_m = {p: mastery[p]["score"] for p in prereqs if p in mastery}
    auto_level, level_why = decide_level(concept_m, prereq_m)
    auto_fmt, fmt_why = decide_format(student["stated_style"], student["learned_style"])
    if level:
        level_why = reason or f"Level set to {level}."
    if fmt:
        fmt_why = reason or f"Format set to {fmt}."
    level, fmt = level or auto_level, fmt or auto_fmt

    misconceptions = _active_misconceptions(student_id, concept_id)

    # ---- 2. Only TRUSTED claims go to the model (concept + prerequisites for a foundation recap) ----
    concept_scope = [concept_id] + (prereqs if level == "foundation" else [])
    in_scope = [c for c in kb["claims"] if c["concept_id"] in concept_scope and c["status"] == "trusted"]
    claims = [c for c in in_scope if c.get("claim_type") != "requirement"]  # citable teaching facts
    industry = [c["statement"] for c in in_scope if c.get("claim_type") == "requirement"]
    claims_by_id = {c["id"]: c for c in claims}

    lesson = heavy_json(  # long, detailed writing: Claude when available, else Agnes
        TUTOR_PROMPT.format(level=level, level_guide=LEVEL_GUIDE[level],
                            fmt=fmt, format_guide=FORMAT_GUIDE[fmt]),
        json.dumps({
            "course": courses.COURSES[courses.active_course()]["title"],
            "concept": kb["concepts"][concept_id]["name"],
            "target_role": student["target_role"],
            "trusted_claims": [{"id": c["id"], "concept": c["concept_id"], "claim": c["statement"]} for c in claims],
            "misconceptions": misconceptions,
            "industry_context": industry if level == "challenge" else [],
        }, ensure_ascii=False, indent=1),
        TutorLesson,
    )

    # ---- 3. Verify provenance in code: "material" must cite real trusted claims ----
    sources_by_id = {s["id"]: s for s in kb["sources"]}
    segments = []
    for seg in lesson.segments:
        ids = [i for i in seg.claim_ids if i in claims_by_id]
        origin = "material" if seg.origin == "material" and ids else "ai"
        segments.append({
            "heading": (seg.heading or "").strip() or None,
            "text": re.sub(r"\s*\((?:claim_\d+(?:,\s*)?)+\)", "", seg.text).strip(),
            "origin": origin,
            "sources": [{
                "claim_id": i,
                "source": sources_by_id.get(claims_by_id[i]["source_id"], {}).get("title", claims_by_id[i]["source_id"]),
                "page": claims_by_id[i]["page"],
                "quote": claims_by_id[i]["quote"],
            } for i in ids] if origin == "material" else [],
        })
    total = sum(len(s["text"]) for s in segments) or 1
    material_share = round(100 * sum(len(s["text"]) for s in segments if s["origin"] == "material") / total)

    # Only diagram types the UI can draw; the UI also repairs unquoted labels before giving up
    diagrams = [d.model_dump() for d in lesson.diagrams
                if d.mermaid.strip().startswith(MERMAID_TYPES)][:3]
    code_examples = [c.model_dump() for c in lesson.code_examples if c.code.strip()][:3]
    for c in code_examples:
        c["language"] = c["language"].strip().lower() or "text"

    content = {
        "title": lesson.title,
        "overview": lesson.overview,
        "segments": segments,
        "material_share_percent": material_share,
        "diagrams": diagrams,
        "walkthrough_title": lesson.walkthrough_title,
        "walkthrough": [w.model_dump() for w in lesson.walkthrough][:10],
        "code_examples": code_examples,
        "complexity": [r.model_dump() for r in lesson.complexity][:10],
        "common_mistakes": lesson.common_mistakes[:6],
        "key_points": lesson.key_points[:8],
        "misconception_fix": lesson.misconception_fix if misconceptions else None,
        "audio_script": lesson.audio_script if fmt == "audio" else None,
        "practice": [p.model_dump() for p in lesson.practice],
    }
    adaptation = {
        "level": level, "level_reason": level_why,
        "format": fmt, "format_reason": fmt_why,
        "targets_misconceptions": misconceptions,
        "recapped_prerequisites": prereqs if level == "foundation" else [],
    }
    lesson_id = db.execute(
        "INSERT INTO lessons (student_id, concept_id, level, format, content, adaptation) "
        "VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
        (student_id, concept_id, level, fmt,
         json.dumps(content, ensure_ascii=False), json.dumps(adaptation, ensure_ascii=False)),
    )
    return {"lesson_id": lesson_id, "student_id": student_id, "concept_id": concept_id,
            "concept_name": kb["concepts"][concept_id]["name"], "adaptation": adaptation, **content}


def get_lesson(lesson_id):
    row = _lesson_row(lesson_id)
    return {"lesson_id": row["id"], "student_id": row["student_id"], "concept_id": row["concept_id"],
            "adaptation": row["adaptation"], **row["content"]}


# --------------------------------------------------------------------------- #
# Practice check: performance feeds back into mastery, learned style and the next lesson
# --------------------------------------------------------------------------- #
def check_practice(lesson_id, question_index, answer, confidence_rating):
    row = _lesson_row(lesson_id)
    practice = row["content"]["practice"]
    if not 0 <= question_index < len(practice):
        raise ValueError("question_index out of range")
    kb = _kb()
    student = _student(row["student_id"])
    q = practice[question_index]
    trusted = [c["statement"] for c in kb["claims"] if c["concept_id"] == row["concept_id"]
               and c["status"] == "trusted" and c.get("claim_type") != "requirement"]

    ev = chat_json(
        CHECK_PROMPT,
        json.dumps({"question": q["question"], "model_answer": q["answer"], "trusted_claims": trusted,
                    "student_answer": answer}, ensure_ascii=False, indent=1),
        AnswerEvaluation,
    )
    low, high = SCORE_RANGE[ev.verdict]
    score = max(low, min(high, ev.score))
    misconception = ev.misconception if ev.verdict in ("incorrect", "partial") else None

    db.execute(
        "INSERT INTO lesson_checks (student_id, lesson_id, concept_id, format, level, question, answer, score) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (row["student_id"], lesson_id, row["concept_id"], row["format"], row["level"], q["question"], answer, score),
    )
    db.execute(
        "INSERT INTO attempts (student_id, concept_id, kind, question, answer, correct, misconception) "
        "VALUES (?, ?, 'quiz', ?, ?, ?, ?)",
        (row["student_id"], row["concept_id"], q["question"], answer, score, misconception),
    )

    # ---- mastery update (code) ----
    old = _mastery(row["student_id"]).get(row["concept_id"])
    new_mastery = round(blend(old["score"] if old else None, score, CHECK_WEIGHT), 3)
    old_conf = old["confidence"] if old and old["confidence"] is not None else None
    new_conf = round(blend(old_conf, confidence_to_unit(confidence_rating), CHECK_WEIGHT), 3)
    db.execute(
        "INSERT INTO mastery (student_id, concept_id, score, confidence, last_practiced) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(student_id, concept_id) DO UPDATE SET score = excluded.score, "
        "confidence = excluded.confidence, last_practiced = excluded.last_practiced",
        (row["student_id"], row["concept_id"], new_mastery, new_conf, date.today().isoformat()),
    )

    # ---- learned style (code): which format actually gives this student the best results? ----
    checks = db.rows("SELECT format, score FROM lesson_checks WHERE student_id = ?", (row["student_id"],))
    style = learned_style(checks, student["stated_style"])
    if style != student["learned_style"]:
        db.execute("UPDATE students SET learned_style = ? WHERE id = ?", (style, row["student_id"]))

    return {
        "evaluation": {**ev.model_dump(), "score": score, "misconception": misconception},
        "mastery": {"before": old["score"] if old else None, "after": new_mastery},
        "learned_style": style,
        "next_step": next_step_after_check(score, row["level"], row["format"]),
    }
