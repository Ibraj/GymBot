from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import (
    get_active_session, update_session_exercises,
    complete_session, upsert_user,
    update_exercise_history, get_exercise_history
)
from core.rotation import get_alternative
from core.progression import compute_progression, advance_week
from core.formatter import format_set_prompt, format_session_summary
from config import VALID_DAYS


# ── Set logging flow ──────────────────────────────────────────────────────────

async def handle_log_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Callback: log_ex:{session_id}:{exercise_index}:{set_number}
    Prompts user for rep count for a specific set.
    """
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

    # Build rep choice keyboard: 0–20 in rows of 7
    rep_buttons = []
    row = []
    for r in range(0, 21):
        row.append(InlineKeyboardButton(
            str(r),
            callback_data=f"reps:{session_id}:{ex_idx}:{set_num}:{r}"
        ))
        if len(row) == 7:
            rep_buttons.append(row)
            row = []
    if row:
        rep_buttons.append(row)

    await query.edit_message_text(
        format_set_prompt(ex["name"], set_num, ex["sets"], ex["weight_kg"]),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rep_buttons),
    )


async def handle_reps_logged(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Callback: reps:{session_id}:{exercise_index}:{set_number}:{reps}
    Records the reps, then prompts next set or returns to workout menu.
    """
    query = update.callback_query
    await query.answer()

    _, session_id, ex_idx, set_num, reps = query.data.split(":")
    ex_idx  = int(ex_idx)
    set_num = int(set_num)
    reps    = int(reps)

    user_id = query.from_user.id
    session = await get_active_session(user_id)
    if not session:
        await query.edit_message_text("Session expired.")
        return

    exercises = session["exercises"]
    ex        = exercises[ex_idx]

    ex["sets_logged"].append({"set": set_num, "weight": ex["weight_kg"], "reps": reps})
    exercises[ex_idx] = ex
    await update_session_exercises(session_id, exercises)

    next_set = set_num + 1
    if next_set <= ex["sets"]:
        # Prompt next set
        rep_buttons = []
        row = []
        for r in range(0, 21):
            row.append(InlineKeyboardButton(
                str(r),
                callback_data=f"reps:{session_id}:{ex_idx}:{next_set}:{r}"
            ))
            if len(row) == 7:
                rep_buttons.append(row)
                row = []
        if row:
            rep_buttons.append(row)

        await query.edit_message_text(
            format_set_prompt(ex["name"], next_set, ex["sets"], ex["weight_kg"]),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(rep_buttons),
        )
    else:
        # All sets done — confirm and return to menu
        total_reps = sum(s["reps"] for s in ex["sets_logged"])
        await query.edit_message_text(
            f"✅ *{ex['name']}* logged — {len(ex['sets_logged'])} sets, {total_reps} total reps.\n\n"
            f"Go back to your workout and log the next exercise.",
            parse_mode="HTML",
        )


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
    alt  = get_alternative(ex["slot"], ex["exercise_id"], user["pinned"])

    if not alt:
        await query.answer("No alternative available for this slot.", show_alert=True)
        return

    exercises[ex_idx]["exercise_id"] = alt["id"]
    exercises[ex_idx]["name"]        = alt["name"]
    exercises[ex_idx]["video_id"]    = alt["video_id"]
    exercises[ex_idx]["swapped"]     = True
    exercises[ex_idx]["sets_logged"] = []

    await update_session_exercises(session_id, exercises)
    await query.answer(f"Swapped to {alt['name']}", show_alert=False)
    await query.edit_message_text(
        f"🔄 Swapped to *{alt['name']}* for this session.",
        parse_mode="HTML"
    )


# ── Finish / Skip ─────────────────────────────────────────────────────────────

async def handle_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: finish:{session_id} — process progression and complete session."""
    query = update.callback_query
    await query.answer()

    _, session_id = query.data.split(":", 1)
    user_id = query.from_user.id

    session   = await get_active_session(user_id)
    if not session:
        await query.edit_message_text("No active session found.")
        return

    exercises = session["exercises"]
    user      = await upsert_user(user_id)

    for ex in exercises:
        history = await get_exercise_history(user_id, ex["exercise_id"])
        result  = compute_progression(
            ex["sets_logged"],
            session["intensity"],
            ex["slot"],
            history["current_weight_kg"],
            history["consecutive_failures"],
        )

        ex["progression_decision"] = result["decision"]
        ex["next_weight_kg"]       = result["next_weight_kg"]
        ex["avg_reps"]             = result["avg_reps"]

        await update_exercise_history(
            user_id,
            ex["exercise_id"],
            result["next_weight_kg"],
            result["consecutive_failures"],
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

    # Advance week counter if last day of cycle
    split      = session["split"]
    valid_days = VALID_DAYS[split]
    if session["day"] == valid_days[-1]:
        week_update = advance_week(user, split)
        await upsert_user(user_id, **week_update)

    summary = format_session_summary(exercises)
    await query.edit_message_text(summary, parse_mode="HTML")


async def handle_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: skip:{session_id} — save partial session without progression."""
    query = update.callback_query
    await query.answer()

    _, session_id = query.data.split(":", 1)
    user_id = query.from_user.id

    await complete_session(session_id, user_id)
    await query.edit_message_text("Session saved as partial. No weight changes applied.")


async def handle_abandon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: abandon_session"""
    query = update.callback_query
    await query.answer()

    session = await get_active_session(query.from_user.id)
    if session:
        await complete_session(session["session_id"], query.from_user.id)

    await query.edit_message_text(
        "Session abandoned. Start a new one with `/workout <day>`.",
        parse_mode="HTML"
    )


async def handle_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: resume_session"""
    query = update.callback_query
    await query.answer("Resuming your session — scroll up to find your workout.", show_alert=True)
