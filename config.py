import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH   = os.getenv("DB_PATH", "gymbot.db")

# ── Intensity definitions ────────────────────────────────────────────────────
INTENSITY = {
    "easy": {
        "sets": (2, 3),
        "reps": (10, 15),
        "rest": "45–60s",
        "increment_standard": 2.5,
        "increment_lower":    2.5,
        "decrement_standard": 2.5,
        "decrement_lower":    2.5,
    },
    "moderate": {
        "sets": (3, 4),
        "reps": (8, 12),
        "rest": "60–90s",
        "increment_standard": 2.5,
        "increment_lower":    2.5,
        "decrement_standard": 2.5,
        "decrement_lower":    2.5,
    },
    "hardcore": {
        "sets": (4, 5),
        "reps": (4, 10),
        "rest": "90–150s",
        "increment_standard": 5.0,
        "increment_lower":    10.0,
        "decrement_standard": 5.0,
        "decrement_lower":    5.0,
    },
}

# ── Valid split → day combinations ───────────────────────────────────────────
VALID_DAYS = {
    "ppl":         ["push", "pull", "legs"],
    "pplul":       ["push", "pull", "legs", "upper", "lower"],
    "upper_lower": ["upper", "lower"],
    "full_body":   ["full"],
}

DELOAD_WEEK        = 4      # every 4th week
DELOAD_WEIGHT_FACTOR = 0.6  # 60% of normal weight
CONSECUTIVE_FAIL_THRESHOLD = 3  # sessions before single-exercise deload
