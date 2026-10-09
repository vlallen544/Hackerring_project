# Viva agent: adaptive spoken-style diagnostic. Asks, evaluates, probes vague answers, detects misconceptions,
# then writes per-concept mastery + confidence to the database.
import json
from datetime import date
from pathlib import Path

import networkx as nx

from backend import db
from backend.engine.mastery import blend, calibration, concept_score, confidence_to_unit, mastery_band
from backend.models import AnswerEvaluation, QuestionReviews, VivaOpeners
from backend.tools.agnes_client import chat_json

TRUSTED_FILE = Path("data/trusted_kb.json")
MAX_CONCEPTS = 4            # concepts tested per viva (keeps the demo short)
MAX_FOLLOW_UPS = 1          # extra probing questions allowed per concept

# The LLM gives the verdict, the CODE keeps the score consistent with it
SCORE_RANGE = {"correct": (0.75, 1.0), "partial": (0.40, 0.74), "vague": (0.15, 0.45), "incorrect": (0.0, 0.35)}

OPENER_PROMPT = """You are the Viva agent of VidyaPath, conducting a short spoken diagnostic interview
with a college student preparing for a {role} role.
For EACH concept given, write ONE opening question:
- Conversational, like a friendly interviewer speaking aloud. Answerable in 2-4 sentences.
- Test understanding, not memorised definitions (ask "why", "when would you", "what is the difference").
- Base it ONLY on the TRUSTED FACTS provided for that concept.
- NEVER include the answer, the key terms of the answer, or hints that give it away in the question.
  Do not presuppose the answer either ("why can't X..." tells the student that X is not possible).
  BAD:  "Why can't we use AVG inside a WHERE clause?"  (reveals that it is not allowed)
  GOOD: "If you want only the groups whose average is above 100, which clause would you use, and why?"
- Write the question in clear, simple English.
Return the questions in the same order as the concepts."""

REVIEW_PROMPT = """You are a strict exam reviewer. Assume every question leaks until you have checked it.
For each viva question you get the question and the expected points of a good answer.
A question LEAKS if it states, presupposes or hints at any expected point. Examples of leaks:
  - saying an approach fails or is not allowed ("you put AVG in WHERE but it fails, explain why")
  - narrowing the choice to the right answer ("a specific type of outer join")
  - explaining the reason that the student is supposed to give ("since GROUP BY removes the rows")
  - asking yes/no about a practice in a way that signals the answer ("is it good practice to ...?")
For each question, FIRST fill gives_away with the exact leaking words (or null), THEN write the question:
unchanged if nothing leaks, otherwise rewritten as a neutral scenario that tests the same expected points.
Every question must be in clear, simple English. Keep the conversational style. Return every concept_id, in the same order."""

EVAL_PROMPT = """You are the Viva agent of VidyaPath, evaluating one spoken answer from a student.
Grade ONLY against the TRUSTED FACTS and expected points. Do not penalise grammar or spelling mistakes.
Verdicts:
- correct: covers the key points accurately.
- partial: some key points right, some missing.
- vague: generic or hand-wavy, avoids specifics ("it is used to connect tables").
- incorrect: states something wrong.
If the answer reveals a specific wrong belief (for example "AVG can be used in WHERE"), write it as a misconception.
If the answer shows the student does not understand a PREREQUISITE concept, give that concept's id.
For vague or partial answers, write ONE follow-up question that probes the same concept more specifically.
Write feedback and the follow-up question in clear, simple English. Be encouraging."""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _kb():
    return json.loads(TRUSTED_FILE.read_text(encoding="utf-8"))


def _trusted_facts(kb, concept_id):
    """Only TRUSTED claims are used, so students are never graded against outdated notes."""
    return [c["statement"] for c in kb["claims"] if c["concept_id"] == concept_id and c["status"] == "trusted"]


def _graph(kb):
    g = nx.DiGraph()
    g.add_nodes_from(kb["concepts"])
    g.add_edges_from((p["before"], p["after"]) for p in kb["prerequisites"])
    return g


def pick_concepts(kb, limit=MAX_CONCEPTS):
    """Diagnose the most foundational concepts first: those that the most other concepts depend on."""
    g = _graph(kb)
    testable = [c for c in kb["concepts"] if _trusted_facts(kb, c)]
    ranked = sorted(testable, key=lambda c: len(nx.descendants(g, c)), reverse=True)[:limit]
    order = {c: i for i, c in enumerate(kb["learning_order"])}
    return sorted(ranked, key=lambda c: order.get(c, 99))


def _student(student_id):
    found = db.rows("SELECT * FROM students WHERE id = ?", (student_id,))
    if not found:
        raise ValueError(f"Unknown student {student_id}")
    return found[0]


def _save(session_id, state, status="active"):
    db.execute("UPDATE viva_sessions SET state = ?, status = ? WHERE id = ?",
               (json.dumps(state, ensure_ascii=False), status, session_id))


def _load(session_id):
    found = db.rows("SELECT * FROM viva_sessions WHERE id = ?", (session_id,))
    if not found:
        raise ValueError(f"Unknown viva session {session_id}")
    return found[0], json.loads(found[0]["state"])


def _public_question(state):
    q = state["current"]
    return {
        "concept_id": q["concept_id"],
        "concept_name": state["concept_names"][q["concept_id"]],
        "question": q["question"],
        "is_follow_up": q["is_follow_up"],
        "progress": {"concept": state["concepts"].index(q["concept_id"]) + 1, "of": len(state["concepts"])},
    }


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def start_viva(student_id, concepts=None):
    student = _student(student_id)
    kb = _kb()
    concepts = [c for c in (concepts or pick_concepts(kb)) if c in kb["concepts"]]
    if not concepts:
        raise ValueError("No testable concepts found. Build the course first.")

    # ONE call writes the opening question for every concept (saves rate limit)
    payload = [{"concept_id": c, "concept": kb["concepts"][c]["name"], "trusted_facts": _trusted_facts(kb, c)}
               for c in concepts]
    openers = chat_json(
        OPENER_PROMPT.format(role=student["target_role"]),
        "CONCEPTS:\n" + json.dumps(payload, ensure_ascii=False, indent=1),
        VivaOpeners,
    )
    by_concept = {q.concept_id: q for q in openers.questions}
    # Second pass: an independent reviewer rewrites any question that gives its answer away
    reviewed = chat_json(REVIEW_PROMPT,
                         json.dumps([q.model_dump() for q in openers.questions], ensure_ascii=False, indent=1),
                         QuestionReviews)
    for r in reviewed.reviews:
        if r.concept_id in by_concept:  # ignore anything the reviewer invented; keep the original expected points
            by_concept[r.concept_id] = by_concept[r.concept_id].model_copy(update={"question": r.question})
    queue = []
    for c in concepts:
        if c in by_concept:
            queue.append({"concept_id": c, "question": by_concept[c].question,
                          "expected_points": by_concept[c].expected_points, "is_follow_up": False})
        else:  # model skipped or misspelled this concept: use a safe fallback question
            queue.append({"concept_id": c,
                          "question": f"In your own words, explain {kb['concepts'][c]['name']} and give one example.",
                          "expected_points": _trusted_facts(kb, c)[:3], "is_follow_up": False})
    state = {
        "student_id": student_id,
        "concepts": [q["concept_id"] for q in queue],
        "concept_names": {c: kb["concepts"][c]["name"] for c in concepts},
        "current": queue[0],
        "queue": queue[1:],
        "follow_ups": {},
        "scores": {},
        "confidences": {},
        "misconceptions": [],
        "missing_prerequisites": [],
        "transcript": [],
    }
    session_id = db.execute("INSERT INTO viva_sessions (student_id, state) VALUES (?, ?) RETURNING id",
                            (student_id, json.dumps(state, ensure_ascii=False)))
    return {"session_id": session_id, "student": student["name"], **_public_question(state)}


def answer_viva(session_id, answer, confidence_rating):
    row, state = _load(session_id)
    if row["status"] != "active":
        raise ValueError("This viva is already finished")
    kb = _kb()
    q = state["current"]
    cid = q["concept_id"]

    evaluation = chat_json(
        EVAL_PROMPT,
        json.dumps({
            "concept": kb["concepts"][cid]["name"],
            "trusted_facts": _trusted_facts(kb, cid),
            "expected_points": q["expected_points"],
            "known_prerequisite_ids": sorted(nx.ancestors(_graph(kb), cid)),
            "question": q["question"],
            "student_answer": answer,
        }, ensure_ascii=False, indent=1),
        AnswerEvaluation,
    )
    low, high = SCORE_RANGE[evaluation.verdict]
    score = max(low, min(high, evaluation.score))  # score must agree with the verdict
    confidence = confidence_to_unit(confidence_rating)

    # A misconception is a FALSE statement, so only keep it for incorrect/partial answers
    misconception = evaluation.misconception if evaluation.verdict in ("incorrect", "partial") else None
    # Accept a missing prerequisite only if it really is a prerequisite in the graph
    prereq = evaluation.missing_prerequisite
    if prereq not in nx.ancestors(_graph(kb), cid):
        prereq = None

    state["scores"].setdefault(cid, []).append(score)
    state["confidences"].setdefault(cid, []).append(confidence)
    if misconception:
        state["misconceptions"].append({"concept_id": cid, "misconception": misconception})
    if prereq:
        state["missing_prerequisites"].append({"concept_id": cid, "prerequisite": prereq})
    state["transcript"].append({"concept_id": cid, "question": q["question"], "answer": answer,
                                "verdict": evaluation.verdict, "score": score, "confidence": confidence})
    db.execute(
        "INSERT INTO attempts (student_id, concept_id, kind, question, answer, correct, misconception) "
        "VALUES (?, ?, 'viva', ?, ?, ?, ?)",
        (state["student_id"], cid, q["question"], answer, score, misconception),
    )

    # ---- Adaptive decision: probe deeper, or move on? ----
    used = state["follow_ups"].get(cid, 0)
    if evaluation.verdict in ("vague", "partial") and evaluation.follow_up_question and used < MAX_FOLLOW_UPS:
        state["follow_ups"][cid] = used + 1
        state["current"] = {"concept_id": cid, "question": evaluation.follow_up_question,
                            "expected_points": q["expected_points"], "is_follow_up": True}
        decision = f"Answer was {evaluation.verdict}: asking a follow-up on the same concept."
    elif state["queue"]:
        state["current"] = state["queue"].pop(0)
        decision = "Moving to the next concept."
    else:
        _save(session_id, state, status="done")
        return {"evaluation": {**evaluation.model_dump(), "score": score, "misconception": misconception,
                               "missing_prerequisite": prereq},
                "agent_decision": "Viva complete.",
                "done": True, "summary": finish_viva(state)}

    _save(session_id, state)
    return {"evaluation": {**evaluation.model_dump(), "score": score, "misconception": misconception,
                           "missing_prerequisite": prereq},
            "agent_decision": decision, "done": False,
            "next": _public_question(state)}


def finish_viva(state):
    """Writes mastery + confidence per concept (calculated in code) and returns the summary."""
    sid = state["student_id"]
    today = date.today().isoformat()
    previous = {r["concept_id"]: r["score"] for r in db.rows("SELECT * FROM mastery WHERE student_id = ?", (sid,))}

    results = []
    for cid in state["concepts"]:
        new = concept_score(state["scores"].get(cid, []))
        if new is None:
            continue
        mastery = round(blend(previous.get(cid), new), 3)
        conf = round(sum(state["confidences"][cid]) / len(state["confidences"][cid]), 3)
        db.execute(
            "INSERT INTO mastery (student_id, concept_id, score, confidence, last_practiced) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(student_id, concept_id) DO UPDATE SET score = excluded.score, "
            "confidence = excluded.confidence, last_practiced = excluded.last_practiced",
            (sid, cid, mastery, conf, today),
        )
        results.append({
            "concept_id": cid,
            "concept_name": state["concept_names"][cid],
            "mastery": mastery,
            "band": mastery_band(mastery),
            "confidence": conf,
            "calibration": calibration(conf, mastery),
        })

    return {
        "student_id": sid,
        "results": results,
        "misconceptions": state["misconceptions"],
        "missing_prerequisites": state["missing_prerequisites"],
        "transcript": state["transcript"],
    }
