"""Deterministic plan diffing — what changed between two plan versions.

This is what powers "drive moved earlier": the planner reorders, and this
reports added / removed / moved / unchanged items without an LLM.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def _key(item: Any, index: int) -> str:
    if isinstance(item, Mapping):
        for field in ("id", "concept", "key", "name", "title"):
            if field in item:
                return str(item[field])
    if hasattr(item, "concept"):
        return item.concept
    return str(index)


def _same(a: Any, b: Any, ignore: Iterable[str] = ("position", "index")) -> bool:
    """Structural equality on dicts, ignoring ordering metadata."""
    if isinstance(a, Mapping) and isinstance(b, Mapping):
        keys = set(a) | set(b)
        return all(a.get(k) == b.get(k) for k in keys if k not in set(ignore))
    return a == b


def diff(old: list, new: list) -> dict:
    """Compare two ordered plan versions.

    Returns keys: added, removed, moved, modified, unchanged, reorder.
    """
    old_map = {_key(v, i): v for i, v in enumerate(old)}
    new_map = {_key(v, i): v for i, v in enumerate(new)}
    old_keys = list(old_map)
    new_keys = list(new_map)

    added = [k for k in new_keys if k not in old_map]
    removed = [k for k in old_keys if k not in new_map]

    shared = [k for k in new_keys if k in old_map]
    modified = [k for k in shared if not _same(old_map[k], new_map[k])]

    # Order relative to other shared items: count pairs that changed rank.
    old_shared = [k for k in old_keys if k in new_map]
    new_shared = [k for k in new_keys if k in old_map]
    moved = [k for k, a in zip(new_shared, old_shared) if k != a]
    moved = list(dict.fromkeys(moved))

    unchanged = [k for k in shared if k not in modified and k not in moved]

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "moved": moved,
        "unchanged": unchanged,
        "reorder": moved != [],
        "summary": _summary(added, removed, modified, moved),
    }


def _summary(added, removed, modified, moved) -> str:
    parts = []
    if added:
        parts.append(f"{len(added)} added")
    if removed:
        parts.append(f"{len(removed)} removed")
    if modified:
        parts.append(f"{len(modified)} modified")
    if moved:
        parts.append(f"{len(moved)} moved")
    return "; ".join(parts) if parts else "no changes"


def diff_plan(old_plan: Mapping[str, Any], new_plan: Mapping[str, Any]) -> dict:
    """Diff two plan objects keyed on `items`."""
    return diff(list(old_plan.get("items", [])), list(new_plan.get("items", [])))
