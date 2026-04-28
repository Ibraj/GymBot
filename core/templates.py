import json
import os

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "exercises.json")

with open(_DATA_PATH) as f:
    _DATA = json.load(f)

CATEGORIES = _DATA["categories"]
TEMPLATES  = _DATA["templates"]


def get_slots(split: str, day: str) -> list[str]:
    return TEMPLATES[split][day]


def get_category(slot: str) -> dict:
    return CATEGORIES[slot]


def get_exercise(exercise_id: str) -> dict | None:
    for cat in CATEGORIES.values():
        for ex in cat["exercises"]:
            if ex["id"] == exercise_id:
                return ex
    return None


def get_exercises_in_slot(slot: str) -> list[dict]:
    return CATEGORIES[slot]["exercises"]


def is_lower_body(slot: str) -> bool:
    return CATEGORIES[slot].get("is_lower", False)


def video_url(video_ref: str) -> str:
    """Handles both short YouTube IDs and full URLs (search links for new exercises)."""
    if video_ref.startswith("http"):
        return video_ref
    return f"https://youtube.com/watch?v={video_ref}"