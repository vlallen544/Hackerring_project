# Doubt Assistant: answers a student's question ONLY from the course's trusted facts, with citations.
# The model answers; the code checks the citations and turns any answer without real citations into a decline.
import json
import re
from pathlib import Path

from backend import courses, db
from backend.models import DoubtAnswer
from backend.tools.agnes_client import chat_json

MAX_FACTS = 120           # large courses (PDF books): send the most relevant facts only
HISTORY_LIMIT = 30

DOUBT_PROMPT = """You are the Doubt Assistant of VidyaPath, helping one college student with a question about their course.
Answer using ONLY the TRUSTED FACTS given. They are the course's verified facts.
- If the facts contain what is needed, set answerable true, explain clearly in 1-3 short paragraphs of simple English,
  and list the ids of the facts you used in claim_ids.
- If the facts do not cover the question (or it is not about this course), set answerable false, say briefly that it
  is not covered by the course material, leave claim_ids empty and suggest the closest course concept in closest_topic.
  Never answer from outside knowledge and never guess.
- Never contradict the trusted facts. Never write fact ids like (claim_5) in the answer text.
- Pitch the explanation at the student's level (their mastery of the concept is given). If one of the student's
  known misconceptions is related, gently correct it.
- Give a short example only if it helps and agrees with the facts: a few lines of code in the course's language,
  or a small worked example.
- Suggest 2-3 short follow-up questions the student could ask next.
"""


def _kb():
    return json.loads(courses.course_file("trusted_kb.json").read_text(encoding="utf-8"))


def _words(text):
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}


def _relevant_facts(kb, question, concept_id):
    """Trusted teaching facts (not job requirements); for very large courses, the ones closest to the question."""
    facts = [c for c in kb["claims"] if c["status"] == "trusted" and c.get("claim_type") != "requirement"]
    if len(facts) <= MAX_FACTS:
        return facts
    q = _words(question)

    def score(c):
        name = kb["concepts"].get(c["concept_id"], {}).get("name", "")
        return len(q & _words(c["statement"] + " " + name)) + (5 if c["concept_id"] == concept_id else 0)

    return sorted(facts, key=score, reverse=True)[:MAX_FACTS]


def answer_doubt(student_id, question, concept_id=None):
    kb = _kb()
    found = db.rows("SELECT * FROM students WHERE id = ?", (student_id,))
    if not found:
        raise ValueError(f"Unknown student {student_id}")
    student = found[0]
    if concept_id and concept_id not in kb["concepts"]:
        raise ValueError(f"Unknown concept {concept_id}")

    facts = _relevant_facts(kb, question, concept_id)
    facts_by_id = {c["id"]: c for c in facts}
    mastery = {r["concept_id"]: r["score"] for r in db.rows("SELECT * FROM mastery WHERE student_id = ?", (student_id,))}
    misconceptions = [r["misconception"] for r in db.rows(
        "SELECT misconception FROM attempts WHERE student_id = ? AND misconception IS NOT NULL "
        "GROUP BY misconception ORDER BY MAX(id) DESC LIMIT 5", (student_id,))]  # the 5 most recent, no repeats

    result = chat_json(DOUBT_PROMPT, json.dumps({
        "course": courses.COURSES[courses.active_course()]["title"],
        "student_target_role": student["target_role"],
        "question": question,
        "topic_chosen_by_student": kb["concepts"][concept_id]["name"] if concept_id else None,
        "concepts": {cid: c["name"] for cid, c in kb["concepts"].items()},
        "student_mastery": {kb["concepts"][c]["name"]: round(s, 2) for c, s in mastery.items() if c in kb["concepts"]},
        "student_misconceptions": misconceptions,
        "trusted_facts": [{"id": c["id"], "concept": c["concept_id"], "fact": c["statement"]} for c in facts],
    }, ensure_ascii=False, indent=1), DoubtAnswer)

    # ---- Grounding check in code: an answer counts only if it cites real trusted facts ----
    cited = [i for i in result.claim_ids if i in facts_by_id]
    answerable = result.answerable and bool(cited)
    sources_by_id = {s["id"]: s for s in kb["sources"]}
    concept = result.concept_id if result.concept_id in kb["concepts"] else concept_id
    closest = result.closest_topic if result.closest_topic in kb["concepts"] else None
    answer_text = re.sub(r"\s*\((?:claim_\d+(?:,\s*)?)+\)", "", result.answer).strip()
    if not answerable:
        answer_text = (answer_text if not result.answerable else
                       "I couldn't find this in your course material, so I won't guess.")
        answer_text += " You can ask your faculty about it."

    payload = {
        "answer": answer_text,
        "citations": [{
            "claim_id": i,
            "concept_id": facts_by_id[i]["concept_id"],
            "source": sources_by_id.get(facts_by_id[i]["source_id"], {}).get("title", facts_by_id[i]["source_id"]),
            "page": facts_by_id[i]["page"],
            "quote": facts_by_id[i]["quote"],
        } for i in cited] if answerable else [],
        "example": result.example if answerable else None,
        "closest_topic": None if answerable else (closest or concept),
        "follow_ups": result.follow_ups[:3],
    }
    doubt_id = db.execute(
        "INSERT INTO doubts (student_id, concept_id, question, answerable, answer) VALUES (?, ?, ?, ?, ?) RETURNING id",
        (student_id, concept, question, int(answerable), json.dumps(payload, ensure_ascii=False)),
    )
    return {"id": doubt_id, "question": question, "concept_id": concept, "answerable": answerable, **payload}


def doubt_history(student_id):
    rows = db.rows("SELECT * FROM doubts WHERE student_id = ? ORDER BY id DESC LIMIT ?", (student_id, HISTORY_LIMIT))
    return [{"id": r["id"], "question": r["question"], "concept_id": r["concept_id"], "answerable": bool(r["answerable"]),
             "created_at": r["created_at"], **json.loads(r["answer"])} for r in rows]
