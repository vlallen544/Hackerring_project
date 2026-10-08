# Runs the Source Reconciler and checks the planted conflicts were resolved correctly
import sys

sys.path.insert(0, ".")
from backend.agents.reconciler import OUTPUT_FILE, reconcile  # noqa: E402
from backend.tools.verify import normalize  # noqa: E402

kb = reconcile()

print("\n=== CONFLICTS ===")
for c in kb["conflicts"]:
    print(f"\n[{c['id']}] {c['topic']}  ({c['type']})  ->  {c['decision'].upper()}")
    for i, s in enumerate(c["sides"]):
        mark = "WIN " if c.get("winner_side") == i else "    "
        f = s["score"]["factors"]
        print(f"  {mark} trust={s['score']['trust']:.2f}  rec={f['recency']} auth={f['authority']} "
              f"agree={f['agreement']} spec={f['specificity']}  | {s['label']}  {s['score']['sources']}")
    print(f"  WHY: {c['explanation']}")

fr = kb["freshness_report"]
print(f"\n=== SYLLABUS FRESHNESS: {fr['score']}% aligned with industry ===")
for s in fr["skills"]:
    print(f"  {s['faculty_coverage']:<9} {s['skill']}  - {s['note']}")

# Planted wrong/outdated claims must NOT end up trusted; correct ones must.
print("\n=== PLANTED RESULTS CHECK ===")
checks = [
    ("Outdated 'MySQL ignores CHECK' not trusted", "ignores them", False),
    ("Outdated 'no window functions' not trusted", "does not support window functions", False),
    ("Wrong '3NF = BCNF' not trusted", "3nf and bcnf are the same", False),
    ("Misleading 'subqueries faster' not trusted", "subqueries are always faster", False),
    ("'CHECK enforced since 8.0.16' trusted", "8.0.16", True),
    ("'Window functions from MySQL 8.0' trusted", "from version 8.0", True),
]
for label, phrase, should_be_trusted in checks:
    matches = [c for c in kb["claims"] if phrase in normalize(c["quote"])]
    if not matches:
        print(f"  ??    {label}  (claim not found - check Step 3 output)")
        continue
    ok = all((c["status"] == "trusted") == should_be_trusted for c in matches)
    print(f"  {'OK  ' if ok else 'FAIL'}  {label}  [{', '.join(c['status'] for c in matches)}]")

print(f"\nSaved to {OUTPUT_FILE}")
