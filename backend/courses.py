# Course registry: which sample-data folder and student database belong to each course, and which course is active.
# Agents always read/write the ACTIVE course's files in data/; switching saves them and restores the other course's.
import json
import shutil
from pathlib import Path

COURSES = {
    "dbms": {"title": "Database Management Systems", "data_dir": "sample_data", "db": "vidyapath.db"},
    "dsa": {"title": "Data Structures and Algorithms", "data_dir": "sample_data_dsa", "db": "vidyapath_dsa.db"},
}
DEFAULT_COURSE = "dbms"
ACTIVE_FILE = Path("data/active_course.json")
STORE_DIR = Path("data/courses")  # saved outputs of the courses that are not active
COURSE_FILES = ["knowledge_base.json", "trusted_kb.json", "faculty_overrides.json"]


def active_course():
    try:
        name = json.loads(ACTIVE_FILE.read_text(encoding="utf-8"))["course"]
        return name if name in COURSES else DEFAULT_COURSE
    except (OSError, ValueError, KeyError):
        return DEFAULT_COURSE


def data_dir():
    return Path(COURSES[active_course()]["data_dir"])


def db_path():
    return Path("data") / COURSES[active_course()]["db"]


def is_built():
    return (Path("data") / "trusted_kb.json").exists()


def switch(name):
    """Saves the active course's outputs, restores the target course's saved outputs (if any) and activates it."""
    if name not in COURSES:
        raise ValueError(f"Unknown course '{name}'. Choose one of: {', '.join(COURSES)}")
    current = active_course()
    if name == current:
        return
    saved_current, saved_target = STORE_DIR / current, STORE_DIR / name
    saved_current.mkdir(parents=True, exist_ok=True)
    for f in COURSE_FILES:
        live = Path("data") / f
        if live.exists():
            shutil.move(str(live), saved_current / f)
        if (saved_target / f).exists():
            shutil.move(str(saved_target / f), live)  # move, so data/courses/ only holds inactive courses
    ACTIVE_FILE.parent.mkdir(exist_ok=True)
    ACTIVE_FILE.write_text(json.dumps({"course": name}), encoding="utf-8")
