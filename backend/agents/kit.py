# Class-Ready Kit agent: turns the faculty's trusted material into a lecture outline, a handout, a quiz and an
# assignment for one topic. Class data (misconceptions, weak students) and industry requirements shape it;
# the code checks provenance, quiz answers and timing.
import json
from pathlib import Path

from backend import courses, db
from backend.models import ClassKit
from backend.tools.llm import heavy_json

TRUSTED_FILE = Path("data/trusted_kb.json")
WEAK = 0.45  # same "weak" threshold as the mastery bands

KIT_PROMPT = """You are the Class-Ready Kit agent of VidyaPath. A faculty member is teaching ONE topic tomorrow in a
{minutes}-minute class. Build their class pack from the TRUSTED FACTS of their course:
- outline: 5-8 teaching points in teaching order. Their minutes must add up to about {minutes}.
- handout: one page for students (6-10 items). Each item: origin "material" if it restates trusted facts (list their
  ids in claim_ids), origin "ai" if it is your own explanation or example (claim_ids empty).
- common_mistakes: 2-4 mistakes with corrections. Put the CLASS MISCONCEPTIONS first and mark them from_class_data.
- quiz: 6-8 questions with at least 2 easy, 2 medium and 2 hard (hard = apply or debug in a new situation). Use "mcq" (exactly 4 options, the answer copied exactly from the
  options) or "short". Add at least one question for each class misconception and mark it targets_misconception.
  No questions that give away their answer.
- assignment: 1-2 practical, interview-style tasks. Base them on the INDUSTRY REQUIREMENTS when they fit, and say
  which requirement in industry_link. Give any data or starter code needed. Write code in the course's language.
Rules: the trusted facts are the course's verified facts; never contradict them and never use outdated claims.
Explanations and examples may use standard textbook knowledge, but must not add facts about specific product versions
or vendors that are not in the trusted facts. Never write fact ids like (claim_5) in any text. Write in clear English.
"""


def _kb():
    return json.loads(TRUSTED_FILE.read_text(encoding="utf-8"))


def class_insight(concept_id):
    """How the class is doing on this topic, calculated in code (not by the model)."""
    mastery = db.rows("SELECT student_id, score FROM mastery WHERE concept_id = ?", (concept_id,))
    rows = db.rows("SELECT student_id, misconception FROM attempts WHERE concept_id = ? AND misconception IS NOT NULL",
                   (concept_id,))
    with_misconception = sorted({r["student_id"] for r in rows})
    assessed = sorted({r["student_id"] for r in mastery} | set(with_misconception))
    return {
        "students_assessed": len(assessed),
        "students_weak": sum(1 for r in mastery if r["score"] < WEAK),
        "students_with_misconceptions": len(with_misconception),
        "average_mastery": round(sum(r["score"] for r in mastery) / len(mastery), 2) if mastery else None,
        "misconceptions": list(dict.fromkeys(r["misconception"] for r in rows))[:8],
    }


def generate_kit(concept_id, class_minutes=50, created_by="faculty"):
    kb = _kb()
    if concept_id not in kb["concepts"]:
        raise ValueError(f"Unknown concept {concept_id}")
    prereqs = [p["before"] for p in kb["prerequisites"] if p["after"] == concept_id]
    scope = {concept_id, *prereqs}
    trusted = [c for c in kb["claims"] if c["status"] == "trusted"]
    facts = [c for c in trusted if c["concept_id"] in scope and c.get("claim_type") != "requirement"]
    facts_by_id = {c["id"]: c for c in facts}
    requirements = [c["statement"] for c in trusted if c.get("claim_type") == "requirement"]
    insight = class_insight(concept_id)

    kit = heavy_json(KIT_PROMPT.format(minutes=class_minutes), json.dumps({
        "course": courses.COURSES[courses.active_course()]["title"],
        "topic": kb["concepts"][concept_id]["name"],
        "topic_description": kb["concepts"][concept_id]["description"],
        "prerequisites": [kb["concepts"][p]["name"] for p in prereqs],
        "trusted_facts": [{"id": c["id"], "concept": c["concept_id"], "fact": c["statement"]} for c in facts],
        "class_misconceptions": insight["misconceptions"],
        "class_summary": {k: v for k, v in insight.items() if k != "misconceptions"},
        "industry_requirements": requirements,
    }, ensure_ascii=False, indent=1), ClassKit)

    # ---- Checks in code ----
    sources_by_id = {s["id"]: s for s in kb["sources"]}
    handout = []
    for item in kit.handout:
        ids = [i for i in item.claim_ids if i in facts_by_id]
        material = item.origin == "material" and bool(ids)
        handout.append({
            "heading": (item.heading or "").strip() or None,
            "text": item.text,
            "origin": "material" if material else "ai",
            "sources": [{"source": sources_by_id.get(facts_by_id[i]["source_id"], {}).get("title", facts_by_id[i]["source_id"]),
                         "page": facts_by_id[i]["page"], "quote": facts_by_id[i]["quote"]} for i in ids] if material else [],
        })
    quiz, warnings = [], []
    for q in kit.quiz:
        options = q.options if q.kind == "mcq" else []
        if q.kind == "mcq" and q.answer not in options:  # the answer must be one of the options
            match = next((o for o in options if o.strip().lower() == q.answer.strip().lower()), None)
            if not match:
                warnings.append(f"Dropped a multiple-choice question whose answer was not among its options: {q.question[:60]}")
                continue
            q = q.model_copy(update={"answer": match})
        item = {**q.model_dump(), "options": options}
        if not insight["misconceptions"]:
            item["targets_misconception"] = False  # nothing to target without class data
        quiz.append(item)
    total = sum(p.minutes for p in kit.outline)
    if abs(total - class_minutes) > 10:
        warnings.append(f"The outline adds up to {total} minutes for a {class_minutes}-minute class.")
    levels = {q["difficulty"] for q in quiz}
    if len(levels) < 3:
        warnings.append(f"The quiz only has {', '.join(sorted(levels))} questions.")

    material_chars = sum(len(h["text"]) for h in handout if h["origin"] == "material")
    content = {
        "title": kit.title,
        "concept_id": concept_id,
        "concept_name": kb["concepts"][concept_id]["name"],
        "course": courses.COURSES[courses.active_course()]["title"],
        "class_minutes": class_minutes,
        "outline": [p.model_dump() for p in kit.outline],
        "outline_minutes": total,
        "handout_title": kit.handout_title,
        "handout": handout,
        "material_share_percent": round(100 * material_chars / max(1, sum(len(h["text"]) for h in handout))),
        "common_mistakes": [{**m.model_dump(), "from_class_data": m.from_class_data and bool(insight["misconceptions"])}
                            for m in kit.common_mistakes],
        "quiz": quiz,
        "assignment": [a.model_dump() for a in kit.assignment],
        "class_insight": insight,
        "warnings": warnings,
    }
    kit_id = db.execute("INSERT INTO class_kits (concept_id, class_minutes, content, created_by) VALUES (?, ?, ?, ?)",
                        (concept_id, class_minutes, json.dumps(content, ensure_ascii=False), created_by))
    return {"id": kit_id, **content}


def list_kits(limit=20):
    rows = db.rows("SELECT id, concept_id, class_minutes, content, created_at FROM class_kits ORDER BY id DESC LIMIT ?", (limit,))
    return [{"id": r["id"], "concept_id": r["concept_id"], "class_minutes": r["class_minutes"],
             "title": json.loads(r["content"])["title"], "created_at": r["created_at"]} for r in rows]


def get_kit(kit_id):
    found = db.rows("SELECT * FROM class_kits WHERE id = ?", (kit_id,))
    if not found:
        raise ValueError("Unknown kit")
    return {"id": found[0]["id"], **json.loads(found[0]["content"])}
