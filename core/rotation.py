import random
from core.templates import get_exercises_in_slot


def _filter_by_difficulty(exercises: list, intensity: str) -> list:
    """Filter exercise pool to those matching the intensity level."""
    filtered = [e for e in exercises if intensity in e.get("difficulty", ["easy","moderate","hardcore"])]
    # Fallback: if no exercises match (shouldn't happen), return full pool
    return filtered if filtered else exercises


def pick_exercise(slot: str, last_used: dict, pinned: dict, intensity: str = "moderate") -> dict:
    """
    Pick the exercise for a slot.
    - Respects difficulty filtering by intensity
    - If slot is pinned, return pinned exercise
    - Excludes last_used exercise from pool
    - If only one option after filtering, it repeats
    """
    if slot in pinned:
        pin_id    = pinned[slot]
        exercises = get_exercises_in_slot(slot)
        pinned_ex = next((e for e in exercises if e["id"] == pin_id), None)
        if pinned_ex:
            return pinned_ex

    exercises = get_exercises_in_slot(slot)
    pool      = _filter_by_difficulty(exercises, intensity)

    if len(pool) == 1:
        return pool[0]

    last_id = last_used.get(slot)
    options = [e for e in pool if e["id"] != last_id]
    if not options:
        options = pool  # all filtered exercises were last used

    return random.choice(options)


def get_alternative(slot: str, current_exercise_id: str, pinned: dict, intensity: str = "moderate") -> dict | None:
    """
    Return a random alternative exercise for a slot, excluding current.
    Respects difficulty filtering.
    Returns None if no alternative exists.
    """
    if slot in pinned:
        return None

    exercises = get_exercises_in_slot(slot)
    pool      = _filter_by_difficulty(exercises, intensity)
    options   = [e for e in pool if e["id"] != current_exercise_id]

    if not options:
        return None
    return random.choice(options)