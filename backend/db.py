# Database: student state (profiles, mastery, attempts, learning path, risk events) in Postgres or SQLite (see sql.py).
# Course knowledge (knowledge_base.json, trusted_kb.json) stays as JSON files produced by the agents.
import json
from pathlib import Path

from backend import auth, courses, sql
from backend.sql import ID, NOW

DEFAULT_STUDENTS_FILE = Path("sample_data/students.json")


def _students_file(course=None):
    """A course may have its own students.json (e.g. a different target role); else the default one."""
    own = Path(courses.COURSES[course or courses.active_course()]["data_dir"]) / "students.json"
    return own if own.exists() else DEFAULT_STUDENTS_FILE

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS students (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    stated_style TEXT,
    learned_style TEXT,            -- filled later: the format that actually works best for this student
    pace TEXT,
    target_role TEXT
);

CREATE TABLE IF NOT EXISTS mastery (
    student_id TEXT,
    concept_id TEXT,
    score DOUBLE PRECISION,        -- 0.0 to 1.0
    confidence DOUBLE PRECISION,   -- student's self-rated confidence, 0.0 to 1.0
    last_practiced TEXT,           -- ISO date
    PRIMARY KEY (student_id, concept_id)
);

CREATE TABLE IF NOT EXISTS attempts (
    id {ID},
    student_id TEXT,
    concept_id TEXT,
    kind TEXT,                     -- viva / quiz / doubt
    question TEXT,
    answer TEXT,
    correct DOUBLE PRECISION,      -- 0.0 to 1.0
    misconception TEXT,
    created_at TEXT DEFAULT {NOW}
);

CREATE TABLE IF NOT EXISTS path_items (
    id {ID},
    student_id TEXT,
    position INTEGER,
    concept_id TEXT,
    kind TEXT,                     -- lesson / refresher / challenge
    format TEXT,                   -- text / audio / visual / practice
    status TEXT DEFAULT 'pending', -- pending / done / locked
    reason TEXT,                   -- why the agent added it (reason chain)
    scheduled_for TEXT
);

CREATE TABLE IF NOT EXISTS viva_sessions (
    id {ID},
    student_id TEXT,
    status TEXT DEFAULT 'active',  -- active / done
    state TEXT,                    -- JSON: question queue, answers, transcript
    created_at TEXT DEFAULT {NOW}
);

CREATE TABLE IF NOT EXISTS lessons (
    id {ID},
    student_id TEXT,
    concept_id TEXT,
    level TEXT,                    -- foundation / standard / challenge
    format TEXT,                   -- text / audio / visual / practice
    content TEXT,                  -- JSON: segments with provenance, diagram, audio script, practice
    adaptation TEXT,               -- JSON: why this level and format were chosen
    created_at TEXT DEFAULT {NOW}
);

CREATE TABLE IF NOT EXISTS lesson_checks (
    id {ID},
    student_id TEXT,
    lesson_id INTEGER,
    concept_id TEXT,
    format TEXT,                   -- format of the lesson being checked (used to learn the student's best style)
    level TEXT,
    question TEXT,
    answer TEXT,
    score DOUBLE PRECISION,
    created_at TEXT DEFAULT {NOW}
);

CREATE TABLE IF NOT EXISTS doubts (
    id {ID},
    student_id TEXT,
    concept_id TEXT,
    question TEXT,
    answerable INTEGER,            -- 1 if answered from trusted facts, 0 if declined
    answer TEXT,                   -- JSON: answer, citations, example, follow-ups
    created_at TEXT DEFAULT {NOW}
);

CREATE TABLE IF NOT EXISTS class_kits (
    id {ID},
    concept_id TEXT,
    class_minutes INTEGER,
    content TEXT,                  -- JSON: outline, handout, mistakes, quiz, assignment, class insight
    created_by TEXT,
    created_at TEXT DEFAULT {NOW}
);

CREATE TABLE IF NOT EXISTS risk_events (
    id {ID},
    student_id TEXT,
    concept_id TEXT,
    risk DOUBLE PRECISION,
    action TEXT,
    reason TEXT,
    created_at TEXT DEFAULT {NOW}
);
"""


def get_conn(course=None):
    course = course or courses.active_course()
    return sql.connect(courses.db_path(course), schema=f"course_{course}")  # each course keeps its own student progress


def init_db(course=None):
    """Creates tables (safe to call every startup), seeds demo students once and adds faculty-created students."""
    course = course or courses.active_course()
    with get_conn(course) as conn:
        if sql.POSTGRES:
            conn.execute(f'CREATE SCHEMA IF NOT EXISTS "course_{course}"')
        conn.script(SCHEMA)
        if conn.execute("SELECT 1 FROM students LIMIT 1").fetchone() is None and _students_file(course).exists():
            for s in json.loads(_students_file(course).read_text(encoding="utf-8"))["students"]:
                conn.execute(
                    "INSERT INTO students (id, name, stated_style, pace, target_role) VALUES (?,?,?,?,?)",
                    (s["id"], s["name"], s["stated_style"], s["pace"], s["target_role"]),
                )
        for s in auth.registered_students():  # students created by faculty exist in every course
            conn.execute("INSERT INTO students (id, name, stated_style, pace, target_role) VALUES (?,?,?,?,?) "
                         "ON CONFLICT (id) DO NOTHING",
                         (s["id"], s["name"], s["stated_style"], s["pace"], s["target_role"]))


def add_student(student):
    """Faculty creates a student: registered once, then added to every course's database."""
    auth.register_student(student)
    for course in courses.COURSES:
        init_db(course)


def rows(query, params=()):
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def execute(query, params=()):
    """Runs a write query. Returns the new row id when the query ends with RETURNING id."""
    with get_conn() as conn:
        cur = conn.execute(query, params)
        return cur.fetchone()["id"] if "RETURNING" in query.upper() else None


def reset_student_progress():
    """Demo helper: wipes progress but keeps students, so you can re-run the demo cleanly."""
    with get_conn() as conn:
        for table in ("mastery", "attempts", "path_items", "risk_events", "viva_sessions", "lessons", "lesson_checks", "doubts"):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("UPDATE students SET learned_style = NULL")
