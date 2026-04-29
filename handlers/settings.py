import aiosqlite
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import (
    upsert_user, get_exercise_history, update_exercise_history,
    get_recent_sessions, get_last_session, add_session_note,
    get_active_session
)
from core.formatter import format_progress
from core.templates import get_exercise, CATEGORIES
from config import VALID_DAYS, INTENSITY, DB_PATH

# Main lifts to walk through in /setup
SETUP_LIFTS = [
    ("bench_bar",  "Barbell Bench Press"),
    ("squat_bar",  "Barbell Back Squat"),
    ("deadlift",   "Barbell Deadlift"),
    ("ohp_bar",    "Overhead Barbell Press"),
    ("row_bar",    "Barbell Row"),
    ("pulldown",   "Lat Pulldown"),
]


# ── /setup ────────────────────────────────────────────────────────────────────

async def setup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 1: pick split."""
    await upsert_user(update.effective_user.id)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("PPL (3 days)",           callback_data="setup:split:ppl")],
        [InlineKeyboardButton("PPLUL (5 days)",         callback_data="setup:split:pplul")],
        [InlineKeyboardButton("Upper / Lower (2 days)", callback_data="setup:split:upper_lower")],
        [InlineKeyboardButton("Full Body (1 day)",      callback_data="setup:split:full_body")],
    ])
    await update.message.reply_text(
        "<b>GymBot Setup</b> 🏋️\n\nStep 1 of 3 — Choose your split:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def handle_setup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles all setup: callbacks."""
    query = update.callback_query
    await query.answer()

    parts   = query.data.split(":")  # setup:step:value
    step    = parts[1]
    value   = parts[2] if len(parts) > 2 else None
    user_id = query.from_user.id

    if step == "split":
        await upsert_user(user_id, split=value, week_number=1, is_deload=0)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Easy (2–3 sets, 10–15 reps)",    callback_data="setup:intensity:easy")],
            [InlineKeyboardButton("Moderate (3–4 sets, 8–12 reps)", callback_data="setup:intensity:moderate")],
            [InlineKeyboardButton("Hardcore (4–5 sets, 4–10 reps)", callback_data="setup:intensity:hardcore")],
        ])
        await query.edit_message_text(
            f"✅ Split set to <b>{value}</b>\n\nStep 2 of 3 — Choose your default intensity:",
            parse_mode="HTML",
            reply_markup=keyboard
        )

    elif step == "intensity":
        await upsert_user(user_id, intensity=value)
        # Start weight entry for first lift
        lift_id, lift_name = SETUP_LIFTS[0]
        context.user_data["setup_lift_idx"] = 0
        await query.edit_message_text(
            f"✅ Intensity set to <b>{value}</b>\n\n"
            f"Step 3 of 3 — Set your working weights.\n\n"
            f"<b>{lift_name}</b>\n"
            f"Reply with your current working weight in kg (e.g. <code>80</code>)\n"
            f"Type <code>0</code> if you don't do this lift.",
            parse_mode="HTML"
        )
        context.user_data["awaiting_setup_weight"] = True

    elif step == "done":
        await upsert_user(user_id, setup_done=1)
        user = await upsert_user(user_id)
        first_day = VALID_DAYS[user["split"]][0]
        await query.edit_message_text(
            "✅ <b>Setup complete!</b>\n\n"
            f"Split: <code>{user['split']}</code>\n"
            f"Intensity: <code>{user['intensity']}</code>\n\n"
            f"Start your first session:\n"
            f"<code>/workout {first_day} {user['intensity']}</code>",
            parse_mode="HTML"
        )
        context.user_data.pop("awaiting_setup_weight", None)
        context.user_data.pop("setup_lift_idx", None)


async def handle_setup_weight_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text input during /setup weight entry."""
    if not context.user_data.get("awaiting_setup_weight"):
        return False  # not in setup flow

    user_id = update.effective_user.id
    text    = update.message.text.strip()

    try:
        weight = float(text)
    except ValueError:
        await update.message.reply_text(
            "Please enter a number. Example: <code>80</code>",
            parse_mode="HTML"
        )
        return True

    idx       = context.user_data.get("setup_lift_idx", 0)
    lift_id, lift_name = SETUP_LIFTS[idx]

    if weight > 0:
        history = await get_exercise_history(user_id, lift_id)
        await update_exercise_history(
            user_id, lift_id, weight,
            history["consecutive_failures"],
            {
                "session_id": "setup",
                "date": __import__("datetime").date.today().isoformat(),
                "weight_kg": weight,
                "avg_reps": 0,
                "decision": "manual_set",
            }
        )

    next_idx = idx + 1
    if next_idx < len(SETUP_LIFTS):
        context.user_data["setup_lift_idx"] = next_idx
        next_id, next_name = SETUP_LIFTS[next_idx]
        await update.message.reply_text(
            f"✅ <b>{lift_name}</b> → <code>{weight} kg</code>\n\n"
            f"<b>{next_name}</b>\n"
            f"Weight in kg? Type <code>0</code> to skip.",
            parse_mode="HTML"
        )
    else:
        # All lifts done
        context.user_data.pop("awaiting_setup_weight", None)
        context.user_data.pop("setup_lift_idx", None)
        await upsert_user(user_id, setup_done=1)
        user      = await upsert_user(user_id)
        first_day = VALID_DAYS[user["split"]][0]
        await update.message.reply_text(
            f"✅ <b>{lift_name}</b> → <code>{weight} kg</code>\n\n"
            "<b>Setup complete!</b> 🎉\n\n"
            f"Split: <code>{user['split']}</code>  ·  "
            f"Intensity: <code>{user['intensity']}</code>\n\n"
            f"Start your first session:\n"
            f"<code>/workout {first_day} {user['intensity']}</code>",
            parse_mode="HTML"
        )

    return True


# ── /exercises ────────────────────────────────────────────────────────────────

CATEGORY_FILTER_MAP = {
    "push":          ["chest_upper","chest_mid","chest_lower","shoulder_front","shoulder_side","shoulder_rear","triceps_long","triceps_lateral"],
    "pull":          ["lats_vertical","lats_horizontal","upper_back","traps_upper","biceps_long","biceps_short","brachialis","forearms"],
    "legs":          ["quads_compound","quads_isolation","quads_vmo","hamstrings_curl","hamstrings_hinge","glutes_max","glutes_med","calves_gastro","calves_soleus","adductors","hip_flexors"],
    "upper":         ["chest_upper","chest_mid","chest_lower","lats_vertical","lats_horizontal","shoulder_front","shoulder_side","shoulder_rear","triceps_long","triceps_lateral","biceps_long","biceps_short","brachialis","traps_upper","forearms"],
    "lower":         ["quads_compound","quads_isolation","quads_vmo","hamstrings_curl","hamstrings_hinge","glutes_max","glutes_med","calves_gastro","calves_soleus","adductors","hip_flexors"],
    "chest":         ["chest_upper","chest_mid","chest_lower"],
    "shoulders":     ["shoulder_front","shoulder_side","shoulder_rear"],
    "triceps":       ["triceps_long","triceps_lateral"],
    "back":          ["lats_vertical","lats_horizontal","upper_back","traps_upper"],
    "biceps":        ["biceps_long","biceps_short","brachialis"],
    "quads":         ["quads_compound","quads_isolation","quads_vmo"],
    "hamstrings":    ["hamstrings_curl","hamstrings_hinge"],
    "glutes":        ["glutes_max","glutes_med"],
    "calves":        ["calves_gastro","calves_soleus"],
    "core":          ["core"],
    "forearms":      ["forearms"],
    "traps":         ["traps_upper"],
}

async def exercises_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List exercise IDs. Optional filter: /exercises push, /exercises legs, etc."""
    filter_arg = context.args[0].lower() if context.args else None

    if filter_arg and filter_arg not in CATEGORY_FILTER_MAP and filter_arg not in CATEGORIES:
        valid = ", ".join(CATEGORY_FILTER_MAP.keys())
        await update.message.reply_text(
            f"❌ Unknown filter <code>{filter_arg}</code>.\n"
            f"Valid filters: <code>{valid}</code>\n"
            f"Or just /exercises to see all.",
            parse_mode="HTML"
        )
        return

    if filter_arg in CATEGORY_FILTER_MAP:
        slots_to_show = {k: CATEGORIES[k] for k in CATEGORY_FILTER_MAP[filter_arg] if k in CATEGORIES}
        title = f"<b>{filter_arg.title()} Day Exercises</b>\n"
    elif filter_arg in CATEGORIES:
        slots_to_show = {filter_arg: CATEGORIES[filter_arg]}
        title = f"<b>{CATEGORIES[filter_arg]['label']} Exercises</b>\n"
    else:
        slots_to_show = CATEGORIES
        title = "<b>Exercise IDs by Category</b>\n"

    lines = [title]
    for slot, cat in slots_to_show.items():
        lines.append(f"\n<b>{cat['label']}</b>")
        for ex in cat["exercises"]:
            lines.append(f"  <code>{ex['id']}</code> — {ex['name']}")

    text = "\n".join(lines)
    if len(text) <= 4096:
        await update.message.reply_text(text, parse_mode="HTML")
    else:
        mid = len(lines) // 2
        await update.message.reply_text("\n".join(lines[:mid]), parse_mode="HTML")
        await update.message.reply_text("\n".join(lines[mid:]), parse_mode="HTML")


# ── /history ──────────────────────────────────────────────────────────────────

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show last 7 completed sessions."""
    user_id  = update.effective_user.id
    sessions = await get_recent_sessions(user_id, limit=7)

    if not sessions:
        await update.message.reply_text(
            "No sessions logged yet. Start one with /workout",
            parse_mode="HTML"
        )
        return

    lines = ["<b>Last sessions</b>\n"]
    for s in sessions:
        deload = " ⚠️" if s["is_deload"] else ""
        note   = f"\n   <i>{s['note']}</i>" if s.get("note") else ""
        lines.append(
            f"<code>{s['date']}</code>  <b>{s['day'].title()}</b>  "
            f"<i>{s['split']} · {s['intensity']}</i>{deload}{note}"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


# ── /note ─────────────────────────────────────────────────────────────────────

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /note <text> — attach a note to active or last session.
    """
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text(
            "Usage: <code>/note &lt;text&gt;</code>\n"
            "Example: <code>/note felt strong today, new PR on bench</code>",
            parse_mode="HTML"
        )
        return

    note_text = " ".join(context.args)

    # Try active session first
    session = await get_active_session(user_id)
    if session:
        await add_session_note(session["session_id"], note_text)
        await update.message.reply_text(
            f"📝 Note added to current session:\n<i>{note_text}</i>",
            parse_mode="HTML"
        )
        return

    # Fall back to last completed session
    last = await get_last_session(user_id)
    if not last:
        await update.message.reply_text("No sessions found to attach a note to.")
        return

    await add_session_note(last["session_id"], note_text)
    await update.message.reply_text(
        f"📝 Note added to last session ({last['date']} — {last['day']}):\n<i>{note_text}</i>",
        parse_mode="HTML"
    )


# ── /split ────────────────────────────────────────────────────────────────────

async def split_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user    = await upsert_user(user_id)

    if not context.args:
        await update.message.reply_text(
            f"Your current split: <b>{user['split']}</b>\n\n"
            "To change:\n"
            "<code>/split ppl</code>         — Push / Pull / Legs (3 days)\n"
            "<code>/split pplul</code>        — PPL + Upper / Lower (5 days)\n"
            "<code>/split upper_lower</code>  — Upper / Lower (2 days)\n"
            "<code>/split full_body</code>    — Full Body (1 day)",
            parse_mode="HTML"
        )
        return

    new_split = context.args[0].lower()
    if new_split not in VALID_DAYS:
        await update.message.reply_text(
            "❌ Invalid split. Choose: <code>ppl</code>, <code>pplul</code>, "
            "<code>upper_lower</code>, or <code>full_body</code>.",
            parse_mode="HTML"
        )
        return

    await upsert_user(user_id, split=new_split, week_number=1, is_deload=0)
    await update.message.reply_text(
        f"✅ Split updated to <b>{new_split}</b>. Week counter reset to 1.",
        parse_mode="HTML"
    )


# ── /intensity ────────────────────────────────────────────────────────────────

async def intensity_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user    = await upsert_user(user_id)

    if not context.args:
        await update.message.reply_text(
            f"Default intensity: <b>{user['intensity']}</b>\n\n"
            "To change:\n"
            "<code>/intensity easy</code>      — 2–3 sets, 10–15 reps\n"
            "<code>/intensity moderate</code>  — 3–4 sets, 8–12 reps\n"
            "<code>/intensity hardcore</code>  — 4–5 sets, 4–10 reps",
            parse_mode="HTML"
        )
        return

    new_intensity = context.args[0].lower()
    if new_intensity not in INTENSITY:
        await update.message.reply_text(
            "❌ Invalid intensity. Choose: <code>easy</code>, <code>moderate</code>, or <code>hardcore</code>.",
            parse_mode="HTML"
        )
        return

    await upsert_user(user_id, intensity=new_intensity)
    await update.message.reply_text(
        f"✅ Default intensity set to <b>{new_intensity}</b>.",
        parse_mode="HTML"
    )


# ── /progress ─────────────────────────────────────────────────────────────────

async def progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text(
            "Usage: <code>/progress &lt;exercise_id&gt;</code>\n"
            "Example: <code>/progress bench_bar</code>\n\n"
            "See all IDs: /exercises",
            parse_mode="HTML"
        )
        return

    exercise_id = context.args[0].lower()
    history     = await get_exercise_history(user_id, exercise_id)
    text        = format_progress(exercise_id, history)
    await update.message.reply_text(text, parse_mode="HTML")


# ── /status ───────────────────────────────────────────────────────────────────

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user    = await upsert_user(user_id)
    deload  = "⚠️ Yes — next session is a deload" if user["is_deload"] else "No"

    await update.message.reply_text(
        f"<b>GymBot Status</b>\n\n"
        f"Split:      <code>{user['split']}</code>\n"
        f"Intensity:  <code>{user['intensity']}</code>\n"
        f"Week:       <code>{user['week_number']} / 4</code>\n"
        f"Deload due: <code>{deload}</code>",
        parse_mode="HTML"
    )


# ── /today ────────────────────────────────────────────────────────────────────

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id    = update.effective_user.id
    user       = await upsert_user(user_id)
    split      = user["split"]
    valid_days = VALID_DAYS[split]

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT day, date FROM sessions
               WHERE user_id = ? AND split = ? AND completed = 1
               ORDER BY date DESC, session_id DESC LIMIT 1""",
            (user_id, split)
        ) as cur:
            row = await cur.fetchone()

    if not row:
        suggested = valid_days[0]
        await update.message.reply_text(
            f"No sessions logged yet for <b>{split}</b>.\n\n"
            f"Start with: <code>/workout {suggested} {user['intensity']}</code>",
            parse_mode="HTML"
        )
        return

    last_day  = row["day"]
    last_date = row["date"]

    if last_day in valid_days:
        idx       = valid_days.index(last_day)
        suggested = valid_days[(idx + 1) % len(valid_days)]
    else:
        suggested = valid_days[0]

    deload_note = "\n⚠️ <i>Next session is a deload week.</i>" if user["is_deload"] else ""

    await update.message.reply_text(
        f"Last session: <b>{last_day}</b> on <code>{last_date}</code>\n\n"
        f"Up next: <b>{suggested}</b>{deload_note}\n\n"
        f"<code>/workout {suggested} {user['intensity']}</code>",
        parse_mode="HTML"
    )


# ── /setweight ────────────────────────────────────────────────────────────────

async def setweight_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: <code>/setweight &lt;exercise_id&gt; &lt;kg&gt;</code>\n"
            "Example: <code>/setweight bench_bar 80</code>\n\n"
            "See all IDs: /exercises",
            parse_mode="HTML"
        )
        return

    exercise_id = context.args[0].lower()
    try:
        weight = float(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "❌ Weight must be a number. Example: <code>/setweight bench_bar 80</code>",
            parse_mode="HTML"
        )
        return

    if weight < 0:
        await update.message.reply_text("❌ Weight can't be negative.", parse_mode="HTML")
        return

    ex = get_exercise(exercise_id)
    if not ex:
        await update.message.reply_text(
            f"❌ <code>{exercise_id}</code> not found. See all IDs: /exercises",
            parse_mode="HTML"
        )
        return

    history = await get_exercise_history(user_id, exercise_id)
    await update_exercise_history(
        user_id, exercise_id, weight,
        history["consecutive_failures"],
        {
            "session_id": "manual",
            "date": __import__("datetime").date.today().isoformat(),
            "weight_kg": weight,
            "avg_reps": 0,
            "decision": "manual_set",
        }
    )

    await update.message.reply_text(
        f"✅ <b>{ex['name']}</b> set to <code>{weight} kg</code>.",
        parse_mode="HTML"
    )