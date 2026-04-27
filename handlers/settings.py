from telegram import Update
from telegram.ext import ContextTypes

from database import upsert_user, get_exercise_history, update_exercise_history
from core.formatter import format_progress
from core.templates import get_exercise
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


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /today — suggest what to train based on split and last session.
    """
    user_id = update.effective_user.id
    user    = await upsert_user(user_id)

    split      = user["split"]
    valid_days = VALID_DAYS[split]
    last_used  = user.get("last_used", {})

    # Find the last day trained by checking which days have last_used entries
    # We track this by looking at which template day's slots appear in last_used
    from core.templates import get_slots
    import aiosqlite
    from config import DB_PATH

    # Get the last completed session day
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
        # No sessions yet — suggest the first day
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
        next_idx  = (idx + 1) % len(valid_days)
        suggested = valid_days[next_idx]
    else:
        suggested = valid_days[0]

    deload_note = "\n⚠️ <i>Next session is a deload week.</i>" if user["is_deload"] else ""

    await update.message.reply_text(
        f"Last session: <b>{last_day}</b> on <code>{last_date}</code>\n\n"
        f"Up next: <b>{suggested}</b>{deload_note}\n\n"
        f"<code>/workout {suggested} {user['intensity']}</code>",
        parse_mode="HTML"
    )


async def setweight_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /setweight <exercise_id> <kg>
    Manually set the working weight for an exercise.
    """
    user_id = update.effective_user.id

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: <code>/setweight &lt;exercise_id&gt; &lt;kg&gt;</code>\n"
            "Example: <code>/setweight bench_bar 80</code>",
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

    # Validate exercise exists
    ex = get_exercise(exercise_id)
    if not ex:
        await update.message.reply_text(
            f"❌ Exercise <code>{exercise_id}</code> not found.\n"
            "Check the ID — example: <code>bench_bar</code>, <code>squat_bar</code>, <code>rdl</code>",
            parse_mode="HTML"
        )
        return

    history = await get_exercise_history(user_id, exercise_id)
    await update_exercise_history(
        user_id,
        exercise_id,
        weight,
        history["consecutive_failures"],
        {
            "session_id": "manual",
            "date":       __import__("datetime").date.today().isoformat(),
            "weight_kg":  weight,
            "avg_reps":   0,
            "decision":   "manual_set",
        }
    )

    await update.message.reply_text(
        f"✅ <b>{ex['name']}</b> starting weight set to <code>{weight} kg</code>.",
        parse_mode="HTML"
    )