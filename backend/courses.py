# Course registry: which sample-data folder and student database belong to each course, and which course a request is for.
# Each course keeps its outputs in data/courses/<id>/. Every user picks their own course (the UI sends it as the
# X-Course header); scripts and requests without one use the default course (data/active_course.json).
import json
import shutil
from contextvars import ContextVar
from pathlib import Path

from backend import storage

COURSES = {
    "dbms": {"title": "Database Management Systems", "data_dir": "sample_data", "db": "vidyapath.db"},
    "dsa": {"title": "Data Structures and Algorithms", "data_dir": "sample_data_dsa", "db": "vidyapath_dsa.db"},
    "os": {"title": "Operating Systems", "data_dir": "sample_data_os", "db": "vidyapath_os.db"},
    "oop": {"title": "Object-Oriented Programming with Java", "data_dir": "sample_data_oop", "db": "vidyapath_oop.db"},
    "agentic": {"title": "Agentic AI Systems", "data_dir": "sample_data_agentic", "db": "vidyapath_agentic.db"},
    "aicoding": {"title": "AI-Assisted Software Engineering (Vibe Coding)", "data_dir": "sample_data_aicoding",
                 "db": "vidyapath_aicoding.db"},
}
DEFAULT_COURSE = "dbms"
ACTIVE_FILE = Path("data/active_course.json")  # the default course
STORE_DIR = Path("data/courses")
COURSE_FILES = ["knowledge_base.json", "trusted_kb.json", "faculty_overrides.json"]

_request_course = ContextVar("course", default=None)  # set per API request from the X-Course header


def default_course():
    try:
        name = json.loads(ACTIVE_FILE.read_text(encoding="utf-8"))["course"]
        return name if name in COURSES else DEFAULT_COURSE
    except (OSError, ValueError, KeyError):
        return DEFAULT_COURSE


def active_course():
    """The course of the current request, else the default course."""
    return _request_course.get() or default_course()


def use(name):
    """Makes `name` the course for the rest of this request (or script). Unknown names are ignored."""
    if name in COURSES:
        _request_course.set(name)


def course_file(name, course=None):
    """Path of one of the course's outputs (knowledge_base.json, trusted_kb.json, faculty_overrides.json)."""
    return STORE_DIR / (course or active_course()) / name


def data_dir():
    return Path(COURSES[active_course()]["data_dir"])


def db_path(course=None):
    return Path("data") / COURSES[course or active_course()]["db"]


def is_built(course=None):
    return course_file("trusted_kb.json", course).exists()


def switch(name):
    """Sets the default course (used by scripts and by browsers that have not picked one)."""
    if name not in COURSES:
        raise ValueError(f"Unknown course '{name}'. Choose one of: {', '.join(COURSES)}")
    ACTIVE_FILE.parent.mkdir(exist_ok=True)
    ACTIVE_FILE.write_text(json.dumps({"course": name}), encoding="utf-8")
    storage.save(ACTIVE_FILE)


def migrate_layout():
    """Older versions kept the active course's outputs in data/ itself: move them into its course folder."""
    for f in COURSE_FILES:
        old = Path("data") / f
        if old.exists():
            new = course_file(f, default_course())
            new.parent.mkdir(parents=True, exist_ok=True)
            if not new.exists():
                shutil.move(str(old), new)
