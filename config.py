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
DAY_REQUIRED_PATTERNS = {
    "push":  ["horizontal_push", "vertical_push"],
    "pull":  ["vertical_pull", "horizontal_pull"],
    "legs":  ["squat", "hinge"],
    "upper": ["horizontal_push", "vertical_pull"],
    "lower": ["squat", "hinge"],
    "full":  ["squat", "horizontal_push", "vertical_pull", "hinge"],
}

# ── Warmup ────────────────────────────────────────────────────────────────────
DAY_WARMUP = {
    "push":  ["Band External Rotation × 15", "YTWL × 10 each"],
    "pull":  ["Band Pull-Apart × 20", "Scapular Pull-ups × 10"],
    "legs":  ["Hip 90/90 Stretch × 60s", "Leg Swings × 15 each side"],
    "upper": ["Band External Rotation × 15", "Face Pull × 15"],
    "lower": ["Hip 90/90 Stretch × 60s", "Cossack Squat × 8 each side"],
    "full":  ["Hip 90/90 Stretch × 60s", "Band Pull-Apart × 20"],
}

# ── Base templates (lean — easy-level slot count) ────────────────────────────
# EXTRA_SLOTS layers on top per intensity
BASE_TEMPLATES = {
    "ppl": {
        "push":  ["chest_mid", "shoulder_front", "shoulder_side", "triceps_lateral", "core"],
        "pull":  ["lats_vertical", "lats_horizontal", "biceps_short", "traps_upper", "core"],
        "legs":  ["quads_compound", "hamstrings_hinge", "glutes_max", "calves_gastro", "core"],
    },
    "pplul": {
        "push":  ["chest_mid", "shoulder_front", "shoulder_side", "triceps_lateral", "core"],
        "pull":  ["lats_vertical", "lats_horizontal", "biceps_short", "traps_upper", "core"],
        "legs":  ["quads_compound", "hamstrings_hinge", "glutes_max", "calves_gastro", "core"],
        "upper": ["chest_mid", "lats_vertical", "shoulder_front", "triceps_lateral", "biceps_short", "core"],
        "lower": ["quads_compound", "hamstrings_hinge", "glutes_max", "calves_gastro", "core"],
    },
    "upper_lower": {
        "upper": ["chest_mid", "lats_vertical", "shoulder_front", "triceps_lateral", "biceps_short", "core"],
        "lower": ["quads_compound", "hamstrings_hinge", "glutes_max", "calves_gastro", "core"],
    },
    "full_body": {
        "full":  ["quads_compound", "chest_mid", "lats_vertical", "hamstrings_hinge", "glutes_max", "core"],
    },
}

# ── Extra slots per intensity ─────────────────────────────────────────────────
EXTRA_SLOTS = {
    "ppl": {
        "push": {
            "moderate": ["chest_upper", "shoulder_rear", "triceps_long"],
            "hardcore": ["chest_upper", "chest_lower", "shoulder_rear", "triceps_long"],
        },
        "pull": {
            "moderate": ["upper_back", "biceps_long", "brachialis"],
            "hardcore": ["upper_back", "biceps_long", "brachialis", "forearms"],
        },
        "legs": {
            "moderate": ["quads_isolation", "hamstrings_curl", "calves_soleus"],
            "hardcore": ["quads_isolation", "hamstrings_curl", "glutes_med", "calves_soleus"],
        },
    },
    "pplul": {
        "push": {
            "moderate": ["chest_upper", "shoulder_rear", "triceps_long"],
            "hardcore": ["chest_upper", "chest_lower", "shoulder_rear", "triceps_long"],
        },
        "pull": {
            "moderate": ["upper_back", "biceps_long", "brachialis"],
            "hardcore": ["upper_back", "biceps_long", "brachialis", "forearms"],
        },
        "legs": {
            "moderate": ["quads_isolation", "hamstrings_curl", "calves_soleus"],
            "hardcore": ["quads_isolation", "hamstrings_curl", "glutes_med", "calves_soleus"],
        },
        "upper": {
            "moderate": ["chest_upper", "shoulder_side", "shoulder_rear", "biceps_long", "traps_upper"],
            "hardcore": ["chest_upper", "shoulder_side", "shoulder_rear", "triceps_long", "biceps_long", "traps_upper"],
        },
        "lower": {
            "moderate": ["quads_isolation", "hamstrings_curl", "calves_soleus"],
            "hardcore": ["quads_isolation", "hamstrings_curl", "glutes_med", "calves_soleus"],
        },
    },
    "upper_lower": {
        "upper": {
            "moderate": ["chest_upper", "shoulder_side", "shoulder_rear", "biceps_long", "traps_upper"],
            "hardcore": ["chest_upper", "chest_lower", "shoulder_side", "shoulder_rear", "triceps_long", "biceps_long", "traps_upper"],
        },
        "lower": {
            "moderate": ["quads_isolation", "hamstrings_curl", "calves_soleus"],
            "hardcore": ["quads_isolation", "hamstrings_curl", "glutes_med", "calves_soleus"],
        },
    },
    "full_body": {
        "full": {
            "moderate": ["shoulder_front", "biceps_short", "calves_gastro"],
            "hardcore": ["shoulder_front", "triceps_lateral", "biceps_short", "calves_gastro"],
        },
    },
}

# ── Session slot counts by intensity ─────────────────────────────────────────
# For reference — actual counts driven by BASE_TEMPLATES + EXTRA_SLOTS above
# push:  easy=5  moderate=8  hardcore=9
# pull:  easy=5  moderate=8  hardcore=9
# legs:  easy=5  moderate=8  hardcore=9

# ── Deload ────────────────────────────────────────────────────────────────────
DELOAD_WEEK                = 4
DELOAD_WEIGHT_FACTOR       = 0.6
CONSECUTIVE_FAIL_THRESHOLD = 3