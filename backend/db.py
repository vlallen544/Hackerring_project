# Database: SQLite for student state (profiles, mastery, attempts, learning path, risk events).
# Course knowledge (knowledge_base.json, trusted_kb.json) stays as JSON files produced by the agents.
import json
import sqlite3
from pathlib import Path

DB_PATH = Path("data/vidyapath.db")
STUDENTS_FILE = Path("sample_data/students.json")

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    language TEXT,
    stated_style TEXT,
    learned_style TEXT,            -- filled later: the format that actually works best for this student
    pace TEXT,
    target_role TEXT
);

CREATE TABLE IF NOT EXISTS mastery (
    student_id TEXT,
    concept_id TEXT,
    score REAL,                    -- 0.0 to 1.0
    confidence REAL,               -- student's self-rated confidence, 0.0 to 1.0
    last_practiced TEXT,           -- ISO date
    PRIMARY KEY (student_id, concept_id)
);

CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT,
    concept_id TEXT,
    kind TEXT,                     -- viva / quiz / doubt
    question TEXT,
    answer TEXT,
    correct REAL,                  -- 0.0 to 1.0
    misconception TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS path_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT,
    status TEXT DEFAULT 'active',  -- active / done
    state TEXT,                    -- JSON: question queue, answers, transcript
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS risk_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT,
    concept_id TEXT,
    risk REAL,
    action TEXT,
    reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    return conn


def init_db():
    """Creates tables (safe to call every startup) and seeds demo students once."""
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0 and STUDENTS_FILE.exists():
            for s in json.loads(STUDENTS_FILE.read_text(encoding="utf-8"))["students"]:
                conn.execute(
                    "INSERT INTO students (id, name, language, stated_style, pace, target_role) VALUES (?,?,?,?,?,?)",
                    (s["id"], s["name"], s["language"], s["stated_style"], s["pace"], s["target_role"]),
                )


def rows(query, params=()):
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def execute(query, params=()):
    """Runs a write query. Returns the new row id for INSERTs."""
    with get_conn() as conn:
        return conn.execute(query, params).lastrowid


def reset_student_progress():
    """Demo helper: wipes progress but keeps students, so you can re-run the demo cleanly."""
    with get_conn() as conn:
        for table in ("mastery", "attempts", "path_items", "risk_events", "viva_sessions"):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("UPDATE students SET learned_style = NULL")
