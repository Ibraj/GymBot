import random
from core.templates import get_exercises_in_slot


def pick_exercise(slot: str, last_used: dict, pinned: dict) -> dict:
    """
    Pick the exercise for a slot.
    - If slot is pinned, return pinned exercise.
    - Otherwise exclude last_used exercise and pick from remainder.
    - If only one option exists, it repeats (no alternative).
    """
    if slot in pinned:
        pin_id = pinned[slot]
        exercises = get_exercises_in_slot(slot)
        pinned_ex = next((e for e in exercises if e["id"] == pin_id), None)
        if pinned_ex:
            return pinned_ex

    exercises = get_exercises_in_slot(slot)
    if len(exercises) == 1:
        return exercises[0]

    last_id = last_used.get(slot)
    pool = [e for e in exercises if e["id"] != last_id]
    return random.choice(pool)


def get_alternative(slot: str, current_exercise_id: str, pinned: dict) -> dict | None:
    """
    Return a random alternative exercise for a slot, excluding current.
    Returns None if no alternative exists.
    """
    if slot in pinned:
        return None  # Pinned slots cannot be swapped

    exercises = get_exercises_in_slot(slot)
    pool = [e for e in exercises if e["id"] != current_exercise_id]
    if not pool:
        return None
    return random.choice(pool)
