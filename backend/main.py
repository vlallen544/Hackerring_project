# FastAPI app entry point: defines the application and API routes
import json
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import courses, db

KB_FILE = Path("data/knowledge_base.json")
TRUSTED_FILE = Path("data/trusted_kb.json")
SOURCE_TYPES = {"faculty_notes", "textbook", "job_description", "web_link"}
UI_DIR = Path("ui")


@asynccontextmanager
async def lifespan(app):
    db.init_db()  # create tables + seed demo students on startup
    yield


app = FastAPI(title="VidyaPath API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/ui", StaticFiles(directory=UI_DIR, html=True), name="ui")  # the VidyaPath web UI


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/ui/")


def _load(path):
    if not path.exists():
        raise HTTPException(404, f"{path.name} not found. Run POST /api/course/build first.")
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #
@app.get("/health")
def health():
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# Faculty: sources
# --------------------------------------------------------------------------- #
def _sources_json():
    return courses.data_dir() / "sources.json"


@app.get("/api/course")
def course_info():
    """Which course is active (switch with: python scripts/switch_course.py <name>)."""
    name = courses.active_course()
    return {"id": name, "title": courses.COURSES[name]["title"], "built": courses.is_built(),
            "available": {k: v["title"] for k, v in courses.COURSES.items()}}


class CourseSwitch(BaseModel):
    course: str


@app.post("/api/course/switch")
def switch_course(body: CourseSwitch):
    """Makes another course active. Builds it first if it has never been built (about a minute)."""
    try:
        courses.switch(body.course)
    except ValueError as err:
        raise HTTPException(400, str(err))
    db.init_db()  # each course has its own student database
    if not courses.is_built():
        from backend.agents.knowledge_builder import build_knowledge
        from backend.agents.reconciler import reconcile

        build_knowledge(str(courses.data_dir()))
        reconcile()
    return course_info()


@app.get("/api/sources")
def list_sources():
    return json.loads(_sources_json().read_text(encoding="utf-8"))["sources"]


@app.post("/api/sources/upload")
async def upload_source(
    file: UploadFile = File(...),
    title: str = Form(...),
    type: str = Form(...),
    year: int = Form(...),
):
    """Faculty uploads a new source (PDF, PPTX, MD, TXT). Then call POST /api/course/build."""
    if type not in SOURCE_TYPES:
        raise HTTPException(400, f"type must be one of {sorted(SOURCE_TYPES)}")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".pdf", ".pptx", ".md", ".txt"}:
        raise HTTPException(400, "Only PDF, PPTX, MD or TXT files are supported")

    source_id = re.sub(r"[^a-z0-9]+", "_", Path(file.filename).stem.lower()).strip("_")
    dest = courses.data_dir() / "sources" / f"{source_id}{suffix}"
    dest.write_bytes(await file.read())

    meta = json.loads(_sources_json().read_text(encoding="utf-8"))
    meta["sources"] = [s for s in meta["sources"] if s["id"] != source_id]  # replace if re-uploaded
    meta["sources"].append(
        {"id": source_id, "file": f"sources/{dest.name}", "title": title, "type": type, "year": year}
    )
    _sources_json().write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"id": source_id, "message": "Uploaded. Run POST /api/course/build to update the knowledge base."}


# --------------------------------------------------------------------------- #
# Faculty: build + knowledge base
# --------------------------------------------------------------------------- #
@app.post("/api/course/build")
def build_course():
    """Runs Knowledge Builder then Source Reconciler. Takes ~1 minute on a fresh run, instant when cached."""
    from backend.agents.knowledge_builder import build_knowledge
    from backend.agents.reconciler import reconcile

    kb = build_knowledge(str(courses.data_dir()))
    db.init_db()  # make sure the active course's student database exists
    trusted = reconcile()
    return {
        "concepts": len(kb["concepts"]),
        "claims_verified": len(kb["claims"]),
        "claims_rejected": len(kb["rejected_claims"]),
        "conflicts": len(trusted["conflicts"]),
        "freshness_score": trusted["freshness_report"]["score"],
    }


@app.get("/api/course/graph")
def course_graph():
    """Prerequisite graph in a shape React Flow (or any graph library) can use directly."""
    kb = _load(TRUSTED_FILE)
    order = {cid: i for i, cid in enumerate(kb["learning_order"])}
    return {
        "nodes": [
            {"id": cid, "label": c["name"], "description": c["description"], "order": order.get(cid, 0)}
            for cid, c in kb["concepts"].items()
        ],
        "edges": [
            {"id": f"{p['before']}->{p['after']}", "source": p["before"], "target": p["after"], "reason": p["reason"]}
            for p in kb["prerequisites"]
        ],
        "learning_order": kb["learning_order"],
    }


@app.get("/api/course/claims")
def course_claims(status: str | None = None, concept_id: str | None = None):
    """Filter with ?status=trusted|outdated|superseded|unreliable|needs_review and/or ?concept_id=..."""
    claims = _load(TRUSTED_FILE)["claims"]
    if status:
        claims = [c for c in claims if c["status"] == status]
    if concept_id:
        claims = [c for c in claims if c["concept_id"] == concept_id]
    return claims


@app.get("/api/course/rejected-claims")
def rejected_claims():
    """Claims whose quotes could not be found in the sources (hallucinations caught)."""
    return _load(KB_FILE)["rejected_claims"]


@app.get("/api/course/conflicts")
def course_conflicts():
    return _load(TRUSTED_FILE)["conflicts"]


class Override(BaseModel):
    winning_side: int


@app.post("/api/course/conflicts/{conflict_id}/override")
def override_conflict(conflict_id: str, body: Override):
    """Faculty control: choose which side of a conflict is trusted."""
    from backend.agents.reconciler import reconcile, set_faculty_override

    conflicts = {c["id"]: c for c in _load(TRUSTED_FILE)["conflicts"]}
    if conflict_id not in conflicts:
        raise HTTPException(404, "Unknown conflict")
    if not 0 <= body.winning_side < len(conflicts[conflict_id]["sides"]):
        raise HTTPException(400, "winning_side out of range")
    set_faculty_override(conflict_id, body.winning_side)
    return next(c for c in reconcile()["conflicts"] if c["id"] == conflict_id)


@app.get("/api/course/freshness")
def freshness_report():
    return _load(TRUSTED_FILE)["freshness_report"]


# --------------------------------------------------------------------------- #
# Students
# --------------------------------------------------------------------------- #
@app.get("/api/students")
def list_students():
    return db.rows("SELECT * FROM students ORDER BY name")


@app.get("/api/students/{student_id}")
def get_student(student_id: str):
    found = db.rows("SELECT * FROM students WHERE id = ?", (student_id,))
    if not found:
        raise HTTPException(404, "Unknown student")
    return {
        **found[0],
        "mastery": db.rows("SELECT * FROM mastery WHERE student_id = ?", (student_id,)),
        "path": db.rows("SELECT * FROM path_items WHERE student_id = ? ORDER BY position", (student_id,)),
        "risk_events": db.rows(
            "SELECT * FROM risk_events WHERE student_id = ? ORDER BY created_at DESC", (student_id,)
        ),
    }


@app.post("/api/demo/reset")
def demo_reset():
    """Clears all student progress (keeps students and course knowledge). Use before each demo run."""
    db.reset_student_progress()
    return {"status": "reset"}


# --------------------------------------------------------------------------- #
# Student: Viva diagnostic
# --------------------------------------------------------------------------- #
class VivaStart(BaseModel):
    concepts: list[str] | None = None  # optional: force specific concept ids (e.g. for the demo)


class VivaAnswer(BaseModel):
    answer: str
    confidence: int  # student's self-rating, 1 (not sure) to 5 (very sure)


@app.post("/api/viva/{student_id}/start")
def viva_start(student_id: str, body: VivaStart | None = None):
    from backend.agents.viva import start_viva

    try:
        return start_viva(student_id, body.concepts if body else None)
    except ValueError as err:
        raise HTTPException(400, str(err))


@app.post("/api/viva/session/{session_id}/answer")
def viva_answer(session_id: int, body: VivaAnswer):
    from backend.agents.viva import answer_viva

    if not body.answer.strip():
        raise HTTPException(400, "Answer is empty")
    try:
        return answer_viva(session_id, body.answer, body.confidence)
    except ValueError as err:
        raise HTTPException(400, str(err))


@app.get("/api/viva/session/{session_id}")
def viva_session(session_id: int):
    found = db.rows("SELECT * FROM viva_sessions WHERE id = ?", (session_id,))
    if not found:
        raise HTTPException(404, "Unknown session")
    return {**found[0], "state": json.loads(found[0]["state"])}


# --------------------------------------------------------------------------- #
# Student: personalised lessons (Tutor agent)
# --------------------------------------------------------------------------- #
class LessonRequest(BaseModel):
    concept_id: str
    level: str | None = None   # optional override: foundation / standard / challenge
    format: str | None = None  # optional override: text / audio / visual / practice
    reason: str | None = None  # optional: why it was overridden (e.g. "re-teach after wrong answer")


class PracticeAnswer(BaseModel):
    question_index: int
    answer: str
    confidence: int = 3


@app.post("/api/tutor/{student_id}/lesson")
def tutor_lesson(student_id: str, body: LessonRequest):
    from backend.agents.tutor import generate_lesson

    if body.level and body.level not in ("foundation", "standard", "challenge"):
        raise HTTPException(400, "level must be foundation, standard or challenge")
    if body.format and body.format not in ("text", "audio", "visual", "practice"):
        raise HTTPException(400, "format must be text, audio, visual or practice")
    try:
        return generate_lesson(student_id, body.concept_id, body.level, body.format, body.reason)
    except ValueError as err:
        raise HTTPException(400, str(err))


@app.get("/api/tutor/lessons/{lesson_id}")
def tutor_get_lesson(lesson_id: int):
    from backend.agents.tutor import get_lesson

    try:
        return get_lesson(lesson_id)
    except ValueError as err:
        raise HTTPException(404, str(err))


@app.post("/api/tutor/lessons/{lesson_id}/check")
def tutor_check(lesson_id: int, body: PracticeAnswer):
    from backend.agents.tutor import check_practice

    if not body.answer.strip():
        raise HTTPException(400, "Answer is empty")
    try:
        return check_practice(lesson_id, body.question_index, body.answer, body.confidence)
    except ValueError as err:
        raise HTTPException(400, str(err))


# --------------------------------------------------------------------------- #
# Gap prediction + proactive path redesign (Objective 2)
# --------------------------------------------------------------------------- #
@app.get("/api/students/{student_id}/path")
def student_path(student_id: str):
    from backend.agents.gap_predictor import build_path

    try:
        return build_path(student_id)
    except ValueError as err:
        raise HTTPException(404, str(err))


@app.get("/api/students/{student_id}/gap-radar")
def student_gap_radar(student_id: str):
    """Risk for every upcoming concept with its factors and reason chain. Read-only, instant."""
    from backend.agents.gap_predictor import gap_radar

    try:
        return gap_radar(student_id)
    except ValueError as err:
        raise HTTPException(404, str(err))


@app.post("/api/students/{student_id}/predict")
def student_predict(student_id: str):
    """Predicts gaps and redesigns the path. Call after a viva or a practice check."""
    from backend.agents.gap_predictor import predict_and_redesign

    try:
        return predict_and_redesign(student_id)
    except ValueError as err:
        raise HTTPException(404, str(err))


@app.post("/api/students/{student_id}/path/{item_id}/complete")
def student_complete_item(student_id: str, item_id: int):
    from backend.agents.gap_predictor import complete_item

    try:
        return complete_item(student_id, item_id)
    except ValueError as err:
        raise HTTPException(404, str(err))


@app.get("/api/class/gap-radar")
def class_gap_radar():
    """Faculty view: which upcoming concepts put which students at risk."""
    from backend.agents.gap_predictor import class_radar

    return class_radar()
