# Mastery engine: turns viva/quiz scores into per-concept mastery and confidence calibration (pure Python)

NEW_EVIDENCE_WEIGHT = 0.6   # how much a new viva counts vs. previous mastery
CALIBRATION_GAP = 0.25      # confidence vs. mastery gap that counts as over/under-confident


def concept_score(scores):
    """Average of all answer scores for a concept in one session (first answer + follow-ups)."""
    return sum(scores) / len(scores) if scores else None


def blend(old, new):
    """Combine previous mastery with new evidence. First evidence is taken as-is."""
    if old is None:
        return new
    return NEW_EVIDENCE_WEIGHT * new + (1 - NEW_EVIDENCE_WEIGHT) * old


def confidence_to_unit(rating):
    """Student rates confidence 1-5; store it as 0.0-1.0."""
    return (max(1, min(5, int(rating))) - 1) / 4


def calibration(confidence, mastery):
    """Compares how sure the student felt with how well they actually did."""
    gap = confidence - mastery
    if gap > CALIBRATION_GAP:
        return "overconfident"
    if gap < -CALIBRATION_GAP:
        return "underconfident"
    return "calibrated"


def mastery_band(score):
    if score >= 0.75:
        return "strong"
    if score >= 0.45:
        return "developing"
    return "weak"
