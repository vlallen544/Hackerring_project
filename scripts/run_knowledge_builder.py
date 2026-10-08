# Runs the Knowledge Builder and checks its output against sample_data/expected_results.md
import sys
from collections import Counter

sys.path.insert(0, ".")
from backend.agents.knowledge_builder import OUTPUT_FILE, build_knowledge  # noqa: E402
from backend.tools.verify import normalize  # noqa: E402

kb = build_knowledge()

print("\n=== CONCEPTS ===")
for cid, c in kb["concepts"].items():
    print(f"  {cid:<28} {c['name']}")

print(f"\n=== CLAIMS: {len(kb['claims'])} verified, {len(kb['rejected_claims'])} rejected ===")
for src, n in Counter(c["source_id"] for c in kb["claims"]).items():
    print(f"  {src:<28} {n} claims")
for r in kb["rejected_claims"]:
    print(f"  REJECTED ({r['reject_reason']}): {r['quote'][:70]}")

print("\n=== PREREQUISITES ===")
for p in kb["prerequisites"]:
    print(f"  {p['before']} -> {p['after']}")
print("\n  Learning order:", " -> ".join(kb["learning_order"]))

# The planted claims MUST survive extraction, or the Reconciler (Step 4) has nothing to resolve.
print("\n=== PLANTED CLAIMS CHECK ===")
planted = {
    "Outdated: MySQL ignores CHECK": "ignores them",
    "Outdated: no window functions": "does not support window functions",
    "Wrong: 3NF = BCNF": "3nf and bcnf are the same",
    "Misleading: subqueries faster": "subqueries are always faster",
    "Correct: CHECK enforced 8.0.16": "8.0.16",
    "Correct: window funcs MySQL 8.0": "from version 8.0",
}
all_quotes = [normalize(c["quote"]) for c in kb["claims"]]
for label, phrase in planted.items():
    found = any(phrase in q for q in all_quotes)
    print(f"  {'OK  ' if found else 'MISSING'}  {label}")

print(f"\nSaved to {OUTPUT_FILE}")