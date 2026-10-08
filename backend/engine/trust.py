# Trust engine: scores competing sides of a conflict deterministically (no LLM math)
from datetime import date

# Weights are deliberately simple so they can be explained to faculty and judges.
WEIGHTS = {"recency": 0.35, "authority": 0.30, "agreement": 0.25, "specificity": 0.10}
ABSOLUTE_PENALTY = 0.15      # claims using "always / never / every" are less reliable
CLOSE_CALL_MARGIN = 0.10     # if both sides score this close, ask the faculty instead of deciding
UNRELIABLE_THRESHOLD = 0.40  # a lone claim scoring below this is flagged as unreliable
CURRENT_YEAR = date.today().year


def recency_score(year):
    """1.0 for this year, falling to 0.0 for material 10+ years old."""
    return max(0.0, min(1.0, 1 - (CURRENT_YEAR - year) / 10))


def score_side(side, claims_by_id, sources_by_id, authority_defaults, total_sources_in_conflict):
    """Returns each factor and the total trust for one side of a conflict."""
    src_ids = {claims_by_id[cid]["source_id"] for cid in side["claim_ids"]}
    srcs = [sources_by_id[s] for s in src_ids]

    factors = {
        "recency": max(recency_score(s["year"]) for s in srcs),
        "authority": max(authority_defaults.get(s["type"], 0.5) for s in srcs),
        # a lone claim with no opponent gets a neutral 0.5 for agreement
        "agreement": len(src_ids) / total_sources_in_conflict if total_sources_in_conflict > len(src_ids) else 0.5,
        "specificity": 1.0 if side["is_specific"] else 0.0,
    }
    total = sum(WEIGHTS[k] * v for k, v in factors.items())
    if side["is_absolute"]:
        total -= ABSOLUTE_PENALTY
    return {
        "factors": {k: round(v, 2) for k, v in factors.items()},
        "absolute_penalty": side["is_absolute"],
        "sources": sorted(src_ids),
        "newest_year": max(s["year"] for s in srcs),
        "trust": round(max(total, 0.0), 3),
    }


def explain(winner, loser):
    """Plain-language reason built from the factors (deterministic, no LLM)."""
    w, l = winner["score"], loser["score"]
    reasons = []
    if w["newest_year"] > l["newest_year"]:
        reasons.append(f"newer source ({w['newest_year']} vs {l['newest_year']})")
    if len(w["sources"]) > len(l["sources"]):
        reasons.append(f"{len(w['sources'])} sources agree vs {len(l['sources'])}")
    if w["factors"]["authority"] > l["factors"]["authority"]:
        reasons.append("higher-authority source")
    if w["factors"]["specificity"] > l["factors"]["specificity"]:
        reasons.append("more specific (gives versions or reasons)")
    if l["absolute_penalty"]:
        reasons.append("the other side makes an absolute 'always/never' claim")
    because = ", ".join(reasons) if reasons else "higher overall trust score"
    return f"Trusted \"{winner['label']}\" over \"{loser['label']}\" because of: {because}."
