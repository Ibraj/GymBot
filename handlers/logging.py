from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import (
    get_active_session, update_session_exercises,
    complete_session, upsert_user,
    update_exercise_history, get_exercise_history,
    get_workout_message
)
from core.rotation import get_alternative
from core.progression import compute_progression, advance_week
from core.formatter import (
    format_set_prompt, format_session_summary,
    build_workout_message_and_keyboard
)
from config import VALID_DAYS, INTENSITY


# ── Helpers ───────────────────────────────────────────────────────────────────

def _back_button(session_id: str) -> InlineKeyboardButton:
    return InlineKeyboardButton("⬅️ Back to workout", callback_data=f"back_to_workout:{session_id}")


def _rep_keyboard(session_id: str, ex_idx: int, set_num: int) -> InlineKeyboardMarkup:
    rows, row = [], []
    for r in range(0, 21):
        row.append(InlineKeyboardButton(
            str(r),
            callback_data=f"reps:{session_id}:{ex_idx}:{set_num}:{r}"
        ))
        if len(row) == 7:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    # Add back button as last row
    rows.append([_back_button(session_id)])
    return InlineKeyboardMarkup(rows)


async def _cancel_rest_timer(context, user_id: int):
    if not context.job_queue:
        return
    for job in context.job_queue.get_jobs_by_name(f"rest_{user_id}"):
        job.schedule_removal()


async def _update_workout_message(context, user_id: int, session: dict, exercises: list):
    """Edit the original workout message with updated trackers and button states."""
    message_id, chat_id = await get_workout_message(user_id)
    if not message_id or not chat_id:
        return

    session_ctx = {
        "day":         session["day"],
        "intensity":   session["intensity"],
        "week_number": session["week_number"],
        "is_deload":   session["is_deload"],
    }
    text, keyboard_rows = build_workout_message_and_keyboard(
        session_ctx, exercises, session["session_id"]
    )

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard_rows),
            disable_web_page_preview=True,
        )
    except Exception:
        pass


async def _rest_over_callback(context):
    job  = context.job
    data = job.data
    await context.bot.send_message(
        chat_id=job.chat_id,
        text=(
            f"⏱ <b>Rest over!</b>\n"
            f"Time for set {data['next_set']} of <b>{data['exercise_name']}</b> 💪"
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Got it", callback_data="dismiss_rest")
        ]])
    )


# ── Back to workout ───────────────────────────────────────────────────────────

async def handle_back_to_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: back_to_workout:{session_id} — resend/show the workout message."""
    query = update.callback_query
    await query.answer()

    _, session_id = query.data.split(":", 1)
    user_id = query.from_user.id

    session = await get_active_session(user_id)
    if not session or session["session_id"] != session_id:
        await query.edit_message_text("Session not found.")
        return

    session_ctx = {
        "day":         session["day"],
        "intensity":   session["intensity"],
        "week_number": session["week_number"],
        "is_deload":   session["is_deload"],
    }
    text, keyboard_rows = build_workout_message_and_keyboard(
        session_ctx, session["exercises"], session_id
    )

    # Try to edit current message first, then send new if it fails
    try:
        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard_rows),
            disable_web_page_preview=True,
        )
        # Update stored message id
        from database import store_workout_message
        await store_workout_message(user_id, query.message.message_id, query.message.chat_id)
    except Exception:
        msg = await query.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard_rows),
            disable_web_page_preview=True,
        )
        from database import store_workout_message
        await store_workout_message(user_id, msg.message_id, query.message.chat_id)


# ── Set logging ───────────────────────────────────────────────────────────────

async def handle_log_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: log_ex:{session_id}:{exercise_index}:{set_number}"""
    query = update.callback_query
    await query.answer()

    _, session_id, ex_idx, set_num = query.data.split(":")
    ex_idx  = int(ex_idx)
    set_num = int(set_num)

    session = await get_active_session(query.from_user.id)
    if not session or session["session_id"] != session_id:
        await query.edit_message_text("Session not found or already completed.")
        return

    ex = session["exercises"][ex_idx]
    await query.edit_message_text(
        format_set_prompt(ex["name"], set_num, ex["sets"], ex["weight_kg"]),
        parse_mode="HTML",
        reply_markup=_rep_keyboard(session_id, ex_idx, set_num),
    )


async def handle_reps_logged(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: reps:{session_id}:{exercise_index}:{set_number}:{reps}"""
    query = update.callback_query
    await query.answer()

    _, session_id, ex_idx, set_num, reps = query.data.split(":")
    ex_idx  = int(ex_idx)
    set_num = int(set_num)
    reps    = int(reps)

    user_id   = query.from_user.id
    session   = await get_active_session(user_id)
    if not session:
        await query.edit_message_text("Session expired.")
        return

    exercises = session["exercises"]
    ex        = exercises[ex_idx]

    existing = next((s for s in ex["sets_logged"] if s["set"] == set_num), None)
    if existing:
        existing["reps"] = reps
    else:
        ex["sets_logged"].append({"set": set_num, "weight": ex["weight_kg"], "reps": reps})

    exercises[ex_idx] = ex
    await update_session_exercises(session_id, exercises)

    next_set = set_num + 1

    if next_set <= ex["sets"]:
        rest_seconds = INTENSITY[session["intensity"]]["rest_seconds"]

        await query.edit_message_text(
            f"✅ Set {set_num} — <b>{reps} reps</b>\n\n"
            f"⏱ Rest <b>{rest_seconds}s</b>, then set {next_set}. I'll ping you.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    f"Log Set {next_set} now",
                    callback_data=f"log_ex:{session_id}:{ex_idx}:{next_set}"
                ),
                InlineKeyboardButton(
                    f"✏️ Edit Set {set_num}",
                    callback_data=f"edit_set:{session_id}:{ex_idx}:{set_num}"
                ),
            ],[
                _back_button(session_id)
            ]])
        )

        await _cancel_rest_timer(context, user_id)
        if context.job_queue:
            context.job_queue.run_once(
                _rest_over_callback,
                when=rest_seconds,
                chat_id=user_id,
                data={"exercise_name": ex["name"], "next_set": next_set},
                name=f"rest_{user_id}",
            )

    else:
        total_reps = sum(s["reps"] for s in ex["sets_logged"])
        await _cancel_rest_timer(context, user_id)

        edit_buttons = [
            InlineKeyboardButton(
                f"✏️ Set {s['set']} ({s['reps']})",
                callback_data=f"edit_set:{session_id}:{ex_idx}:{s['set']}"
            )
            for s in ex["sets_logged"]
        ]
        edit_rows = [edit_buttons[i:i+2] for i in range(0, len(edit_buttons), 2)]
        edit_rows.append([_back_button(session_id)])

        await query.edit_message_text(
            f"✅ <b>{ex['name']}</b> done — "
            f"{len(ex['sets_logged'])} sets, {total_reps} total reps.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(edit_rows)
        )

        await _update_workout_message(context, user_id, session, exercises)


async def handle_edit_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: edit_set:{session_id}:{ex_idx}:{set_num}"""
    query = update.callback_query
    await query.answer()

    _, session_id, ex_idx, set_num = query.data.split(":")
    ex_idx  = int(ex_idx)
    set_num = int(set_num)

    session = await get_active_session(query.from_user.id)
    if not session:
        await query.edit_message_text("Session expired.")
        return

    ex = session["exercises"][ex_idx]
    await query.edit_message_text(
        f"✏️ <b>Edit Set {set_num} — {ex['name']}</b>\n"
        f"<code>{ex['weight_kg']} kg</code>\n\n"
        f"Select the correct rep count:",
        parse_mode="HTML",
        reply_markup=_rep_keyboard(session_id, ex_idx, set_num),
    )


async def handle_dismiss_rest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: dismiss_rest"""
    query = update.callback_query
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        await query.edit_message_text("✅")


# ── Swap ──────────────────────────────────────────────────────────────────────

async def handle_swap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: swap:{session_id}:{exercise_index}"""
    query = update.callback_query
    await query.answer()

    _, session_id, ex_idx = query.data.split(":")
    ex_idx  = int(ex_idx)
    user_id = query.from_user.id

    session   = await get_active_session(user_id)
    exercises = session["exercises"]
    ex        = exercises[ex_idx]

    user = await upsert_user(user_id)
    alt  = get_alternative(ex["slot"], ex["exercise_id"], user["pinned"], session["intensity"])

    if not alt:
        await query.answer("No alternative available for this slot.", show_alert=True)
        return

    exercises[ex_idx].update({
        "exercise_id": alt["id"],
        "name":        alt["name"],
        "video_id":    alt["video_id"],
        "swapped":     True,
        "sets_logged": [],
    })

    await update_session_exercises(session_id, exercises)
    await _update_workout_message(context, user_id, session, exercises)
    await query.answer(f"Swapped to {alt['name']}", show_alert=False)

    # Edit the button-press confirmation inline, with back button
    await query.edit_message_text(
        f"🔄 Swapped to <b>{alt['name']}</b>.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[_back_button(session_id)]])
    )


# ── Finish / Skip / Abandon / Resume ─────────────────────────────────────────

async def handle_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, session_id = query.data.split(":", 1)
    user_id = query.from_user.id

    session = await get_active_session(user_id)
    if not session:
        await query.edit_message_text("No active session found.")
        return

    exercises = session["exercises"]
    user      = await upsert_user(user_id)

    for ex in exercises:
        history = await get_exercise_history(user_id, ex["exercise_id"])
        result  = compute_progression(
            ex["sets_logged"], session["intensity"],
            ex["slot"], history["current_weight_kg"],
            history["consecutive_failures"],
        )
        ex["progression_decision"] = result["decision"]
        ex["next_weight_kg"]       = result["next_weight_kg"]
        ex["avg_reps"]             = result["avg_reps"]

        await update_exercise_history(
            user_id, ex["exercise_id"],
            result["next_weight_kg"], result["consecutive_failures"],
            {
                "session_id": session_id,
                "date":       session["date"],
                "weight_kg":  history["current_weight_kg"],
                "avg_reps":   result["avg_reps"],
                "decision":   result["decision"],
            }
        )

    await update_session_exercises(session_id, exercises)
    await complete_session(session_id, user_id)

    split      = session["split"]
    valid_days = VALID_DAYS[split]
    if session["day"] == valid_days[-1]:
        await upsert_user(user_id, **advance_week(user, split))

    await _cancel_rest_timer(context, user_id)
    await query.edit_message_text(format_session_summary(exercises), parse_mode="HTML")


async def handle_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, session_id = query.data.split(":", 1)
    user_id = query.from_user.id

    await complete_session(session_id, user_id)
    await _cancel_rest_timer(context, user_id)
    await query.edit_message_text("Session saved as partial. No weight changes applied.")


async def handle_abandon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: abandon_session — clear session then auto-start pending workout."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    session = await get_active_session(user_id)
    if session:
        await complete_session(session["session_id"], user_id)

    await _cancel_rest_timer(context, user_id)

    # Auto-start pending session if params were stored
    pending_day       = context.user_data.pop("pending_day", None)
    pending_intensity = context.user_data.pop("pending_intensity", None)

    if pending_day and pending_intensity:
        await query.edit_message_text(
            f"Starting <b>{pending_day}</b> — <b>{pending_intensity}</b>...",
            parse_mode="HTML"
        )
        from handlers.workout import start_session
        await start_session(user_id, pending_day, pending_intensity, query.message, context)
    else:
        await query.edit_message_text(
            "Session abandoned. Start a new one with /workout &lt;day&gt;",
            parse_mode="HTML"
        )


async def handle_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    session = await get_active_session(user_id)
    if not session:
        await query.edit_message_text(
            "No active session found. Start a new one with /workout &lt;day&gt;",
            parse_mode="HTML"
        )
        return

    session_ctx = {
        "day":         session["day"],
        "intensity":   session["intensity"],
        "week_number": session["week_number"],
        "is_deload":   session["is_deload"],
    }
    text, keyboard_rows = build_workout_message_and_keyboard(
        session_ctx, session["exercises"], session["session_id"]
    )

    msg = await query.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
        disable_web_page_preview=True,
    )

    from database import store_workout_message
    await store_workout_message(user_id, msg.message_id, query.message.chat_id)
    await query.edit_message_text("Session resumed 👆")