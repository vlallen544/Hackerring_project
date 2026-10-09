# Placement Readiness Forecast: for every job role in the course, which students are ready for the drive, which are on
# track, which are at risk, and what holds them back. Pure code, no LLM: it joins the skills the Source Reconciler took
# from the job descriptions (freshness report) with each student's measured mastery and planned path.
import json
from datetime import date, timedelta

from backend import courses, db, storage
from backend.engine.mastery import mastery_band

READY = 0.75             # the same "strong" threshold the whole platform uses
DEFAULT_DRIVE_DAYS = 28  # until faculty set a drive date: the end of the course plan
SYLLABUS_GAP = {"missing", "outdated"}  # the faculty's own material doesn't teach it (well): a course problem


def _settings_file():
    return courses.course_file("placement.json")


def drive_date():
    """(date the drive is on, True if faculty set it)."""
    try:
        return date.fromisoformat(json.loads(_settings_file().read_text(encoding="utf-8"))["drive_date"]), True
    except (OSError, ValueError, KeyError):
        return date.today() + timedelta(days=DEFAULT_DRIVE_DAYS), False


def set_drive_date(value):
    when = date.fromisoformat(value)  # ValueError for a bad date
    path = _settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"drive_date": when.isoformat()}), encoding="utf-8")
    storage.save(path)  # survives redeploys
    return when


def _skill_status(concept_id, mastery, scheduled, drive):
    """ready: strong now · on_track: weak/untested but taught before the drive · at_risk: neither."""
    score = mastery.get(concept_id)
    if score is not None and score >= READY:
        return "ready", None
    when = min((d for d in scheduled.get(concept_id, []) if d <= drive), default=None)
    if when:
        return "on_track", when
    return "at_risk", None


def forecast():
    kb = json.loads(courses.course_file("knowledge_base.json").read_text(encoding="utf-8"))
    trusted = json.loads(courses.course_file("trusted_kb.json").read_text(encoding="utf-8"))
    drive, drive_set = drive_date()
    drive_iso = drive.isoformat()
    concept_names = {c: v["name"] for c, v in kb["concepts"].items()}
    skills = (trusted.get("freshness_report") or {}).get("skills") or []
    titles = {s["id"]: s["title"] for s in kb["sources"]}
    jd_ids = [s["id"] for s in kb["sources"] if s["type"] == "job_description"]

    students = db.rows("SELECT id, name FROM students ORDER BY name")
    mastery = {}
    for r in db.rows("SELECT student_id, concept_id, score FROM mastery"):
        mastery.setdefault(r["student_id"], {})[r["concept_id"]] = r["score"]
    have_path = {r["student_id"] for r in db.rows("SELECT DISTINCT student_id FROM path_items")}
    if set(mastery) - have_path:  # assessed but never opened My path: plan it, as the class radar does
        from backend.agents.gap_predictor import build_path

        for sid in set(mastery) - have_path:
            build_path(sid)
    scheduled = {}  # student -> concept -> dates it is still to be taught (lesson, refresher or challenge)
    for r in db.rows("SELECT student_id, concept_id, scheduled_for FROM path_items WHERE status != 'done'"):
        if r["scheduled_for"]:
            scheduled.setdefault(r["student_id"], {}).setdefault(r["concept_id"], []).append(r["scheduled_for"])

    roles = []
    for jd in jd_ids:
        demanded = [s for s in skills if jd in s.get("demanded_by", [])]
        if not demanded:
            continue
        measurable = [s for s in demanded if s.get("concept_id") in concept_names]  # skills the course teaches
        role_skills = [{"skill": s["skill"], "concept_id": s.get("concept_id"),
                        "concept_name": concept_names.get(s.get("concept_id")),
                        "coverage": s.get("faculty_coverage"), "note": s.get("note", ""),
                        "in_course": s in measurable} for s in demanded]

        rows, counts = [], {"ready": 0, "on_track": 0, "at_risk": 0, "not_assessed": 0}
        not_ready_by_skill = {s["skill"]: 0 for s in measurable}
        for st in students:
            m = mastery.get(st["id"], {})
            per_skill = []
            for s in measurable:
                cid = s["concept_id"]
                status, when = _skill_status(cid, m, scheduled.get(st["id"], {}), drive_iso)
                per_skill.append({"skill": s["skill"], "concept_id": cid, "status": status,
                                  "mastery": m.get(cid), "band": mastery_band(m[cid]) if cid in m else None,
                                  "scheduled_for": when})
                if status != "ready":
                    not_ready_by_skill[s["skill"]] += 1
            if not m:
                status = "not_assessed"  # no viva yet: no evidence either way
            elif all(p["status"] == "ready" for p in per_skill):
                status = "ready"
            elif any(p["status"] == "at_risk" for p in per_skill):
                status = "at_risk"
            else:
                status = "on_track"
            counts[status] += 1
            readiness = (sum(min((p["mastery"] or 0) / READY, 1) for p in per_skill) / len(per_skill)) if per_skill else None
            rows.append({"id": st["id"], "name": st["name"], "status": status,
                         "readiness": round(readiness, 3) if readiness is not None else None, "skills": per_skill})

        total = len(students)
        gaps = []
        for s in role_skills:
            if s["in_course"]:
                blocked = not_ready_by_skill[s["skill"]]
            else:
                blocked = total  # no topic in the course teaches it: nobody can get ready here
            syllabus_gap = not s["in_course"] or s["coverage"] in SYLLABUS_GAP
            if blocked or syllabus_gap:
                gaps.append({**s, "students_not_ready": blocked, "syllabus_gap": syllabus_gap})
        gaps.sort(key=lambda g: (g["students_not_ready"], g["syllabus_gap"]), reverse=True)

        roles.append({
            "id": jd,
            "title": titles.get(jd, jd).removeprefix("JD:").strip(),
            "skills": role_skills,
            "counts": counts,
            "total": total,
            "percent": {k: round(100 * v / total) if total else 0 for k, v in counts.items()},
            "gaps": gaps,
            "students": sorted(rows, key=lambda r: ({"at_risk": 0, "on_track": 1, "ready": 2, "not_assessed": 3}[r["status"]],
                                                    r["readiness"] or 0)),
        })

    return {"course": courses.COURSES[courses.active_course()]["title"], "drive_date": drive_iso,
            "drive_date_set": drive_set, "days_to_drive": (drive - date.today()).days,
            "ready_threshold": READY, "roles": roles}
