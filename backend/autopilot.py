# Autopilot: the Gap Predictor runs by itself, without anyone pressing "Check for gaps": right after every viva and
# practice answer (new evidence), and once a day for every assessed student (risk grows as practice fades and the
# schedule slips). Whenever it changes a path, the student's phone gets the agent's message (if they connected one).
import sys
import threading
from datetime import datetime

from backend import courses, db, notify

_locks = {}
_locks_guard = threading.Lock()


def _lock(course, student_id):
    with _locks_guard:
        return _locks.setdefault((course, student_id), threading.Lock())


def predict(student_id, course=None):
    """Gap prediction + redesign, one run at a time per student (a manual and an automatic run never double up).
    Sends the agent's message to the phone when the path changed."""
    from backend.agents.gap_predictor import predict_and_redesign

    course = course or courses.active_course()
    with _lock(course, student_id):
        result = predict_and_redesign(student_id)
    if result["actions"] and result["message"]:  # only a real change reaches the phone
        result["phone"] = notify.send(student_id, "path_change", result["message"]["student_message"],
                                      course, "/ui/student.html#path")
    return result


def after_activity(student_id):
    """New evidence (a finished viva, a practice answer): re-plan in the background, so the student doesn't wait."""
    course = courses.active_course()

    def run():
        courses.use(course)  # this thread only
        try:
            predict(student_id, course)
        except Exception as e:  # e.g. the model is unreachable: the next run will try again
            print(f"Autopilot for {student_id} ({course}) failed: {e}", file=sys.stderr)

    threading.Thread(target=run, daemon=True, name=f"autopilot-{student_id}").start()


def daily_sweep(now=None):
    """Once a day, re-check every assessed student in every course. Returns how many paths changed."""
    now = now or datetime.now(notify.LOCAL_TZ)
    if not notify.QUIET_BEFORE <= now.hour < notify.QUIET_FROM:
        return 0  # messages only in the daytime
    today = now.date().isoformat()
    changed = 0
    for course in courses.COURSES:
        if not courses.is_built(course):
            continue
        courses.use(course)
        for r in db.rows("SELECT DISTINCT student_id FROM mastery"):
            if not notify.claim(f"autopilot:{course}:{r['student_id']}:{today}"):
                continue  # already checked today (here or on another server)
            try:
                changed += bool(predict(r["student_id"], course)["actions"])
            except Exception as e:
                print(f"Autopilot sweep for {r['student_id']} ({course}) failed: {e}", file=sys.stderr)
    return changed
