# Shows Objective 1: the SAME concept taught differently to two students, with reasons and provenance.
# Usage: python scripts/run_tutor_demo.py <concept_id> [student_a] [student_b]
#   e.g. python scripts/run_tutor_demo.py keys ravi asha
# Run the viva for both students first, so their mastery is known.
import sys

sys.path.insert(0, ".")
from backend import db  # noqa: E402
from backend.agents.tutor import generate_lesson  # noqa: E402

db.init_db()
concept = sys.argv[1] if len(sys.argv) > 1 else "keys"
students = sys.argv[2:4] if len(sys.argv) > 2 else ["ravi", "asha"]

for sid in students:
    lesson = generate_lesson(sid, concept)
    a = lesson["adaptation"]
    print("=" * 78)
    print(f"{sid.upper()}  |  {lesson['concept_name']}  |  lesson #{lesson['lesson_id']}")
    print(f"  Level   : {a['level']:<11} <- {a['level_reason']}")
    print(f"  Format  : {a['format']:<11} <- {a['format_reason']}")
    print(f"  Language: {a['language']}")
    if a["targets_misconceptions"]:
        print(f"  Targets : {a['targets_misconceptions']}")
    print(f"  From faculty material: {lesson['material_share_percent']}% of the lesson\n")
    print(f"  {lesson['title']}")
    for seg in lesson["segments"]:
        tag = "[MATERIAL]" if seg["origin"] == "material" else "[AI-ADDED]"
        cite = f"  ({seg['sources'][0]['source']}, p.{seg['sources'][0]['page']})" if seg["sources"] else ""
        print(f"  {tag} {seg['text']}{cite}")
    if lesson["misconception_fix"]:
        print(f"\n  Misconception fix: {lesson['misconception_fix']}")
    if lesson["audio_script"]:
        print(f"\n  Audio script: {lesson['audio_script'][:200]}...")
    if lesson["diagram_mermaid"]:
        print(f"\n  Diagram:\n{lesson['diagram_mermaid']}")
    print("\n  Practice:")
    for i, p in enumerate(lesson["practice"]):
        print(f"   {i}. {p['question']}")
print("=" * 78)
