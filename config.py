import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN     = os.getenv("BOT_TOKEN")
DB_PATH       = os.getenv("DB_PATH", "gymbot.db")
OWNER_CHAT_ID = int(os.getenv("OWNER_CHAT_ID", "0"))

# ── Intensity ─────────────────────────────────────────────────────────────────
INTENSITY = {
    "easy": {
        "sets": (2, 3), "reps": (10, 15), "rest": "45–60s", "rest_seconds": 52,
        "increment_standard": 2.5, "increment_lower": 2.5,
        "decrement_standard": 2.5, "decrement_lower": 2.5,
    },
    "moderate": {
        "sets": (3, 4), "reps": (8, 12), "rest": "60–90s", "rest_seconds": 75,
        "increment_standard": 2.5, "increment_lower": 2.5,
        "decrement_standard": 2.5, "decrement_lower": 2.5,
    },
    "hardcore": {
        "sets": (4, 5), "reps": (4, 10), "rest": "90–150s", "rest_seconds": 120,
        "increment_standard": 5.0, "increment_lower": 10.0,
        "decrement_standard": 5.0, "decrement_lower": 5.0,
    },
}

# ── Valid days per split ───────────────────────────────────────────────────────
VALID_DAYS = {
    "ppl":         ["push", "pull", "legs"],
    "pplul":       ["push", "pull", "legs", "upper", "lower"],
    "upper_lower": ["upper", "lower"],
    "full_body":   ["full"],
}

# ── Required movement patterns per day ───────────────────────────────────────
# If any of these are missing after slot selection, the engine swaps in a fix
DAY_REQUIRED_PATTERNS = {
    "push":  ["horizontal_push", "vertical_push"],
    "pull":  ["vertical_pull", "horizontal_pull"],
    "legs":  ["squat", "hinge"],
    "upper": ["horizontal_push", "vertical_pull"],
    "lower": ["squat", "hinge"],
    "full":  ["squat", "horizontal_push", "vertical_pull", "hinge"],
}

# ── Warmup suggestions (prepended to workout message, not logged) ─────────────
DAY_WARMUP = {
    "push":  ["Band External Rotation × 15", "YTWL × 10 each"],
    "pull":  ["Band Pull-Apart × 20", "Scapular Pull-ups × 10"],
    "legs":  ["Hip 90/90 Stretch × 60s", "Leg Swings × 15 each side"],
    "upper": ["Band External Rotation × 15", "Face Pull × 15"],
    "lower": ["Hip 90/90 Stretch × 60s", "Cossack Squat × 8 each side"],
    "full":  ["Hip 90/90 Stretch × 60s", "Band Pull-Apart × 20"],
}

# ── Extra slots added per intensity (on top of base template) ────────────────
EXTRA_SLOTS = {
    "ppl": {
        "push":  {"moderate": ["shoulder_rear"], "hardcore": ["shoulder_rear","chest_upper"]},
        "pull":  {"moderate": ["lats_horizontal"], "hardcore": ["lats_horizontal","biceps_long"]},
        "legs":  {"moderate": ["quads_isolation"], "hardcore": ["quads_isolation","hamstrings_curl"]},
    },
    "pplul": {
        "push":  {"moderate": ["shoulder_rear"], "hardcore": ["shoulder_rear","chest_upper"]},
        "pull":  {"moderate": ["lats_horizontal"], "hardcore": ["lats_horizontal","biceps_long"]},
        "legs":  {"moderate": ["quads_isolation"], "hardcore": ["quads_isolation","hamstrings_curl"]},
        "upper": {"moderate": ["shoulder_rear"], "hardcore": ["shoulder_rear","chest_upper"]},
        "lower": {"moderate": ["quads_isolation"], "hardcore": ["quads_isolation","hamstrings_curl"]},
    },
    "upper_lower": {
        "upper": {"moderate": ["shoulder_rear"], "hardcore": ["shoulder_rear","chest_upper"]},
        "lower": {"moderate": ["quads_isolation"], "hardcore": ["quads_isolation","hamstrings_curl"]},
    },
    "full_body": {
        "full":  {"moderate": ["quads_isolation"], "hardcore": ["quads_isolation","hamstrings_curl"]},
    },
}

# ── Deload ────────────────────────────────────────────────────────────────────
DELOAD_WEEK                = 4
DELOAD_WEIGHT_FACTOR       = 0.6
CONSECUTIVE_FAIL_THRESHOLD = 3