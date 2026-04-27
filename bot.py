import logging

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler
)

from config import BOT_TOKEN
from database import init_db
from handlers.workout import workout_command
from handlers.logging import (
    handle_log_exercise,
    handle_reps_logged,
    handle_swap,
    handle_finish,
    handle_skip,
    handle_abandon,
    handle_resume,
)
from handlers.settings import (
    split_command,
    intensity_command,
    progress_command,
    status_command,
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start_command(update: Update, _):
    await update.message.reply_text(
        "<b>Welcome to GymBot</b> 💪\n\n"
        "<b>Commands:</b>\n"
        "/workout &lt;day&gt; [intensity] — Start a session\n"
        "/split — View or change your split\n"
        "/intensity — View or change intensity\n"
        "/progress &lt;exercise_id&gt; — View exercise history\n"
        "/status — View your config and week state\n\n"
        "<i>Example: /workout push moderate</i>",
        parse_mode="HTML"
    )


async def post_init(app: Application):
    await init_db()
    logger.info("Database initialised.")


def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Commands
    app.add_handler(CommandHandler("start",     start_command))
    app.add_handler(CommandHandler("workout",   workout_command))
    app.add_handler(CommandHandler("split",     split_command))
    app.add_handler(CommandHandler("intensity", intensity_command))
    app.add_handler(CommandHandler("progress",  progress_command))
    app.add_handler(CommandHandler("status",    status_command))

    # Inline button callbacks — ordered most specific first
    app.add_handler(CallbackQueryHandler(handle_log_exercise, pattern=r"^log_ex:"))
    app.add_handler(CallbackQueryHandler(handle_reps_logged,  pattern=r"^reps:"))
    app.add_handler(CallbackQueryHandler(handle_swap,         pattern=r"^swap:"))
    app.add_handler(CallbackQueryHandler(handle_finish,       pattern=r"^finish:"))
    app.add_handler(CallbackQueryHandler(handle_skip,         pattern=r"^skip:"))
    app.add_handler(CallbackQueryHandler(handle_abandon,      pattern="^abandon_session$"))
    app.add_handler(CallbackQueryHandler(handle_resume,       pattern="^resume_session$"))

    logger.info("GymBot is running.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()