import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import VALID_DAYS, INTENSITY
from database import (
    upsert_user, create_session,
    get_active_session, update_session_exercises,
    get_exercise_history, store_workout_message
)
from core.templates import get_slots, is_lower_body
from core.rotation import pick_exercise
from core.progression import apply_deload
from core.formatter import build_workout_message_and_keyboard


async def workout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args    = context.args

    user  = await upsert_user(user_id)
    day   = args[0].lower() if len(args) >= 1 else None
    intensity = args[1].lower() if len(args) >= 2 else user["intensity"]
    split = user["split"]

    # ── Validate ─────────────────────────────────────────────────────────────
    if not day or day not in VALID_DAYS[split]:
        valid = ", ".join(VALID_DAYS[split])
        await update.message.reply_text(
            f"❌ Invalid day for your split (<b>{split}</b>).\n"
            f"Valid options: <code>{valid}</code>\n\n"
            f"Usage: <code>/workout &lt;day&gt; [intensity]</code>",
            parse_mode="HTML"
        )
        return

    if intensity not in INTENSITY:
        await update.message.reply_text(
            "❌ Invalid intensity. Choose: <code>easy</code>, <code>moderate</code>, or <code>hardcore</code>.",
            parse_mode="HTML"
        )
        return

    # ── Check for existing active session ────────────────────────────────────
    existing = await get_active_session(user_id)
    if existing:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("Abandon & start new", callback_data="abandon_session"),
            InlineKeyboardButton("Resume current",      callback_data="resume_session"),
        ]])
        await update.message.reply_text(
            "⚠️ You have an unfinished session. What do you want to do?",
            reply_markup=keyboard
        )
        return

    # ── Build exercises ───────────────────────────────────────────────────────
    is_deload   = bool(user["is_deload"])
    week_number = user["week_number"]
    cfg         = INTENSITY["easy"] if is_deload else INTENSITY[intensity]
    slots       = get_slots(split, day)

    exercises_data = []
    for slot in slots:
        ex      = pick_exercise(slot, user["last_used"], user["pinned"], intensity)
        history = await get_exercise_history(user_id, ex["id"])
        weight  = history["current_weight_kg"]

        sets_count = cfg["sets"][1]
        reps       = cfg["reps"]

        if is_deload:
            weight, sets_count, reps = apply_deload(weight, INTENSITY[intensity])

        exercises_data.append({
            "slot":                 slot,
            "exercise_id":          ex["id"],
            "name":                 ex["name"],
            "video_id":             ex["video_id"],
            "weight_kg":            weight,
            "sets":                 sets_count,
            "reps":                 reps,
            "sets_logged":          [],
            "swapped":              False,
            "progression_decision": None,
            "next_weight_kg":       weight,
        })

    # ── Create session ────────────────────────────────────────────────────────
    session_id = str(uuid.uuid4())
    await create_session(session_id, user_id, split, day, intensity, week_number, is_deload)
    await update_session_exercises(session_id, exercises_data)

    new_last_used = {**user["last_used"]}
    for ex in exercises_data:
        new_last_used[ex["slot"]] = ex["exercise_id"]
    await upsert_user(user_id, last_used=new_last_used, intensity=intensity)

    # ── Send workout message ──────────────────────────────────────────────────
    session_ctx = {
        "day": day, "intensity": intensity,
        "week_number": week_number, "is_deload": is_deload,
    }
    text, keyboard_rows = build_workout_message_and_keyboard(
        session_ctx, exercises_data, session_id
    )

    msg = await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
        disable_web_page_preview=True,
    )

    # Store message ID so we can edit it live
    await store_workout_message(user_id, msg.message_id, update.effective_chat.id)