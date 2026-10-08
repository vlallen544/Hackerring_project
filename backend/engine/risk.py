# Risk engine: predicts learning gaps BEFORE they happen (pure Python, every factor visible)
from datetime import date

# risk = how likely the student is to struggle with an upcoming concept
WEIGHTS = {"prerequisite_weakness": 0.65, "forgetting": 0.15, "pace_lag": 0.10, "misconception": 0.10}
RISK_THRESHOLD = 0.45         # at or above this, the path is redesigned
UNTESTED_MASTERY = 0.5        # an untested prerequisite counts as "unknown", not weak
FORGET_DAYS = 21              # practice older than this counts as fully faded
STRONG = 0.75
CHALLENGE_PREREQ = 0.85       # all prerequisites at least this strong -> challenge track


def forgetting(last_practiced, today=None):
    """0.0 if practised today, rising to 1.0 after FORGET_DAYS."""
    if not last_practiced:
        return 0.0
    today = today or date.today()
    days = (today - date.fromisoformat(last_practiced)).days
    return max(0.0, min(1.0, days / FORGET_DAYS))


def pace_lag(path_items, today=None):
    """Share of path items already due that the student has not finished."""
    today = (today or date.today()).isoformat()
    due = [p for p in path_items if p["scheduled_for"] and p["scheduled_for"] <= today]
    if not due:
        return 0.0
    return sum(1 for p in due if p["status"] != "done") / len(due)


def concept_risk(prereqs, mastery, misconceptions_by_concept, lag, today=None):
    """
    prereqs: direct prerequisite concept ids
    mastery: {concept_id: {"score", "last_practiced"}}
    Returns (risk, factors, weakest_prereq) or (0, {}, None) if the concept has no prerequisites.
    """
    if not prereqs:
        return 0.0, {}, None
    effective = {p: (mastery[p]["score"] if p in mastery else UNTESTED_MASTERY) for p in prereqs}
    weakest = min(effective, key=effective.get)
    factors = {
        "prerequisite_weakness": round(1 - effective[weakest], 3),
        "forgetting": round(forgetting(mastery.get(weakest, {}).get("last_practiced"), today), 3),
        "pace_lag": round(lag, 3),
        "misconception": 1.0 if misconceptions_by_concept.get(weakest) else 0.0,
    }
    risk = sum(WEIGHTS[k] * v for k, v in factors.items())
    return round(min(risk, 1.0), 3), factors, weakest


def own_risk(concept_id, mastery, misconceptions_by_concept, lag, today=None):
    """Risk from the concept's OWN tested mastery. None if untested or already strong."""
    if concept_id not in mastery or mastery[concept_id]["score"] >= STRONG:
        return None
    factors = {
        "prerequisite_weakness": round(1 - mastery[concept_id]["score"], 3),  # here: the concept's own weakness
        "forgetting": round(forgetting(mastery[concept_id].get("last_practiced"), today), 3),
        "pace_lag": round(lag, 3),
        "misconception": 1.0 if misconceptions_by_concept.get(concept_id) else 0.0,
    }
    risk = sum(WEIGHTS[k] * v for k, v in factors.items())
    return round(min(risk, 1.0), 3), factors


def risk_band(risk):
    if risk >= RISK_THRESHOLD:
        return "high"
    if risk >= 0.25:
        return "medium"
    return "low"


def all_prereqs_strong(prereqs, mastery):
    return bool(prereqs) and all(p in mastery and mastery[p]["score"] >= CHALLENGE_PREREQ for p in prereqs)
