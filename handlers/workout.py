import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import VALID_DAYS, INTENSITY
from database import (
    get_user, upsert_user, create_session,
    get_active_session, update_session_exercises,
    get_exercise_history
)
from core.templates import get_slots, get_category, is_lower_body
from core.rotation import pick_exercise
from core.progression import apply_deload
from core.formatter import format_workout


async def workout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args    = context.args  # e.g. ["push", "moderate"]

    # ── Load or create user ──────────────────────────────────────────────────
    user = await upsert_user(user_id)

    # ── Parse args ───────────────────────────────────────────────────────────
    day       = args[0].lower() if len(args) >= 1 else None
    intensity = args[1].lower() if len(args) >= 2 else user["intensity"]

    split = user["split"]

    # ── Validate ─────────────────────────────────────────────────────────────
    if not day or day not in VALID_DAYS[split]:
        valid = ", ".join(VALID_DAYS[split])
        await update.message.reply_text(
            f"❌ Invalid day for your split (*{split}*).\n"
            f"Valid options: `{valid}`\n\n"
            f"Usage: `/workout <day> [intensity]`",
            parse_mode="HTML"
        )
        return

    if intensity not in INTENSITY:
        await update.message.reply_text(
            "❌ Invalid intensity. Choose: `easy`, `moderate`, or `hardcore`.",
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

    # ── Build session ─────────────────────────────────────────────────────────
    is_deload   = bool(user["is_deload"])
    week_number = user["week_number"]
    cfg         = INTENSITY["easy"] if is_deload else INTENSITY[intensity]
    slots       = get_slots(split, day)

    exercises_data = []
    for slot in slots:
        ex       = pick_exercise(slot, user["last_used"], user["pinned"])
        history  = await get_exercise_history(user_id, ex["id"])
        weight   = history["current_weight_kg"]
        lower    = is_lower_body(slot)

        sets_count = cfg["sets"][1]  # use upper bound of range
        reps       = cfg["reps"]

        if is_deload:
            weight, sets_count, reps = apply_deload(weight, INTENSITY[intensity])

        exercises_data.append({
            "slot":          slot,
            "exercise_id":   ex["id"],
            "name":          ex["name"],
            "video_id":      ex["video_id"],
            "weight_kg":     weight,
            "sets":          sets_count,
            "reps":          reps,
            "sets_logged":   [],
            "swapped":       False,
            "progression_decision": None,
            "next_weight_kg": weight,
        })

    # ── Create session in DB ──────────────────────────────────────────────────
    session_id = str(uuid.uuid4())
    await create_session(session_id, user_id, split, day, intensity, week_number, is_deload)
    await update_session_exercises(session_id, exercises_data)

    # ── Update last_used ─────────────────────────────────────────────────────
    new_last_used = {**user["last_used"]}
    for ex in exercises_data:
        new_last_used[ex["slot"]] = ex["exercise_id"]
    await upsert_user(user_id, last_used=new_last_used, intensity=intensity)

    # ── Send workout message ──────────────────────────────────────────────────
    session = {
        "day": day,
        "intensity": intensity,
        "week_number": week_number,
        "is_deload": is_deload,
    }
    text = format_workout(session, exercises_data)

    # Build inline keyboard: one "Log" button per exercise
    keyboard_rows = []
    for i, ex in enumerate(exercises_data):
        keyboard_rows.append([
            InlineKeyboardButton(
                f"Log {ex['name']}",
                callback_data=f"log_ex:{session_id}:{i}:1"
            ),
            InlineKeyboardButton(
                "🔄 Swap",
                callback_data=f"swap:{session_id}:{i}"
            ),
        ])
    keyboard_rows.append([
        InlineKeyboardButton("✅ Finish Session", callback_data=f"finish:{session_id}"),
        InlineKeyboardButton("⏭ Skip & Save",    callback_data=f"skip:{session_id}"),
    ])

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
        disable_web_page_preview=True,
    )
