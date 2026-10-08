# Interactive viva in the terminal (no frontend needed). Usage: python scripts/viva_cli.py ravi
import sys

sys.path.insert(0, ".")
from backend import db  # noqa: E402
from backend.agents.viva import answer_viva, start_viva  # noqa: E402

db.init_db()
student_id = sys.argv[1] if len(sys.argv) > 1 else "ravi"

q = start_viva(student_id)
session_id = q["session_id"]
print(f"\nViva for {q['student']} (session {session_id}). Type your answer, then rate confidence 1-5.\n")

while True:
    tag = "  (follow-up)" if q["is_follow_up"] else ""
    print(f"[{q['progress']['concept']}/{q['progress']['of']}] {q['concept_name']}{tag}")
    print(f"Q: {q['question']}")
    answer = input("A: ").strip() or "I don't know"
    conf = input("Confidence 1-5: ").strip()
    result = answer_viva(session_id, answer, int(conf) if conf.isdigit() else 3)

    ev = result["evaluation"]
    print(f"  -> {ev['verdict'].upper()} (score {ev['score']:.2f})  {ev['feedback']}")
    if ev["misconception"]:
        print(f"  -> Misconception: {ev['misconception']}")
    print(f"  -> Agent: {result['agent_decision']}\n")
    if result["done"]:
        break
    q = result["next"]

s = result["summary"]
print("=== RESULT ===")
for r in s["results"]:
    print(f"  {r['concept_name']:<30} mastery {r['mastery']:.2f} ({r['band']}), "
          f"confidence {r['confidence']:.2f} -> {r['calibration']}")
for m in s["misconceptions"]:
    print(f"  Misconception [{m['concept_id']}]: {m['misconception']}")
for m in s["missing_prerequisites"]:
    print(f"  Missing prerequisite: {m['prerequisite']} (seen while testing {m['concept_id']})")
