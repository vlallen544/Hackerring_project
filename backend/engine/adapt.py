# Adaptation engine: decides HOW a student should be taught (level, format) in plain Python, with reasons.
# The Tutor agent then writes the lesson; it never chooses the level or format itself.

LEVELS = ["foundation", "standard", "challenge"]
STYLE_TO_FORMAT = {"reading": "text", "listening": "audio", "visual": "visual", "practice": "practice"}
# If a format did not work, re-teach in a different one
ALTERNATIVE_FORMAT = {"text": "visual", "audio": "visual", "visual": "practice", "practice": "visual"}
STYLE_SWITCH_MARGIN = 0.15   # a format must beat the stated one by this much to become the learned style
MIN_CHECKS_PER_FORMAT = 2    # evidence needed before trusting a format's average


def decide_level(concept_mastery, prereq_masteries):
    """Level from the student's measured performance (viva / earlier checks)."""
    if concept_mastery is not None:
        if concept_mastery < 0.45:
            return "foundation", f"Mastery {concept_mastery:.2f} is weak, so start from the basics with more examples."
        if concept_mastery < 0.75:
            return "standard", f"Mastery {concept_mastery:.2f} is developing, so teach at the normal level."
        return "challenge", f"Mastery {concept_mastery:.2f} is strong, so add interview-level challenge content."
    if prereq_masteries:
        weakest = min(prereq_masteries.values())
        name = min(prereq_masteries, key=prereq_masteries.get)
        if weakest < 0.45:
            return "foundation", f"Not tested yet, but prerequisite '{name}' is weak ({weakest:.2f}), so recap it first."
        return "standard", f"Not tested yet; prerequisites look fine (weakest {weakest:.2f})."
    return "standard", "No performance data yet, so teach at the normal level."


def decide_format(stated_style, learned_style):
    if learned_style:
        return learned_style, f"Learned from results: '{learned_style}' lessons work best for this student."
    fmt = STYLE_TO_FORMAT.get(stated_style, "text")
    return fmt, f"Student's stated preference is '{stated_style}'."


def learned_style(checks, stated_style):
    """checks: rows with format + score. Returns a better-performing format, or None to keep the stated one."""
    by_format = {}
    for c in checks:
        by_format.setdefault(c["format"], []).append(c["score"])
    averages = {f: sum(s) / len(s) for f, s in by_format.items() if len(s) >= MIN_CHECKS_PER_FORMAT}
    if not averages:
        return None
    best = max(averages, key=averages.get)
    stated = STYLE_TO_FORMAT.get(stated_style, "text")
    if best != stated and averages[best] >= averages.get(stated, 0) + STYLE_SWITCH_MARGIN:
        return best
    return None


def next_step_after_check(score, level, fmt):
    """What the system does after a practice answer: move on, or re-teach differently."""
    if score >= 0.75:
        return {"action": "advance", "reason": "Answered well, ready for the next topic."}
    if score >= 0.4:
        return {"action": "practice_more", "level": level, "format": fmt,
                "reason": "Partly right: one more practice round at the same level."}
    lower = LEVELS[max(0, LEVELS.index(level) - 1)]
    alt = ALTERNATIVE_FORMAT.get(fmt, "visual")
    return {"action": "reteach", "level": lower, "format": alt,
            "reason": f"Struggled with the {fmt} lesson: re-teaching at {lower} level as a {alt} lesson."}
