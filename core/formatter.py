from config import INTENSITY
from core.templates import video_url

DOTS = {"easy": "🟢", "moderate": "🟡", "hardcore": "🔴"}

SLOT_EMOJI = {
    # Chest
    "chest_upper":        "🏋️",
    "chest_mid":          "💪",
    "chest_lower":        "🔻",
    # Shoulders
    "shoulder_front":     "🔺",
    "shoulder_side":      "↔️",
    "shoulder_rear":      "🔙",
    # Triceps
    "triceps_long":       "💥",
    "triceps_lateral":    "🔹",
    # Back/Pull
    "lats_vertical":      "⬆️",
    "lats_horizontal":    "↩️",
    "upper_back":         "🎯",
    "traps_upper":        "🏔️",
    # Biceps
    "biceps_long":        "💪",
    "biceps_short":       "🔸",
    "brachialis":         "🦾",
    # Forearms
    "forearms":           "🤜",
    # Legs
    "quads_compound":     "🦵",
    "quads_isolation":    "⚡",
    "quads_vmo":          "🔷",
    "hamstrings_curl":    "🦶",
    "hamstrings_hinge":   "🏋️",
    "glutes_max":         "🍑",
    "glutes_med":         "🔵",
    "calves_gastro":      "🦿",
    "calves_soleus":      "🦶",
    "adductors":          "🔗",
    "hip_flexors":        "🔄",
    "lower_back":         "🏗️",
    # Core
    "core":               "🎯",
}


def _set_track(logged: int, total: int) -> str:
    return "🟦" * logged + "⬜" * (total - logged)


def _ex_status(ex: dict) -> str:
    logged = len(ex.get("sets_logged", []))
    total  = ex["sets"]
    if logged == 0:
        return f"📋 Log {ex['name']}"
    elif logged < total:
        return f"{ex['name']} {logged}/{total}"
    else:
        return f"✅ {ex['name']}"


def build_workout_message_and_keyboard(session: dict, exercises: list, session_id: str) -> tuple:
    from telegram import InlineKeyboardButton

    cfg       = INTENSITY[session["intensity"]]
    is_deload = session["is_deload"]
    dot       = "⚠️" if is_deload else DOTS.get(session["intensity"], "💪")
    day_label = session["day"].upper()
    intensity = "DELOAD" if is_deload else session["intensity"].upper()

    lines = [
        f'{dot} <b>{day_label} DAY</b>  ·  {intensity}  ·  Wk {session["week_number"]}',
        f'<i>Rest {cfg["rest"]} between sets</i>',
        "",
    ]

    for i, ex in enumerate(exercises, 1):
        rep_min, rep_max = ex["reps"]
        logged_count = len(ex.get("sets_logged", []))
        tracker  = _set_track(logged_count, ex["sets"])
        slot_ico = SLOT_EMOJI.get(ex.get("slot", ""), "•")

        lines.append(
            f'{i}. {slot_ico} <a href="{video_url(ex["video_id"])}"><b>{ex["name"]}</b></a>'
        )
        lines.append(
            f'    <code>{ex["sets"]} × {rep_min}–{rep_max} reps  @  {ex["weight_kg"]} kg</code>'
        )
        lines.append(f'    {tracker}')
        lines.append("")

    if is_deload:
        lines.append("<i>⚠️ Deload week — 60% weight. Form over everything.</i>")

    text = "\n".join(lines)

    keyboard_rows = []
    for i, ex in enumerate(exercises):
        logged = len(ex.get("sets_logged", []))
        total  = ex["sets"]
        done   = logged >= total

        log_btn = InlineKeyboardButton(
            _ex_status(ex),
            callback_data=f"log_ex:{session_id}:{i}:{logged + 1 if not done else total}"
        )
        swap_btn = InlineKeyboardButton(
            "🔄", callback_data=f"swap:{session_id}:{i}"
        )
        keyboard_rows.append([log_btn, swap_btn])

    keyboard_rows.append([
        InlineKeyboardButton("✅ Finish Session", callback_data=f"finish:{session_id}"),
        InlineKeyboardButton("⏭ Skip & Save",    callback_data=f"skip:{session_id}"),
    ])

    return text, keyboard_rows


def format_workout(session: dict, exercises: list, session_id: str = "") -> str:
    text, _ = build_workout_message_and_keyboard(session, exercises, session_id)
    return text


def format_set_prompt(exercise_name: str, set_num: int, total_sets: int, weight_kg: float) -> str:
    tracker = _set_track(set_num - 1, total_sets)
    return (
        f"<b>{exercise_name}</b>\n"
        f"<code>Set {set_num} / {total_sets}  ·  {weight_kg} kg</code>\n"
        f"{tracker}\n\n"
        f"Tap how many reps you completed 👇"
    )


def format_session_summary(exercises: list) -> str:
    decision_map = {
        "increase":      ("⬆️", "weight up next session"),
        "maintain":      ("➡️", "maintain"),
        "decrease":      ("⬇️", "weight down next session"),
        "single_deload": ("🔄", "single deload applied"),
        "no_data":       ("—",  "no data logged"),
    }

    lines = ["<b>✅ Session complete!</b>\n"]
    for ex in exercises:
        logged = ex.get("sets_logged", [])
        if not logged:
            continue
        avg         = sum(s["reps"] for s in logged) / len(logged)
        icon, label = decision_map.get(ex.get("progression_decision", ""), ("—", ""))
        next_w      = ex.get("next_weight_kg", ex["weight_kg"])
        lines.append(
            f'{icon} <b>{ex["name"]}</b>\n'
            f'    avg <code>{avg:.1f} reps</code>  ·  '
            f'<code>{ex["weight_kg"]} kg → {next_w} kg</code>  <i>({label})</i>\n'
        )
    return "\n".join(lines)


def format_progress(exercise_id: str, history_data: dict) -> str:
    name    = exercise_id.replace("_", " ").title()
    history = history_data.get("history", [])[-5:]
    current = history_data.get("current_weight_kg", 0)

    if not history:
        return f"No history yet for <b>{name}</b>.\nLog a session to start tracking."

    lines = [f"📊 <b>{name}</b>  ·  last {len(history)} sessions\n"]
    for entry in history:
        arrow = {"increase": "⬆️", "maintain": "➡️", "decrease": "⬇️"}.get(
            entry.get("decision", ""), "·"
        )
        lines.append(
            f'{arrow}  <code>{entry["date"]}</code>  '
            f'<code>{entry["weight_kg"]} kg</code>  '
            f'avg <code>{entry["avg_reps"]} reps</code>'
        )

    lines.append(f"\n<b>Current weight: {current} kg</b>")
    return "\n".join(lines)