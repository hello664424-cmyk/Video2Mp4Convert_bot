import os
import logging
import asyncio
import tempfile
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Retrieve Telegram Bot Token from environment variable
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")


async def post_init(application) -> None:
    """Automatically sets the bot command menu on startup."""
    commands = [
        BotCommand("start", "Start the bot & welcome message"),
        BotCommand("help", "How to use the converter"),
        BotCommand("about", "About the bot & technical details"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands menu set successfully.")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message when /start is issued."""
    welcome_msg = (
        "👋 **Welcome to the Video Converter Bot!**\n\n"
        "Send or forward me any video file (MKV, MOV, AVI, WEBM, FLV, etc.), "
        "and I will convert it into a standard **MP4** format for you.\n\n"
        "📌 **Available Commands:**\n"
        "/start - Start the bot\n"
        "/help - How to use this bot\n"
        "/about - About the bot"
    )
    await update.message.reply_text(welcome_msg, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends instructions when /help is issued."""
    help_text = (
        "📖 **Help Guide:**\n\n"
        "1. Simply send or forward a video file or document (up to 20MB due to Telegram Bot API limits).\n"
        "2. The bot will automatically download and convert it to **MP4 (H.264/AAC)**.\n"
        "3. Once finished, the converted MP4 will be sent back directly to your chat."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends info when /about is issued."""
    about_text = (
        "🤖 **Video Converter Bot**\n\n"
        "Built with Python (`python-telegram-bot`) and FFmpeg.\n"
        "Hosted securely on Railway."
    )
    await update.message.reply_text(about_text, parse_mode="Markdown")


async def convert_to_mp4(input_path: str, output_path: str) -> bool:
    """Runs FFmpeg asynchronously to convert the input video to MP4 (H.264/AAC)."""
    command = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_path,
    ]

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        logger.error(f"FFmpeg error: {stderr.decode()}")
        return False
    return True


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming video messages and document files."""
    message = update.message

    if message.video:
        file_obj = message.video
        original_filename = message.video.file_name or "input_video.mp4"
    elif message.document:
        file_obj = message.document
        original_filename = message.document.file_name or "input_video"
    else:
        return

    if file_obj.file_size > 20 * 1024 * 1024:
        await message.reply_text("⚠️ File is too large! Bot API limits file downloads to **20MB** max.")
        return

    status_msg = await message.reply_text("📥 Downloading your video...")

    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = os.path.join(temp_dir, original_filename)
        output_path = os.path.join(temp_dir, "converted_video.mp4")

        try:
            tg_file = await context.bot.get_file(file_obj.file_id)
            await tg_file.download_to_drive(input_path)

            await status_msg.edit_text("⚙️ Converting video to MP4 format... Please wait.")

            success = await convert_to_mp4(input_path, output_path)

            if not success or not os.path.exists(output_path):
                await status_msg.edit_text("❌ Failed to convert video. The file might be corrupted or unsupported.")
                return

            await status_msg.edit_text("📤 Uploading converted MP4 video...")

            with open(output_path, "rb") as video_file:
                await message.reply_video(
                    video=video_file,
                    caption="✅ Converted to MP4 successfully!",
                    supports_streaming=True,
                )

            await status_msg.delete()

        except Exception as e:
            logger.exception("An error occurred during processing:")
            await status_msg.edit_text(f"❌ An error occurred: `{str(e)}`", parse_mode="Markdown")


def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("BOT_TOKEN environment variable is not set.")

    # Initialize application with post_init hook
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Command Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about_command))

    # Media Message Handler
    app.add_handler(
        MessageHandler(
            filters.VIDEO | filters.Document.Category("video"),
            handle_video,
        )
    )

    logger.info("Bot started polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
