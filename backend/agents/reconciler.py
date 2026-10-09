# Source Reconciler agent: finds conflicting/outdated claims, decides what to trust, builds the Syllabus Freshness Report
import json

from backend import courses, storage
from backend.engine.trust import CLOSE_CALL_MARGIN, UNRELIABLE_THRESHOLD, explain, score_side
from backend.models import ReconcilerOutput
from backend.tools.llm import heavy_json, heavy_model


SYSTEM_PROMPT = """You are the Source Reconciler agent of VidyaPath, a learning platform for college faculty.
You receive claims extracted from a course's sources (faculty notes, textbook, web articles, job descriptions).
Each claim has an id, a concept, the source it came from, the source type and the year.

TASK 1 - CONFLICTS. Find every place where claims disagree or a claim is misleading:
  - "contradiction": sources state incompatible things.
  - "outdated": one side was true in the past but newer sources show it is no longer true
    (for example, a software feature that was added in a later version).
  - "unreliable": a single claim that is misleading, over-generalised or bad advice, even if no
    other source directly contradicts it. Put it as ONE side.
  For each side, set is_specific (gives versions, dates or reasons) and is_absolute.
  is_absolute means a sweeping generalisation with words like always, never, every or in all cases
  ("X is always faster"). A plain factual statement, including a negative one such as "Java does not
  support X", is NOT absolute.
  IMPORTANT: Do NOT decide who is right. Only group the claims into sides. Trust is calculated separately.
  Job description requirements count as evidence of current industry practice.
  Compare claims across ALL concepts, not only within one concept: an older claim filed under one concept
  can be contradicted or made outdated by a newer claim filed under another (for example a general rule in
  old notes versus a newer language or software feature described elsewhere).
  If a job description requires a feature or skill, include that requirement claim's id
  in the side that says the feature exists or is current. It is supporting evidence.
  Use "unreliable" ONLY when no other claim addresses the same point. If any other source
  states the opposite, report a "contradiction" or "outdated" conflict with BOTH sides,
  and put every agreeing claim from every source on its side.

TASK 2 - INDUSTRY SKILLS. List the skills the job descriptions ask for that belong to THIS course's subject
  (the topics covered by the faculty notes and textbook). Ignore skills outside the subject, such as
  programming languages, tools, soft skills or a different technical area.
  For each, rate how the FACULTY NOTES (source type faculty_notes) handle it:
  covered, partial, outdated (notes cover it but with outdated information) or missing.
"""


def _load_overrides():
    path = courses.course_file("faculty_overrides.json")
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def reconcile():
    kb = json.loads(courses.course_file("knowledge_base.json").read_text(encoding="utf-8"))
    sources_by_id = {s["id"]: s for s in kb["sources"]}
    claims_by_id = {c["id"]: c for c in kb["claims"]}

    # Compact view of claims for the model (with source type + year, which it needs to spot outdated info)
    claim_lines = [
        {
            "id": c["id"],
            "concept": c["concept_id"],
            "source": c["source_id"],
            "source_type": sources_by_id[c["source_id"]]["type"],
            "year": sources_by_id[c["source_id"]]["year"],
            "claim": c["statement"],
            "quote": c["quote"],
        }
        for c in kb["claims"]
    ]
    user = "CLAIMS:\n" + json.dumps(claim_lines, indent=1, ensure_ascii=False)
    print(f"Sending {len(claim_lines)} claims to {heavy_model()} for conflict detection...")
    result = heavy_json(SYSTEM_PROMPT, user, ReconcilerOutput)

    overrides = _load_overrides()
    status = {cid: "trusted" for cid in claims_by_id}  # default: uncontested claims are trusted
    conflicts = []

    for n, conf in enumerate(result.conflicts, start=1):
        conflict_id = f"conflict_{n}"
        # drop any claim ids the model invented
        sides = []
        for s in conf.sides:
            ids = [cid for cid in s.claim_ids if cid in claims_by_id]
            if ids:
                sides.append({**s.model_dump(), "claim_ids": ids})
        if not sides:
            continue

        all_sources = {claims_by_id[cid]["source_id"] for s in sides for cid in s["claim_ids"]}
        for s in sides:
            s["score"] = score_side(s, claims_by_id, sources_by_id, kb["authority_defaults"], len(all_sources))

        record = {
            "id": conflict_id,
            "concept_id": conf.concept_id,
            "topic": conf.topic,
            "type": conf.conflict_type,
            "summary": conf.summary,
            "sides": sides,
        }

        if len(sides) == 1:
            # single misleading claim: flag it if its trust is low
            side = sides[0]
            if side["score"]["trust"] < UNRELIABLE_THRESHOLD:
                record.update(decision="flagged_unreliable", decided_by="agent",
                              explanation=f"Flagged \"{side['label']}\": low trust score "
                                          f"({side['score']['trust']}) from an old, low-authority or absolute claim.")
                for cid in side["claim_ids"]:
                    status[cid] = "unreliable"
            else:
                record.update(decision="kept", decided_by="agent", explanation="Trust score high enough to keep.")
            conflicts.append(record)
            continue

        ranked = sorted(range(len(sides)), key=lambda i: sides[i]["score"]["trust"], reverse=True)
        winner_idx, loser_idx = ranked[0], ranked[1]
        margin = sides[winner_idx]["score"]["trust"] - sides[loser_idx]["score"]["trust"]

        if conflict_id in overrides:  # faculty decision always wins
            winner_idx = overrides[conflict_id]
            loser_idx = ranked[0] if winner_idx != ranked[0] else ranked[1]
            record.update(decided_by="faculty", explanation="Decided by faculty override.")
        elif margin < CLOSE_CALL_MARGIN:
            record.update(decision="needs_faculty_review", decided_by="agent", winner_side=None,
                          explanation=f"Scores too close to decide automatically (margin {margin:.2f}). Sent to faculty.")
            for s in sides:
                for cid in s["claim_ids"]:
                    status[cid] = "needs_review"
            conflicts.append(record)
            continue
        else:
            record.update(decided_by="agent", explanation=explain(sides[winner_idx], sides[loser_idx]))

        record.update(decision="resolved", winner_side=winner_idx, margin=round(margin, 3))
        loser_status = "outdated" if conf.conflict_type == "outdated" else "superseded"
        for i, s in enumerate(sides):
            for cid in s["claim_ids"]:
                status[cid] = "trusted" if i == winner_idx else loser_status
        conflicts.append(record)

    # ---- Syllabus Freshness Report (score calculated in code) ----
    coverage_points = {"covered": 1.0, "partial": 0.5, "outdated": 0.25, "missing": 0.0}
    skills = [s.model_dump() for s in result.industry_skills]
    for s in skills:  # the model sometimes cites claim ids instead of source ids: map them to their source
        ids = [claims_by_id[x]["source_id"] if x in claims_by_id else x for x in s["demanded_by"]]
        s["demanded_by"] = list(dict.fromkeys(x for x in ids if x in sources_by_id))
    freshness = round(100 * sum(coverage_points[s["faculty_coverage"]] for s in skills) / len(skills)) if skills else None

    claims_out = [{**c, "status": status[c["id"]]} for c in kb["claims"]]
    trusted_kb = {
        "concepts": kb["concepts"],
        "prerequisites": kb["prerequisites"],
        "learning_order": kb["learning_order"],
        "sources": kb["sources"],
        "claims": claims_out,
        "conflicts": conflicts,
        "freshness_report": {
            "score": freshness,
            "skills": skills,
            "missing": [s["skill"] for s in skills if s["faculty_coverage"] == "missing"],
            "outdated": [s["skill"] for s in skills if s["faculty_coverage"] == "outdated"],
        },
    }
    courses.course_file("trusted_kb.json").write_text(json.dumps(trusted_kb, indent=2, ensure_ascii=False), encoding="utf-8")
    storage.save(courses.course_file("trusted_kb.json"))
    return trusted_kb


def set_faculty_override(conflict_id, winning_side_index):
    """Faculty control: force which side of a conflict is trusted, then re-run reconcile()."""
    overrides = _load_overrides()
    overrides[conflict_id] = winning_side_index
    courses.course_file("faculty_overrides.json").write_text(json.dumps(overrides, indent=2), encoding="utf-8")
    storage.save(courses.course_file("faculty_overrides.json"))
