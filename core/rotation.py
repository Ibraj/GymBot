import random
from core.templates import get_exercises_in_slot, CATEGORIES
from config import DAY_REQUIRED_PATTERNS


# ── Difficulty filter ─────────────────────────────────────────────────────────

def _by_difficulty(exercises: list, intensity: str) -> list:
    pool = [e for e in exercises if intensity in e.get("difficulty", ["easy","moderate","hardcore"])]
    return pool if pool else exercises


# ── Priority sort ─────────────────────────────────────────────────────────────

PRIORITY_ORDER = {"primary": 0, "secondary": 1, "isolation": 2}

def _by_priority(exercises: list) -> list:
    """Return exercises sorted primary → secondary → isolation."""
    return sorted(exercises, key=lambda e: PRIORITY_ORDER.get(e.get("priority","secondary"), 1))


# ── Dedup key ─────────────────────────────────────────────────────────────────

def _combo(e: dict) -> tuple:
    return (e.get("movement_type", ""), e.get("angle", ""))


# ── Core selection ────────────────────────────────────────────────────────────

def pick_exercise(slot: str, last_used: dict, pinned: dict,
                  intensity: str = "moderate",
                  used_combos: set | None = None) -> dict:
    """
    Pick one exercise for a slot.
    Respects: pinned > difficulty > priority > dedup (movement_type+angle) > last_used
    """
    if used_combos is None:
        used_combos = set()

    # Pinned overrides everything
    if slot in pinned:
        exercises = get_exercises_in_slot(slot)
        pinned_ex = next((e for e in exercises if e["id"] == pinned[slot]), None)
        if pinned_ex:
            return pinned_ex

    pool = _by_difficulty(get_exercises_in_slot(slot), intensity)
    last_id = last_used.get(slot)

    # Try tiers in order: primary → secondary → isolation
    for tier in ["primary", "secondary", "isolation"]:
        tier_pool = [e for e in pool if e.get("priority") == tier]
        if not tier_pool:
            continue

        # Prefer no dedup conflict and no last_used repeat
        candidates = [e for e in tier_pool
                      if _combo(e) not in used_combos and e["id"] != last_id]
        if candidates:
            return random.choice(candidates)

        # Relax last_used constraint
        candidates = [e for e in tier_pool if _combo(e) not in used_combos]
        if candidates:
            return random.choice(candidates)

    # Last resort: pick anything from difficulty pool
    candidates = [e for e in pool if e["id"] != last_id] or pool
    return random.choice(candidates)


# ── Session builder ───────────────────────────────────────────────────────────

def build_session(slots: list, last_used: dict, pinned: dict,
                  intensity: str, split: str, day: str) -> list:
    """
    Build a full session exercise list with:
    - Priority-ordered selection
    - Cross-slot dedup (no same movement_type+angle twice)
    - Required pattern guarantees
    Returns list of exercise dicts (with slot injected).
    """
    used_combos: set = set()
    selected: list[dict] = []

    for slot in slots:
        ex = pick_exercise(slot, last_used, pinned, intensity, used_combos)
        ex_copy = dict(ex)
        ex_copy["slot"] = slot
        selected.append(ex_copy)
        used_combos.add(_combo(ex))

    # ── Verify required patterns ──────────────────────────────────────────────
    required = DAY_REQUIRED_PATTERNS.get(day, [])
    used_types = {e.get("movement_type") for e in selected}
    missing = [p for p in required if p not in used_types]

    if missing:
        selected = _fix_missing_patterns(
            selected, slots, missing, last_used, pinned, intensity, used_combos
        )

    return selected


def _fix_missing_patterns(selected, slots, missing_patterns,
                           last_used, pinned, intensity, used_combos):
    """
    Swap exercises in non-primary slots to satisfy missing required patterns.
    """
    for pattern in missing_patterns:
        # Find a slot that can satisfy this pattern
        for i, (slot, ex) in enumerate(zip(slots, selected)):
            if ex.get("priority") == "primary":
                continue  # don't replace primaries

            pool = _by_difficulty(get_exercises_in_slot(slot), intensity)
            candidates = [
                e for e in pool
                if e.get("movement_type") == pattern
                and _combo(e) not in used_combos
            ]
            if candidates:
                replacement = random.choice(candidates)
                rep_copy = dict(replacement)
                rep_copy["slot"] = slot
                # Remove old combo, add new
                used_combos.discard(_combo(selected[i]))
                used_combos.add(_combo(replacement))
                selected[i] = rep_copy
                break

    return selected


# ── Alternative (swap) ────────────────────────────────────────────────────────

def get_alternative(slot: str, current_exercise_id: str, pinned: dict,
                    intensity: str = "moderate",
                    used_combos: set | None = None) -> dict | None:
    """Return a replacement exercise for a slot, respecting priority and dedup."""
    if slot in pinned:
        return None

    if used_combos is None:
        used_combos = set()

    pool = _by_difficulty(get_exercises_in_slot(slot), intensity)
    sorted_pool = _by_priority(pool)

    for tier in ["primary", "secondary", "isolation"]:
        candidates = [
            e for e in sorted_pool
            if e.get("priority") == tier
            and e["id"] != current_exercise_id
            and _combo(e) not in used_combos
        ]
        if candidates:
            return random.choice(candidates)

    # Fallback: anything different
    candidates = [e for e in pool if e["id"] != current_exercise_id]
    return random.choice(candidates) if candidates else None