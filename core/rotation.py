import random
from core.templates import get_exercises_in_slot
from config import DAY_REQUIRED_PATTERNS

PRIORITY_ORDER = {"primary": 0, "secondary": 1, "isolation": 2}


def _by_difficulty(exercises: list, intensity: str) -> list:
    pool = [e for e in exercises if intensity in e.get("difficulty", ["easy","moderate","hardcore"])]
    return pool if pool else exercises


def _combo(e: dict) -> tuple:
    return (e.get("movement_type", ""), e.get("angle", ""))


def pick_exercise(slot: str, last_used: dict, pinned: dict,
                  intensity: str = "moderate",
                  used_combos: set = None,
                  used_ids: set = None) -> dict:
    """
    Pick one exercise for a slot.
    Priority: pinned > difficulty filter > tier order > no-duplicate-id > no-duplicate-combo
    """
    if used_combos is None:
        used_combos = set()
    if used_ids is None:
        used_ids = set()

    if slot in pinned:
        exercises = get_exercises_in_slot(slot)
        pinned_ex = next((e for e in exercises if e["id"] == pinned[slot]), None)
        if pinned_ex:
            return pinned_ex

    pool    = _by_difficulty(get_exercises_in_slot(slot), intensity)
    last_id = last_used.get(slot)

    for tier in ["primary", "secondary", "isolation"]:
        tier_pool = [e for e in pool if e.get("priority") == tier]
        if not tier_pool:
            continue

        # Best: no id conflict, no combo conflict, not last_used
        candidates = [e for e in tier_pool
                      if e["id"] not in used_ids
                      and _combo(e) not in used_combos
                      and e["id"] != last_id]
        if candidates:
            return random.choice(candidates)

        # Relax last_used
        candidates = [e for e in tier_pool
                      if e["id"] not in used_ids
                      and _combo(e) not in used_combos]
        if candidates:
            return random.choice(candidates)

        # Relax combo constraint
        candidates = [e for e in tier_pool if e["id"] not in used_ids]
        if candidates:
            return random.choice(candidates)

    # Absolute fallback — just avoid exact id repeat
    candidates = [e for e in pool if e["id"] not in used_ids] or pool
    return random.choice(candidates)


def build_session(slots: list, last_used: dict, pinned: dict,
                  intensity: str, split: str, day: str) -> list:
    """
    Build full session with dedup and required pattern guarantees.
    """
    used_combos: set = set()
    used_ids:    set = set()
    selected:   list = []

    for slot in slots:
        ex = pick_exercise(slot, last_used, pinned, intensity, used_combos, used_ids)
        ex_copy = dict(ex)
        ex_copy["slot"] = slot
        selected.append(ex_copy)
        used_combos.add(_combo(ex))
        used_ids.add(ex["id"])  # ← this is what was missing

    # Verify required patterns
    required   = DAY_REQUIRED_PATTERNS.get(day, [])
    used_types = {e.get("movement_type") for e in selected}
    missing    = [p for p in required if p not in used_types]

    if missing:
        selected = _fix_missing_patterns(
            selected, slots, missing, last_used, pinned, intensity, used_combos, used_ids
        )

    return selected


def _fix_missing_patterns(selected, slots, missing_patterns,
                           last_used, pinned, intensity,
                           used_combos, used_ids):
    for pattern in missing_patterns:
        for i, (slot, ex) in enumerate(zip(slots, selected)):
            if ex.get("priority") == "primary":
                continue
            pool = _by_difficulty(get_exercises_in_slot(slot), intensity)
            candidates = [
                e for e in pool
                if e.get("movement_type") == pattern
                and e["id"] not in used_ids
                and _combo(e) not in used_combos
            ]
            if candidates:
                replacement = random.choice(candidates)
                rep_copy = dict(replacement)
                rep_copy["slot"] = slot
                used_combos.discard(_combo(selected[i]))
                used_ids.discard(selected[i]["id"])
                used_combos.add(_combo(replacement))
                used_ids.add(replacement["id"])
                selected[i] = rep_copy
                break
    return selected


def get_alternative(slot: str, current_exercise_id: str, pinned: dict,
                    intensity: str = "moderate",
                    used_combos: set = None) -> dict | None:
    if slot in pinned:
        return None
    if used_combos is None:
        used_combos = set()

    pool = _by_difficulty(get_exercises_in_slot(slot), intensity)

    for tier in ["primary", "secondary", "isolation"]:
        candidates = [
            e for e in pool
            if e.get("priority") == tier
            and e["id"] != current_exercise_id
            and _combo(e) not in used_combos
        ]
        if candidates:
            return random.choice(candidates)

    candidates = [e for e in pool if e["id"] != current_exercise_id]
    return random.choice(candidates) if candidates else None