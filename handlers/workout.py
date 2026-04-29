import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import VALID_DAYS, INTENSITY, EXTRA_SLOTS, DAY_WARMUP
from database import (
    upsert_user, create_session,
    get_active_session, update_session_exercises,
    get_exercise_history, store_workout_message,
    complete_session
)
from core.templates import get_slots
from core.rotation import build_session, get_alternative
from core.progression import apply_deload
from core.formatter import build_workout_message_and_keyboard


async def start_session(user_id: int, day: str, intensity: str,
                        reply_message, context):
    """Shared session builder used by workout_command and handle_abandon."""
    user        = await upsert_user(user_id)
    split       = user["split"]
    is_deload   = bool(user["is_deload"])
    week_number = user["week_number"]
    cfg         = INTENSITY["easy"] if is_deload else INTENSITY[intensity]

    # Base slots + intensity extras
    slots  = list(get_slots(split, day))
    extras = EXTRA_SLOTS.get(split, {}).get(day, {}).get(intensity, [])
    slots  = slots + extras

    # ── Conditional lower back ────────────────────────────────────────────────
    # Add lower_back slot only when no primary hinge is in the session slots
    hinge_slots = {"hamstrings_hinge", "quads_compound"}
    if not any(s in hinge_slots for s in slots):
        slots.append("lower_back")

    # ── Build exercises via smart selector ────────────────────────────────────
    selected = build_session(
        slots=slots,
        last_used=user["last_used"],
        pinned=user["pinned"],
        intensity=intensity if not is_deload else "easy",
        split=split,
        day=day,
    )

    exercises_data = []
    for ex in selected:
        slot    = ex["slot"]
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

    session_id = str(uuid.uuid4())
    await create_session(session_id, user_id, split, day, intensity, week_number, is_deload)
    await update_session_exercises(session_id, exercises_data)

    new_last_used = {**user["last_used"]}
    for ex in exercises_data:
        new_last_used[ex["slot"]] = ex["exercise_id"]
    await upsert_user(user_id, last_used=new_last_used, intensity=intensity)

    # ── Build message ─────────────────────────────────────────────────────────
    session_ctx = {
        "day": day, "intensity": intensity,
        "week_number": week_number, "is_deload": is_deload,
    }

    # Warmup note
    warmup_items = DAY_WARMUP.get(day, [])
    warmup_text  = ""
    if warmup_items:
        warmup_text = (
            "\n🔥 <b>Warm-up first:</b>\n"
            + "\n".join(f"  · {w}" for w in warmup_items)
            + "\n"
        )

    text, keyboard_rows = build_workout_message_and_keyboard(
        session_ctx, exercises_data, session_id
    )
    full_text = warmup_text + "\n" + text if warmup_text else text

    msg = await reply_message.reply_text(
        full_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
        disable_web_page_preview=True,
    )
    await store_workout_message(user_id, msg.message_id, reply_message.chat_id)


async def workout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id   = update.effective_user.id
    args      = context.args
    user      = await upsert_user(user_id)
    day       = args[0].lower() if len(args) >= 1 else None
    intensity = args[1].lower() if len(args) >= 2 else user["intensity"]
    split     = user["split"]

    if not day or day not in VALID_DAYS[split]:
        valid = ", ".join(VALID_DAYS[split])
        await update.message.reply_text(
            f"❌ Invalid day for your split (<b>{split}</b>).\n"
            f"Valid: <code>{valid}</code>\n\n"
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

    existing = await get_active_session(user_id)
    if existing:
        context.user_data["pending_day"]      = day
        context.user_data["pending_intensity"] = intensity
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("Abandon & start new", callback_data="abandon_session"),
            InlineKeyboardButton("Resume current",      callback_data="resume_session"),
        ]])
        await update.message.reply_text(
            "⚠️ You have an unfinished session. What do you want to do?",
            reply_markup=keyboard
        )
        return

    await start_session(user_id, day, intensity, update.message, context)