# FastAPI app entry point: defines the application and API routes
import hashlib
import json
import re
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import auth, autopilot, courses, db, notify, sql, storage
from backend.tools.parsers import SUPPORTED_SUFFIXES, file_sha256, inspect_file, page_texts

SOURCE_TYPES = {"faculty_notes", "textbook", "job_description", "web_link"}
MAX_UPLOAD_MB = 30
LARGE_SOURCE_WORDS = 8000  # above this, suggest a page range (the whole course must stay under the build limit)
UI_DIR = Path("ui")


@asynccontextmanager
async def lifespan(app):
    sql.require_postgres_when_hosted()
    storage.restore()  # uploads, source lists and built course data saved in Supabase (Railway's disk is wiped on deploy)
    auth.init_auth()  # accounts + the master faculty login
    courses.migrate_layout()
    for course in courses.COURSES:  # anyone may open any course: create tables + seed demo students for each
        db.init_db(course)
    from backend.tools import tts

    tts.warm_up()  # load the read-aloud voice in the background
    notify.start_background()  # the autopilot's daily gap check, and "your lesson is tomorrow" messages
    yield


async def use_request_course(x_course: str | None = Header(None)):
    """Each user picks their own course; the UI sends it as X-Course. Async, so it is set before the endpoint runs."""
    courses.use(x_course)


app = FastAPI(title="VidyaPath API", lifespan=lifespan, dependencies=[Depends(use_request_course)])
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/ui", StaticFiles(directory=UI_DIR, html=True), name="ui")  # the VidyaPath web UI


@app.middleware("http")
async def fresh_ui(request: Request, call_next):
    """Browsers re-check the UI files on every load (cheap: unchanged files answer 304), so a new deploy shows at once."""
    response = await call_next(request)
    if request.url.path.startswith("/ui"):
        response.headers["Cache-Control"] = "no-cache"
    return response


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
    return {"status": "ok", "database": "postgres" if sql.POSTGRES else "sqlite"}


# --------------------------------------------------------------------------- #
# Faculty: sources
# --------------------------------------------------------------------------- #
def _sources_json():
    return courses.data_dir() / "sources.json"


# --------------------------------------------------------------------------- #
# Authentication (JWT) and profiles
# --------------------------------------------------------------------------- #
class Login(BaseModel):
    username: str
    password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class NewPassword(BaseModel):
    password: str


class NewStudent(BaseModel):
    id: str
    name: str
    password: str
    stated_style: str = "reading"
    pace: str = "medium"
    target_role: str = "Software Engineer"


STYLES = {"reading", "listening", "visual", "practice"}
PACES = {"slow", "medium", "fast"}
MIN_PASSWORD = 6


def _check_owner(user, table, row_id):
    """A student may only touch their own viva sessions and lessons."""
    found = db.rows(f"SELECT student_id FROM {table} WHERE id = ?", (row_id,))
    if found:
        auth.check_student_access(user, found[0]["student_id"])


def _display_name(user):
    profile_name = auth.get_profile(user["username"])["name"]
    if profile_name:
        return profile_name
    if user["student_id"]:
        found = db.rows("SELECT name FROM students WHERE id = ?", (user["student_id"],))
        if found:
            return found[0]["name"]
    return "Faculty admin" if user["role"] == "faculty" else user["username"]


LOGIN_MAX_FAILURES = 5
LOGIN_LOCK_SECONDS = 300
_failed_logins = {}  # (client ip, username) -> recent failure times; slows down password guessing


@app.post("/api/auth/login")
def login(body: Login, request: Request):
    key = (request.client.host if request.client else "?", body.username.strip().lower())
    now = time.time()
    recent = [t for t in _failed_logins.get(key, []) if now - t < LOGIN_LOCK_SECONDS]
    if len(recent) >= LOGIN_MAX_FAILURES:
        minutes = -(-int(LOGIN_LOCK_SECONDS - (now - recent[0])) // 60)  # round up
        raise HTTPException(429, f"Too many wrong passwords. Try again in {max(minutes, 1)} minute(s).")
    user = auth.authenticate(body.username, body.password)
    if not user:
        _failed_logins[key] = recent + [now]
        raise HTTPException(401, "Wrong username or password")
    _failed_logins.pop(key, None)
    return {"token": auth.create_token(user), "token_type": "bearer", "expires_in_hours": auth.TOKEN_HOURS,
            "user": {**user, "name": _display_name(user)}}


@app.get("/api/auth/me")
def me(user=Depends(auth.current_user)):
    return {**user, "name": _display_name(user)}


@app.post("/api/auth/password")
def change_password(body: PasswordChange, user=Depends(auth.current_user)):
    if not auth.authenticate(user["username"], body.current_password):
        raise HTTPException(400, "Current password is wrong")
    if len(body.new_password) < MIN_PASSWORD:
        raise HTTPException(400, f"New password must have at least {MIN_PASSWORD} characters")
    auth.set_password(user["username"], body.new_password)
    return {"message": "Password changed"}


@app.get("/api/profile")
def get_profile(user=Depends(auth.current_user)):
    return {**auth.get_profile(user["username"]), **user, "display_name": _display_name(user)}


@app.put("/api/profile")
def put_profile(body: dict, user=Depends(auth.current_user)):
    try:
        saved = auth.save_profile(user["username"], body)
    except ValueError as err:
        raise HTTPException(400, str(err))
    return {**saved, **user, "display_name": _display_name(user)}


@app.get("/api/faculty/students")
def faculty_students(_=Depends(auth.require_faculty)):
    """Students of the active course, with their login (if any)."""
    logins = auth.student_logins()
    return [{**s, "login": logins.get(s["id"])} for s in db.rows("SELECT * FROM students ORDER BY name")]


@app.post("/api/faculty/students")
def create_student(body: NewStudent, user=Depends(auth.require_faculty)):
    """Faculty creates a student (added to every course) and the student's login (username = student id)."""
    student_id = body.id.strip().lower()
    if not re.fullmatch(r"[a-z0-9_]{2,32}", student_id):
        raise HTTPException(400, "Student ID: 2-32 characters, letters, digits or _")
    if not body.name.strip():
        raise HTTPException(400, "Name is required")
    if body.stated_style not in STYLES or body.pace not in PACES:
        raise HTTPException(400, f"Learning style must be one of {sorted(STYLES)}, pace one of {sorted(PACES)}")
    if len(body.password) < MIN_PASSWORD:
        raise HTTPException(400, f"Password must have at least {MIN_PASSWORD} characters")
    if db.rows("SELECT 1 FROM students WHERE id = ?", (student_id,)) or auth.get_user(student_id):
        raise HTTPException(400, f"Student ID '{student_id}' is already taken")
    db.add_student({"id": student_id, "name": body.name.strip(),
                    "stated_style": body.stated_style, "pace": body.pace, "target_role": body.target_role})
    auth.create_student_login(student_id, body.password, user["username"])
    return {"id": student_id, "login": student_id, "message": f"Student {body.name.strip()} created. Login: {student_id}"}


@app.post("/api/faculty/students/{student_id}/password")
def set_student_password(student_id: str, body: NewPassword, user=Depends(auth.require_faculty)):
    """Creates a login for an existing student, or resets the password of an existing login."""
    if not db.rows("SELECT 1 FROM students WHERE id = ?", (student_id,)):
        raise HTTPException(404, "Unknown student")
    if len(body.password) < MIN_PASSWORD:
        raise HTTPException(400, f"Password must have at least {MIN_PASSWORD} characters")
    login_name = auth.student_logins().get(student_id)
    if login_name:
        auth.set_password(login_name, body.password)
        return {"login": login_name, "message": "Password reset"}
    try:
        login_name = auth.create_student_login(student_id, body.password, user["username"])
    except ValueError as err:
        raise HTTPException(400, str(err))
    return {"login": login_name, "message": f"Login created: {login_name}"}


@app.delete("/api/faculty/students/{student_id}/login")
def remove_student_login(student_id: str, _=Depends(auth.require_faculty)):
    """Revokes a student's access (their learning data is kept)."""
    login_name = auth.student_logins().get(student_id)
    if not login_name:
        raise HTTPException(404, "This student has no login")
    auth.delete_login(login_name)
    return {"message": "Login removed"}


@app.get("/api/course")
def course_info():
    """The course this request is for (the X-Course header, else the default) and which courses are ready to use."""
    name = courses.active_course()
    return {"id": name, "title": courses.COURSES[name]["title"], "built": courses.is_built(),
            "available": {k: v["title"] for k, v in courses.COURSES.items()},
            "built_courses": [k for k in courses.COURSES if courses.is_built(k)]}


class CourseSwitch(BaseModel):
    course: str


@app.post("/api/course/switch")
def switch_course(body: CourseSwitch, _=Depends(auth.require_faculty)):
    """Prepares a course for use: builds it first if it has never been built (about a minute).
    Which course a user sees is their own choice (X-Course); this does not change anyone else's course."""
    if body.course not in courses.COURSES:
        raise HTTPException(400, f"Unknown course '{body.course}'. Choose one of: {', '.join(courses.COURSES)}")
    courses.use(body.course)
    if not courses.is_built():
        from backend.agents.knowledge_builder import build_knowledge
        from backend.agents.reconciler import reconcile

        build_knowledge(str(courses.data_dir()))
        reconcile()
    return course_info()


def _read_meta():
    return json.loads(_sources_json().read_text(encoding="utf-8"))


def _write_meta(meta):
    _sources_json().write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    storage.save(_sources_json())


def _find_source(source_id):
    meta = _read_meta()
    src = next((s for s in meta["sources"] if s["id"] == source_id), None)
    if not src:
        raise HTTPException(404, f"Unknown source {source_id}")
    return meta, src


@app.get("/api/sources")
def list_sources(_=Depends(auth.require_faculty)):
    """Every source with tracking info: pages, words, whether it is in the current knowledge base, claims from it."""
    meta = _read_meta()
    kb_file, trusted_file = courses.course_file("knowledge_base.json"), courses.course_file("trusted_kb.json")
    kb = json.loads(kb_file.read_text(encoding="utf-8")) if kb_file.exists() else None
    trusted = json.loads(trusted_file.read_text(encoding="utf-8")) if trusted_file.exists() else None
    built_from = (kb or {}).get("built_from")
    built_ids = {s["id"] for s in (kb or {}).get("sources", [])}
    out = []
    for src in meta["sources"]:
        path = courses.data_dir() / src["file"]
        info = {**src}
        if not path.exists():
            out.append({**info, "status": "missing_file"})
            continue
        if "words" not in info:  # sources added before tracking existed (e.g. the demo .md files)
            try:
                info.update(inspect_file(path, src.get("page_range")))
            except ValueError:
                pass
        sha = info.get("sha256") or file_sha256(path)
        if built_from is not None:
            status = "in_build" if built_from.get(src["id"]) == sha else "changed" if src["id"] in built_from else "new"
        else:
            status = "in_build" if src["id"] in built_ids else "new"
        claims = [c for c in (trusted or {}).get("claims", []) if c["source_id"] == src["id"]]
        conflicts = [c for c in (trusted or {}).get("conflicts", [])
                     if any(src["id"] in side["score"]["sources"] for side in c["sides"])]
        out.append({**info, "format": path.suffix.lower().lstrip("."), "status": status,
                    "claims": len(claims), "trusted_claims": sum(c["status"] == "trusted" for c in claims),
                    "conflicts": len(conflicts)})
    return out


@app.post("/api/sources/upload")
async def upload_source(
    file: UploadFile = File(...),
    title: str = Form(...),
    type: str = Form(...),
    year: int = Form(...),
    page_range: str = Form(""),
    _=Depends(auth.require_faculty),
):
    """Faculty uploads notes or a book (PDF, PPTX, MD, TXT). The file is checked and read right away;
    page_range (e.g. '12-40') limits a big book to the chapters being taught. Then call POST /api/course/build."""
    if type not in SOURCE_TYPES:
        raise HTTPException(400, f"type must be one of {sorted(SOURCE_TYPES)}")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(400, "Only PDF, PPTX, MD or TXT files are supported")
    data = await file.read()
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(400, f"File is larger than {MAX_UPLOAD_MB} MB")
    if suffix == ".pdf" and not data.startswith(b"%PDF"):
        raise HTTPException(400, "This file is not a valid PDF")

    source_id = re.sub(r"[^a-z0-9]+", "_", Path(file.filename).stem.lower()).strip("_") or "source"
    meta = _read_meta()
    sha = hashlib.sha256(data).hexdigest()
    duplicate = next((s for s in meta["sources"] if s.get("sha256") == sha and s["id"] != source_id), None)
    if duplicate:
        raise HTTPException(400, f"This file is already uploaded as '{duplicate['title']}'")

    dest = courses.data_dir() / "sources" / f"{source_id}{suffix}"
    previous = dest.read_bytes() if dest.exists() else None
    dest.write_bytes(data)
    try:
        info = inspect_file(dest, page_range)
        if info["words"] == 0:
            raise ValueError("No readable text was found. If this is a scanned PDF, export it with a text layer "
                             "(or run OCR) and upload again.")
    except Exception as err:  # unreadable, encrypted, scanned or a bad page range: undo the upload
        if previous is None:
            dest.unlink(missing_ok=True)
        else:
            dest.write_bytes(previous)
        raise HTTPException(400, f"Could not read {file.filename}: {err}")

    entry = {"id": source_id, "file": f"sources/{dest.name}", "title": title, "type": type, "year": year,
             "page_range": page_range.strip() or None, "sha256": sha, "size_bytes": len(data),
             "uploaded_at": datetime.now().isoformat(timespec="seconds"), **info}
    meta["sources"] = [s for s in meta["sources"] if s["id"] != source_id] + [entry]  # replace if re-uploaded
    storage.save(dest)  # the file first: a saved source list never points at a file that wasn't saved
    _write_meta(meta)

    warnings = []
    if info["pages_without_text"]:
        warnings.append(f"{len(info['pages_without_text'])} page(s) have no text (images or scans) and will be skipped.")
    if info["words"] > LARGE_SOURCE_WORDS:
        warnings.append(f"Large source ({info['words']:,} words). Consider a page range with only the chapters you teach.")
    return {"id": source_id, "source": entry, "warnings": warnings,
            "message": f"Uploaded {info['pages_used']} page(s), {info['words']:,} words. "
                       "Press Build course to add it to the knowledge base."}


@app.get("/api/sources/{source_id}/pages")
def source_pages(source_id: str, _=Depends(auth.require_faculty)):
    """The text the agents will read from this source, page by page (what was extracted from the PDF)."""
    _, src = _find_source(source_id)
    path = courses.data_dir() / src["file"]
    if not path.exists():
        raise HTTPException(404, "Source file is missing")
    try:
        return {"id": source_id, "title": src["title"], "pages": page_texts(path, src.get("page_range"))}
    except ValueError as err:
        raise HTTPException(400, str(err))


@app.delete("/api/sources/{source_id}")
def delete_source(source_id: str, _=Depends(auth.require_faculty)):
    """Removes a source and its file. Press Build course afterwards to update the knowledge base."""
    meta, src = _find_source(source_id)
    meta["sources"] = [s for s in meta["sources"] if s["id"] != source_id]
    _write_meta(meta)
    (courses.data_dir() / src["file"]).unlink(missing_ok=True)
    storage.delete(courses.data_dir() / src["file"])
    return {"deleted": source_id, "message": "Removed. Press Build course to update the knowledge base."}


# --------------------------------------------------------------------------- #
# Faculty: build + knowledge base
# --------------------------------------------------------------------------- #
@app.post("/api/course/build")
def build_course(_=Depends(auth.require_faculty)):
    """Runs Knowledge Builder then Source Reconciler. Takes ~1 minute on a fresh run, instant when cached."""
    from backend.agents.knowledge_builder import build_knowledge
    from backend.agents.reconciler import reconcile

    try:
        kb = build_knowledge(str(courses.data_dir()))
    except ValueError as err:  # e.g. too many words, or a source without readable text
        raise HTTPException(400, str(err))
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
def course_graph(user=Depends(auth.current_user)):
    """Prerequisite graph in a shape React Flow (or any graph library) can use directly."""
    kb = _load(courses.course_file("trusted_kb.json"))
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
def course_claims(status: str | None = None, concept_id: str | None = None, _=Depends(auth.require_faculty)):
    """Filter with ?status=trusted|outdated|superseded|unreliable|needs_review and/or ?concept_id=..."""
    claims = _load(courses.course_file("trusted_kb.json"))["claims"]
    if status:
        claims = [c for c in claims if c["status"] == status]
    if concept_id:
        claims = [c for c in claims if c["concept_id"] == concept_id]
    return claims


@app.get("/api/course/rejected-claims")
def rejected_claims(_=Depends(auth.require_faculty)):
    """Claims whose quotes could not be found in the sources (hallucinations caught)."""
    return _load(courses.course_file("knowledge_base.json"))["rejected_claims"]


@app.get("/api/course/conflicts")
def course_conflicts(_=Depends(auth.require_faculty)):
    return _load(courses.course_file("trusted_kb.json"))["conflicts"]


class Override(BaseModel):
    winning_side: int


@app.post("/api/course/conflicts/{conflict_id}/override")
def override_conflict(conflict_id: str, body: Override, _=Depends(auth.require_faculty)):
    """Faculty control: choose which side of a conflict is trusted."""
    from backend.agents.reconciler import reconcile, set_faculty_override

    conflicts = {c["id"]: c for c in _load(courses.course_file("trusted_kb.json"))["conflicts"]}
    if conflict_id not in conflicts:
        raise HTTPException(404, "Unknown conflict")
    if not 0 <= body.winning_side < len(conflicts[conflict_id]["sides"]):
        raise HTTPException(400, "winning_side out of range")
    set_faculty_override(conflict_id, body.winning_side)
    return next(c for c in reconcile()["conflicts"] if c["id"] == conflict_id)


@app.get("/api/course/freshness")
def freshness_report(_=Depends(auth.require_faculty)):
    return _load(courses.course_file("trusted_kb.json"))["freshness_report"]


# --------------------------------------------------------------------------- #
# Students
# --------------------------------------------------------------------------- #
@app.get("/api/students")
def list_students(_=Depends(auth.require_faculty)):
    return db.rows("SELECT * FROM students ORDER BY name")


@app.get("/api/students/{student_id}")
def get_student(student_id: str, user=Depends(auth.current_user)):
    auth.check_student_access(user, student_id)
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
def demo_reset(_=Depends(auth.require_faculty)):
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
def viva_start(student_id: str, body: VivaStart | None = None, user=Depends(auth.current_user)):
    auth.check_student_access(user, student_id)
    from backend.agents.viva import start_viva

    try:
        return start_viva(student_id, body.concepts if body else None)
    except ValueError as err:
        raise HTTPException(400, str(err))


@app.post("/api/viva/session/{session_id}/answer")
def viva_answer(session_id: int, body: VivaAnswer, user=Depends(auth.current_user)):
    _check_owner(user, "viva_sessions", session_id)
    from backend.agents.viva import answer_viva

    if not body.answer.strip():
        raise HTTPException(400, "Answer is empty")
    try:
        result = answer_viva(session_id, body.answer, body.confidence)
    except ValueError as err:
        raise HTTPException(400, str(err))
    if result["done"]:
        if result["summary"]["misconceptions"]:
            result["phone"] = _nudge_misconceptions(result["summary"])
        autopilot.after_activity(result["summary"]["student_id"])  # re-plan the path in the background
    return result


def _nudge_misconceptions(summary):
    names = {r["concept_id"]: r["concept_name"] for r in summary["results"]}
    found = summary["misconceptions"][:2]
    student = db.rows("SELECT name FROM students WHERE id = ?", (summary["student_id"],))
    lines = "\n".join(f"- {names.get(m['concept_id'], m['concept_id'])}: {m['misconception']}" for m in found)
    text = (f"Hi {student[0]['name'] if student else ''}, your viva showed a mix-up worth fixing early:\n{lines}\n"
            "The agents are planning a short refresher in your path before it matters.")
    return notify.send(summary["student_id"], "misconception", text, courses.active_course(), "/ui/student.html#path")


@app.get("/api/viva/session/{session_id}")
def viva_session(session_id: int, user=Depends(auth.current_user)):
    """A saved viva: its result, or the question to resume with (never the expected answers)."""
    _check_owner(user, "viva_sessions", session_id)
    from backend.agents.viva import viva_view

    try:
        return viva_view(session_id)
    except ValueError:
        raise HTTPException(404, "Unknown session")


@app.get("/api/viva/{student_id}/sessions")
def viva_sessions(student_id: str, user=Depends(auth.current_user)):
    auth.check_student_access(user, student_id)
    from backend.agents.viva import viva_history

    return viva_history(student_id)


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
def tutor_lesson(student_id: str, body: LessonRequest, user=Depends(auth.current_user)):
    auth.check_student_access(user, student_id)
    from backend.agents.tutor import generate_lesson

    if body.level and body.level not in ("foundation", "standard", "challenge"):
        raise HTTPException(400, "level must be foundation, standard or challenge")
    if body.format and body.format not in ("text", "audio", "visual", "practice"):
        raise HTTPException(400, "format must be text, audio, visual or practice")
    try:
        return generate_lesson(student_id, body.concept_id, body.level, body.format, body.reason)
    except ValueError as err:
        raise HTTPException(400, str(err))


@app.get("/api/students/{student_id}/lessons")
def student_lessons(student_id: str, user=Depends(auth.current_user)):
    auth.check_student_access(user, student_id)
    from backend.agents.tutor import lesson_history

    return lesson_history(student_id)


@app.get("/api/tutor/lessons/{lesson_id}")
def tutor_get_lesson(lesson_id: int, user=Depends(auth.current_user)):
    _check_owner(user, "lessons", lesson_id)
    from backend.agents.tutor import get_lesson

    try:
        return get_lesson(lesson_id)
    except ValueError as err:
        raise HTTPException(404, str(err))


@app.post("/api/tutor/lessons/{lesson_id}/check")
def tutor_check(lesson_id: int, body: PracticeAnswer, user=Depends(auth.current_user)):
    _check_owner(user, "lessons", lesson_id)
    from backend.agents.tutor import check_practice

    if not body.answer.strip():
        raise HTTPException(400, "Answer is empty")
    try:
        result = check_practice(lesson_id, body.question_index, body.answer, body.confidence)
    except ValueError as err:
        raise HTTPException(400, str(err))
    if result["evaluation"]["misconception"]:
        result["phone"] = _nudge_practice(lesson_id, result)
    autopilot.after_activity(db.rows("SELECT student_id FROM lessons WHERE id = ?", (lesson_id,))[0]["student_id"])
    return result


def _nudge_practice(lesson_id, result):
    """A mix-up in practice: tell the student what fixes it. The same mix-up on the same topic is sent only once."""
    lesson = db.rows("SELECT l.student_id, l.concept_id, s.name FROM lessons l JOIN students s ON s.id = l.student_id "
                     "WHERE l.id = ?", (lesson_id,))[0]
    kb = json.loads(courses.course_file("knowledge_base.json").read_text(encoding="utf-8"))
    topic = kb["concepts"].get(lesson["concept_id"], {}).get("name", lesson["concept_id"])
    m, step = result["evaluation"]["misconception"], result["next_step"]
    fix = (f"Open the lesson and press Re-teach as {step['format']} for a {step['level']} lesson that clears it up."
           if step["action"] == "reteach" else "Have another go at the practice question when you're ready.")
    course = courses.active_course()
    return notify.send_once(f"practice:{course}:{lesson['student_id']}:{lesson['concept_id']}:{m.strip().lower()[:120]}",
                            lesson["student_id"], "misconception",
                            f"Hi {lesson['name']}, in your {topic} practice we noticed a mix-up: {m}\n{fix}",
                            course, "/ui/student.html#lessons")


# --------------------------------------------------------------------------- #
# Gap prediction + proactive path redesign (Objective 2)
# --------------------------------------------------------------------------- #
@app.get("/api/students/{student_id}/path")
def student_path(student_id: str, user=Depends(auth.current_user)):
    auth.check_student_access(user, student_id)
    from backend.agents.gap_predictor import build_path

    try:
        return build_path(student_id)
    except ValueError as err:
        raise HTTPException(404, str(err))


@app.get("/api/students/{student_id}/gap-radar")
def student_gap_radar(student_id: str, user=Depends(auth.current_user)):
    """Risk for every upcoming concept with its factors and reason chain. Read-only, instant."""
    auth.check_student_access(user, student_id)
    from backend.agents.gap_predictor import gap_radar

    try:
        return gap_radar(student_id)
    except ValueError as err:
        raise HTTPException(404, str(err))


@app.post("/api/students/{student_id}/predict")
def student_predict(student_id: str, user=Depends(auth.current_user)):
    """Predicts gaps and redesigns the path. Call after a viva or a practice check."""
    auth.check_student_access(user, student_id)
    try:
        return autopilot.predict(student_id)  # the phone gets the message when the path changed
    except ValueError as err:
        raise HTTPException(404, str(err))


@app.post("/api/students/{student_id}/path/{item_id}/complete")
def student_complete_item(student_id: str, item_id: int, user=Depends(auth.current_user)):
    auth.check_student_access(user, student_id)
    from backend.agents.gap_predictor import complete_item

    try:
        return complete_item(student_id, item_id)
    except ValueError as err:
        raise HTTPException(404, str(err))


@app.get("/api/class/gap-radar")
def class_gap_radar(_=Depends(auth.require_faculty)):
    """Faculty view: which upcoming concepts put which students at risk."""
    from backend.agents.gap_predictor import class_radar

    return class_radar()


# --------------------------------------------------------------------------- #
# Student: Doubt Assistant (answers only from trusted course facts)
# --------------------------------------------------------------------------- #
class DoubtRequest(BaseModel):
    question: str
    concept_id: str | None = None  # optional: the topic the student picked


@app.post("/api/doubts/{student_id}")
def ask_doubt(student_id: str, body: DoubtRequest, user=Depends(auth.current_user)):
    auth.check_student_access(user, student_id)
    from backend.agents.doubt import answer_doubt

    question = body.question.strip()
    if not question:
        raise HTTPException(400, "Please type a question")
    if len(question) > 1000:
        raise HTTPException(400, "Please keep the question under 1000 characters")
    try:
        return answer_doubt(student_id, question, body.concept_id or None)
    except ValueError as err:
        raise HTTPException(400, str(err))


@app.get("/api/doubts/{student_id}")
def list_doubts(student_id: str, user=Depends(auth.current_user)):
    auth.check_student_access(user, student_id)
    from backend.agents.doubt import doubt_history

    return doubt_history(student_id)


# --------------------------------------------------------------------------- #
# Phone nudges (Telegram): students connect their phone; agents message them when their path changes
# --------------------------------------------------------------------------- #
def _notify_call(fn, *args):
    if not notify.configured():
        raise HTTPException(503, "Phone nudges are not set up: add TELEGRAM_BOT_TOKEN on the server.")
    try:
        return fn(*args)
    except ValueError as err:
        raise HTTPException(400, str(err))
    except RuntimeError as err:  # Telegram said no (bad token, network...)
        raise HTTPException(502, f"Telegram: {err}")


@app.get("/api/notify")
def notify_overview(_=Depends(auth.require_faculty)):
    return notify.overview()


@app.get("/api/notify/{student_id}")
def notify_status(student_id: str, user=Depends(auth.current_user)):
    auth.check_student_access(user, student_id)
    return notify.status(student_id)


@app.post("/api/notify/{student_id}/link")
def notify_link(student_id: str, user=Depends(auth.current_user)):
    auth.check_student_access(user, student_id)
    return _notify_call(notify.start_link, student_id)


@app.post("/api/notify/{student_id}/verify")
def notify_verify(student_id: str, user=Depends(auth.current_user)):
    auth.check_student_access(user, student_id)
    found = db.rows("SELECT name FROM students WHERE id = ?", (student_id,))
    return _notify_call(notify.finish_link, student_id, found[0]["name"] if found else student_id)


@app.post("/api/notify/{student_id}/test")
def notify_test(student_id: str, user=Depends(auth.current_user)):
    auth.check_student_access(user, student_id)
    result = notify.send(student_id, "test", "Test from VidyaPath: phone nudges are working.", courses.active_course())
    if result["status"] != "sent":
        raise HTTPException(400, result.get("error") or "Connect your phone first")
    return notify.status(student_id)


@app.delete("/api/notify/{student_id}")
def notify_unlink(student_id: str, user=Depends(auth.current_user)):
    auth.check_student_access(user, student_id)
    notify.unlink(student_id)
    return notify.status(student_id)


# --------------------------------------------------------------------------- #
# Placement Readiness Forecast (faculty / HOD): job-description skills x student mastery, per role
# --------------------------------------------------------------------------- #
class DriveDate(BaseModel):
    drive_date: str  # YYYY-MM-DD


@app.get("/api/placement/forecast")
def placement_forecast(_=Depends(auth.require_faculty)):
    from backend import placement

    try:
        return placement.forecast()
    except FileNotFoundError:
        raise HTTPException(404, "Build the course first: the forecast needs its job descriptions.")


@app.put("/api/placement/drive-date")
def placement_drive_date(body: DriveDate, _=Depends(auth.require_faculty)):
    from backend import placement

    try:
        placement.set_drive_date(body.drive_date)
    except ValueError:
        raise HTTPException(400, "drive_date must be a date like 2026-10-30")
    return placement.forecast()


# --------------------------------------------------------------------------- #
# Read aloud: any text the UI shows, spoken on the server (Piper, or pyttsx3 as the fallback)
# --------------------------------------------------------------------------- #
class SpeechRequest(BaseModel):
    text: str


@app.post("/api/tts")
def text_to_speech(body: SpeechRequest, _=Depends(auth.current_user)):
    from backend.tools import tts

    if not body.text.strip():
        raise HTTPException(400, "Nothing to read aloud")
    try:
        path, engine = tts.speech_mp3(body.text)
    except tts.Unavailable as err:
        raise HTTPException(503, str(err))  # the UI then uses the browser's own voice
    return FileResponse(path, media_type="audio/mpeg",
                        headers={"Cache-Control": "private, max-age=86400", "X-Speech-Engine": engine})


# --------------------------------------------------------------------------- #
# Faculty: Class-Ready Kit (outline, handout, quiz, assignment for one topic)
# --------------------------------------------------------------------------- #
class KitRequest(BaseModel):
    concept_id: str
    class_minutes: int = 50


@app.post("/api/faculty/kit")
def create_kit(body: KitRequest, user=Depends(auth.require_faculty)):
    from backend.agents.kit import generate_kit

    if not 20 <= body.class_minutes <= 180:
        raise HTTPException(400, "Class length must be between 20 and 180 minutes")
    try:
        return generate_kit(body.concept_id, body.class_minutes, user["username"])
    except ValueError as err:
        raise HTTPException(400, str(err))


@app.get("/api/faculty/kits")
def list_class_kits(_=Depends(auth.require_faculty)):
    from backend.agents.kit import list_kits

    return list_kits()


@app.get("/api/faculty/kits/{kit_id}")
def get_class_kit(kit_id: int, _=Depends(auth.require_faculty)):
    from backend.agents.kit import get_kit

    try:
        return get_kit(kit_id)
    except ValueError as err:
        raise HTTPException(404, str(err))
