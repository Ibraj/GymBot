from telegram import Update
from telegram.ext import ContextTypes

from database import upsert_user, get_exercise_history
from core.formatter import format_progress
from config import VALID_DAYS, INTENSITY


async def split_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user    = await upsert_user(user_id)

    if not context.args:
        await update.message.reply_text(
            f"Your current split: <b>{user['split']}</b>\n\n"
            "To change:\n"
            "<code>/split ppl</code>         — Push / Pull / Legs (3 days)\n"
            "<code>/split pplul</code>        — Push / Pull / Legs / Upper / Lower (5 days)\n"
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


async def progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text(
            "Usage: <code>/progress &lt;exercise_id&gt;</code>\n"
            "Example: <code>/progress bench_bar</code>",
            parse_mode="HTML"
        )
        return

    exercise_id = context.args[0].lower()
    history     = await get_exercise_history(user_id, exercise_id)
    text        = format_progress(exercise_id, history)

    await update.message.reply_text(text, parse_mode="HTML")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user    = await upsert_user(user_id)

    deload_str = "⚠️ Yes — next session is a deload" if user["is_deload"] else "No"

    await update.message.reply_text(
        f"<b>GymBot Status</b>\n\n"
        f"Split:      <code>{user['split']}</code>\n"
        f"Intensity:  <code>{user['intensity']}</code>\n"
        f"Week:       <code>{user['week_number']} / 4</code>\n"
        f"Deload due: <code>{deload_str}</code>",
        parse_mode="HTML"
    )
