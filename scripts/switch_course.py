# Sets the default course for scripts and new browsers (each course has its own knowledge base, overrides and progress).
# Builds the course the first time it is used.  Usage: python scripts/switch_course.py dsa   (or dbms)
import sys

sys.path.insert(0, ".")
from backend import courses, db  # noqa: E402

if len(sys.argv) != 2 or sys.argv[1] not in courses.COURSES:
    sys.exit(f"Usage: python scripts/switch_course.py <{'|'.join(courses.COURSES)}>   (active: {courses.active_course()})")

name = sys.argv[1]
courses.switch(name)
db.init_db()
print(f"Default course: {courses.COURSES[name]['title']} ({name}), sources in {courses.data_dir()}/")

if not courses.is_built():
    from backend.agents.knowledge_builder import build_knowledge  # noqa: E402
    from backend.agents.reconciler import reconcile  # noqa: E402

    print("Not built yet: running Knowledge Builder and Source Reconciler (about a minute)...")
    kb = build_knowledge(str(courses.data_dir()))
    trusted = reconcile()
    print(f"Built: {len(kb['concepts'])} concepts, {len(kb['claims'])} verified claims "
          f"({len(kb['rejected_claims'])} rejected), {len(trusted['conflicts'])} conflicts, "
          f"freshness {trusted['freshness_report']['score']}%")
else:
    print("Already built.")
