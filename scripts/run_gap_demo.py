# Shows Objective 2: predict gaps and redesign the path BEFORE the student reaches the risky concept.
# Usage: python scripts/run_gap_demo.py ravi
# Run the viva for the student first, so their mastery is known.
import sys

sys.path.insert(0, ".")
from backend import db  # noqa: E402
from backend.agents.gap_predictor import gap_radar, predict_and_redesign  # noqa: E402

db.init_db()
sid = sys.argv[1] if len(sys.argv) > 1 else "ravi"

print(f"\n=== GAP RADAR for {sid} (before redesign) ===")
for r in gap_radar(sid):
    f = r["factors"]
    print(f"  {r['band'].upper():<6} {round(r['risk'] * 100):>3}%  {r['concept_name']:<28} "
          f"(prereq weakness {f['prerequisite_weakness']}, forgetting {f['forgetting']}, "
          f"pace {f['pace_lag']}, misconception {f['misconception']})")
    print(f"         {r['reason_chain']}")

result = predict_and_redesign(sid)

print(f"\n=== ACTIONS TAKEN ({len(result['actions'])}) ===")
for a in result["actions"]:
    print(f"  [{a['type'].upper()}] {a['reason']}")
if result["message"]:
    print(f"\n  Message to student: {result['message']['student_message']}")
    print(f"  Note for faculty  : {result['message']['faculty_note']}")

print("\n=== NEW LEARNING PATH ===")
for p in result["path"]:
    mark = {"refresher": "+ REFRESHER", "challenge": "* CHALLENGE"}.get(p["kind"], "  lesson")
    print(f"  {p['scheduled_for']}  {mark:<12} {p['concept_id']:<22} ({p['format']})")
