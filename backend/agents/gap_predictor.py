# Gap Predictor agent: builds each student's learning path, predicts which upcoming concepts they will struggle
# with, and redesigns the path BEFORE the gap appears (refresher inserted, format switched, challenge track).
# Predictions and decisions are made in code; the LLM only writes the friendly explanation.
import json
from datetime import date, timedelta
from pathlib import Path

from backend import db
from backend.engine.adapt import ALTERNATIVE_FORMAT, decide_format, decide_level
from backend.engine.risk import (RISK_THRESHOLD, STRONG, all_prereqs_strong, concept_risk, own_risk, pace_lag,
                                 risk_band)
from backend.models import GapNudge
from backend.tools.agnes_client import chat_json

TRUSTED_FILE = Path("data/trusted_kb.json")
COURSE_DAYS = 28            # days until the exam / placement drive (demo default)

NUDGE_PROMPT = """You are the Gap Predictor agent of VidyaPath. The system has predicted that a student is likely
to struggle with upcoming topics and has ALREADY changed their learning path. Explain the change kindly and
specifically: which topic is coming, which earlier topic needs strengthening, and what was added.
Mention EVERY change in the list (each refresher and each challenge move). Do not invent changes.
A refresher means the student is WEAK in that earlier topic: say clearly it NEEDS more practice before the
upcoming topic. Never say a refreshed topic is already strong. A challenge move means the student is ready for
harder, interview-level practice.
Write student_message in clear, friendly English. Use only the facts given: quote dates as they are given
(do not turn them into "tomorrow" or weekdays) and do not add durations, times or other details."""


def _kb():
    return json.loads(TRUSTED_FILE.read_text(encoding="utf-8"))


def _student(student_id):
    found = db.rows("SELECT * FROM students WHERE id = ?", (student_id,))
    if not found:
        raise ValueError(f"Unknown student {student_id}")
    return found[0]


def _prereqs(kb):
    out = {}
    for p in kb["prerequisites"]:
        out.setdefault(p["after"], []).append(p["before"])
    return out


def _mastery(student_id):
    return {r["concept_id"]: r for r in db.rows("SELECT * FROM mastery WHERE student_id = ?", (student_id,))}


def _misconceptions(student_id):
    """Concepts with misconceptions recorded since the last correct answer (same rule as the Tutor)."""
    from backend.agents.tutor import _active_misconceptions

    concepts = {r["concept_id"] for r in db.rows(
        "SELECT DISTINCT concept_id FROM attempts WHERE student_id = ? AND misconception IS NOT NULL", (student_id,))}
    return {c: _active_misconceptions(student_id, c) for c in concepts}


def _path(student_id):
    return db.rows("SELECT * FROM path_items WHERE student_id = ? ORDER BY position", (student_id,))


def _a(word):
    return f"an {word}" if word[:1].lower() in "aeiou" else f"a {word}"


def _pct(value):
    """Percent rounded half up (68.5 -> 69), matching the UI. Python's round() would give 68."""
    return int(value * 100 + 0.5)


def _name(kb, cid):
    return kb["concepts"].get(cid, {}).get("name", cid)


# --------------------------------------------------------------------------- #
# 1. Build the initial path (prerequisite order, spread over the course)
# --------------------------------------------------------------------------- #
def build_path(student_id, course_days=COURSE_DAYS):
    if _path(student_id):
        return _path(student_id)  # never rebuild over a student's progress
    kb = _kb()
    student = _student(student_id)
    fmt, _ = decide_format(student["stated_style"], student["learned_style"])
    order = kb["learning_order"]
    step = max(1, course_days // max(1, len(order)))
    for i, cid in enumerate(order):
        db.execute(
            "INSERT INTO path_items (student_id, position, concept_id, kind, format, status, reason, scheduled_for) "
            "VALUES (?, ?, ?, 'lesson', ?, 'pending', ?, ?)",
            (student_id, (i + 1) * 10, cid, fmt, "Planned in prerequisite order.",
             (date.today() + timedelta(days=(i + 1) * step)).isoformat()),
        )
    return _path(student_id)


# --------------------------------------------------------------------------- #
# 2. Gap Radar: risk for every upcoming concept (read-only, no LLM)
# --------------------------------------------------------------------------- #
def gap_radar(student_id):
    kb = _kb()
    _student(student_id)
    path = build_path(student_id)
    mastery = _mastery(student_id)
    if not mastery:
        return []  # not yet assessed: no evidence, so no predictions (frontend shows "take the viva first")
    miscon = _misconceptions(student_id)
    prereqs = _prereqs(kb)
    lag = pace_lag(path)

    radar = []
    for item in path:
        cid = item["concept_id"]
        if item["kind"] != "lesson" or item["status"] == "done":
            continue
        if cid in mastery and mastery[cid]["score"] >= STRONG:
            continue  # already strong, nothing to predict
        p_risk, p_factors, p_weakest = concept_risk(prereqs.get(cid, []), mastery, miscon, lag)
        own = own_risk(cid, mastery, miscon, lag)
        if p_weakest is None and own is None:
            continue

        def status(c):
            return "untested" if c not in mastery else f"at {mastery[c]['score']:.2f}"

        prereq_chain = None
        if p_weakest is not None:
            misc = " with an active misconception" if p_factors["misconception"] else ""
            prereq_chain = (f"{_name(kb, p_weakest)} is {status(p_weakest)}{misc} -> {_name(kb, cid)} on "
                            f"{item['scheduled_for']} -> risk {_pct(p_risk)}%")

        # The radar shows the BIGGER problem; refreshers are decided from the prerequisite risk alone.
        if own is not None and (p_weakest is None or own[0] > p_risk):
            risk, factors = own
            level, _ = decide_level(mastery[cid]["score"], {})  # same rule the Tutor uses
            misc = " with an active misconception" if factors["misconception"] else ""
            cause, shown_weakest = "own", cid
            chain = (f"{_name(kb, cid)} itself is {status(cid)}{misc} -> lesson on {item['scheduled_for']} "
                     f"will be taught at {level} level -> risk {_pct(risk)}%")
        else:
            risk, factors, cause, shown_weakest, chain = p_risk, p_factors, "prerequisite", p_weakest, prereq_chain

        radar.append({
            "path_item_id": item["id"],
            "concept_id": cid,
            "concept_name": _name(kb, cid),
            "scheduled_for": item["scheduled_for"],
            "risk": risk,
            "band": risk_band(risk),
            "factors": factors,
            "weakest_prerequisite": shown_weakest,
            "cause": cause,
            "reason_chain": chain,
            # always kept separately, so refresher timing never depends on which risk is shown
            "prerequisite_risk": p_risk if p_weakest is not None else 0.0,
            "prerequisite_weakest": p_weakest,
            "prerequisite_chain": prereq_chain,
        })
    return sorted(radar, key=lambda r: r["risk"], reverse=True)


# --------------------------------------------------------------------------- #
# 3. Predict and redesign (proactive): act on high risk before the concept is reached
# --------------------------------------------------------------------------- #
def _shift_after(student_id, position):
    db.execute("UPDATE path_items SET position = position + 1 WHERE student_id = ? AND position >= ?",
               (student_id, position))


def predict_and_redesign(student_id):
    kb = _kb()
    student = _student(student_id)
    radar = gap_radar(student_id)
    mastery = _mastery(student_id)
    prereqs = _prereqs(kb)
    path = _path(student_id)
    actions = []

    # ---- High risk: insert a refresher on the weakest prerequisite, one day before the risky concept ----
    position = {p["id"]: p["position"] for p in path}
    for r in sorted(radar, key=lambda x: position[x["path_item_id"]]):  # earliest upcoming topic first
        if r["prerequisite_weakest"] is None or r["prerequisite_risk"] < RISK_THRESHOLD:
            continue  # refreshers fix weak PREREQUISITES; a topic's own weakness is handled by the Tutor's level
        target = next(p for p in _path(student_id) if p["id"] == r["path_item_id"])
        weak = r["prerequisite_weakest"]
        already = any(p["kind"] == "refresher" and p["concept_id"] == weak and p["status"] != "done"
                      and p["position"] < target["position"] for p in _path(student_id))
        if already:
            continue

        fmt, _ = decide_format(student["stated_style"], student["learned_style"])
        failed = db.rows("SELECT 1 FROM lesson_checks WHERE student_id = ? AND concept_id = ? AND format = ? "
                         "AND score < 0.4", (student_id, weak, fmt))
        fmt_note = ""
        if failed:  # this format already failed on this prerequisite: switch
            fmt_note = f" ({fmt} did not work before, so switched to {ALTERNATIVE_FORMAT[fmt]})"
            fmt = ALTERNATIVE_FORMAT[fmt]

        when = (date.fromisoformat(target["scheduled_for"]) - timedelta(days=1))
        when = max(when, date.today()).isoformat()
        reason = f"{r['prerequisite_chain']} -> added {_a(fmt)} refresher on {_name(kb, weak)} for {when}{fmt_note}"
        _shift_after(student_id, target["position"])
        db.execute(
            "INSERT INTO path_items (student_id, position, concept_id, kind, format, status, reason, scheduled_for) "
            "VALUES (?, ?, ?, 'refresher', ?, 'pending', ?, ?)",
            (student_id, target["position"], weak, fmt, reason, when),
        )
        db.execute("INSERT INTO risk_events (student_id, concept_id, risk, action, reason) VALUES (?, ?, ?, ?, ?)",
                   (student_id, r["concept_id"], r["prerequisite_risk"], f"refresher:{weak}", reason))
        actions.append({"type": "refresher", "for_concept": r["concept_id"], "refresher_on": weak,
                        "format": fmt, "scheduled_for": when, "risk": r["prerequisite_risk"], "reason": reason})

    # ---- Very strong prerequisites: move upcoming lessons to a challenge track ----
    for item in _path(student_id):
        if item["kind"] != "lesson" or item["status"] == "done":
            continue
        cid = item["concept_id"]
        own = mastery[cid]["score"] if cid in mastery else None
        if own is not None and own < STRONG:
            continue  # the student is not strong in this concept itself, so no challenge track
        if all_prereqs_strong(prereqs.get(cid, []), mastery):
            reason = (f"All prerequisites of {_name(kb, cid)} are strong (>= 0.85) -> moved to the challenge track "
                      f"with interview-level practice.")
            db.execute("UPDATE path_items SET kind = 'challenge', reason = ? WHERE id = ?", (reason, item["id"]))
            db.execute("INSERT INTO risk_events (student_id, concept_id, risk, action, reason) VALUES (?, ?, ?, ?, ?)",
                       (student_id, cid, 0.0, "challenge_track", reason))
            actions.append({"type": "challenge", "for_concept": cid, "reason": reason})

    nudge = None
    if actions:  # the LLM only explains decisions that were already made in code
        nudge = chat_json(
            NUDGE_PROMPT,
            json.dumps({"student": student["name"], "changes": actions}, ensure_ascii=False, indent=1),
            GapNudge,
        ).model_dump()

    return {"student_id": student_id, "actions": actions, "message": nudge,
            "gap_radar": gap_radar(student_id), "path": _path(student_id)}


def complete_item(student_id, item_id):
    found = db.rows("SELECT * FROM path_items WHERE id = ? AND student_id = ?", (item_id, student_id))
    if not found:
        raise ValueError("Unknown path item")
    db.execute("UPDATE path_items SET status = 'done' WHERE id = ?", (item_id,))
    return _path(student_id)


# --------------------------------------------------------------------------- #
# 4. Class view for faculty: who is at risk on what (read-only, no LLM)
# --------------------------------------------------------------------------- #
def class_radar():
    students = db.rows("SELECT id, name FROM students ORDER BY name")
    by_concept = {}
    not_assessed = []
    for s in students:
        radar = gap_radar(s["id"])
        if not _mastery(s["id"]):
            not_assessed.append(s["name"])
            continue
        for r in radar:
            entry = by_concept.setdefault(r["concept_id"], {"concept_id": r["concept_id"],
                                                            "concept_name": r["concept_name"], "students": []})
            entry["students"].append({"student_id": s["id"], "name": s["name"], "risk": r["risk"], "band": r["band"],
                                      "weakest_prerequisite": r["weakest_prerequisite"]})
    out = []
    for e in by_concept.values():
        e["high_risk_count"] = sum(1 for s in e["students"] if s["band"] == "high")
        e["students"].sort(key=lambda s: s["risk"], reverse=True)
        out.append(e)
    return {"concepts": sorted(out, key=lambda e: e["high_risk_count"], reverse=True), "not_assessed": not_assessed}
