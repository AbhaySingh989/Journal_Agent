# -*- coding: utf-8 -*-

# --- IMPORTS ---
import logging
import os
import asyncio

# Telegram
from telegram.ext import ApplicationBuilder, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram import Update, BotCommand

# Google Gemini
import google.generativeai as genai
from google.generativeai.types import GenerationConfig, SafetySettingDict, HarmCategory, HarmBlockThreshold

# File / Environment
from dotenv import load_dotenv

# Local Imports
from .constants import (
    SELECTING_MODE, CHATBOT_MODE, JOURNAL_MODE, OCR_MODE, END,
    DATA_DIR_NAME, TEMP_DIR_NAME, JOURNAL_FILE_NAME, PROFILES_FILE_NAME,
    TOKEN_USAGE_FILE_NAME, VISUALIZATIONS_DIR_NAME
)
from .utils import (
    set_global_paths, set_gemini_model, set_safety_settings,
    initialize_token_data
)
from .database import set_db_path, initialize_db
from .handlers import (
    start_command, help_command, set_username_command, tokens_command, search_command, export_command, analytics_command,
    cancel_command, end_session_command, mode_button_callback, handle_input,
    error_handler, post_set_commands
)

# --- BASIC SETUP ---
# Configure logging to provide detailed output for monitoring and debugging.
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# Reduce the verbosity of the httpx library which is used by the Telegram API.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- LOAD ENVIRONMENT VARIABLES ---
# Load variables from the .env file into the environment.
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Critical check to ensure all necessary API keys and URLs are present.
if not TELEGRAM_TOKEN or not GEMINI_API_KEY or not WEBHOOK_URL:
    logger.critical("FATAL: Environment variables missing!")
    exit("API Key or Webhook URL Error: Check .env file for TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, and WEBHOOK_URL.")

# --- CONFIGURE GEMINI AI ---
GEMINI_MODEL_NAME = 'gemini-2.0-flash-lite'
try:
    # Initialize the Gemini AI client with the API key.
    genai.configure(api_key=GEMINI_API_KEY)
    generation_config = GenerationConfig()
    # Define safety settings to block harmful content.
    gemini_safety_settings: list[SafetySettingDict] = [
        {"category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
        {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
        {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
        {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
    ]
    # Create the generative model instance.
    gemini_model = genai.GenerativeModel(
        GEMINI_MODEL_NAME,
        generation_config=generation_config,
        safety_settings=gemini_safety_settings
    )
    # Pass the configured model and safety settings to utils for use in other modules.
    set_gemini_model(gemini_model)
    set_safety_settings(gemini_safety_settings)
    logger.info(f"Gemini Model '{GEMINI_MODEL_NAME}' configured and set in utils.")
except Exception as e:
    logger.critical(f"Failed to configure Gemini: {e}", exc_info=True)
    exit("Gemini Configuration Error.")

# --- APPLICATION SETUP ---
# Create the Application instance using ApplicationBuilder.
# This application object is defined globally so it can be imported and used by the Flask web server (app.py).
application = (
    ApplicationBuilder()
    .token(TELEGRAM_TOKEN)
    .build()
)

# --- MAIN BOT SETUP FUNCTION ---
async def main() -> None:
    """
    Sets up all the handlers for the bot, initializes the application,
    and configures the webhook. This function is called once when the
    web server starts.
    """
    # Set global paths for data directories in utils module.
    # Determine the project root directory (one level up from the 'bot' package)
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    set_global_paths(PROJECT_ROOT)

    # --- ADD HANDLERS ---
    # Add the global error handler first.
    application.add_error_handler(error_handler)

    # This handler manages the different modes of the bot (Chatbot, Journal, OCR).
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start_command),
            CommandHandler('mode', start_command),
            CommandHandler('changemode', start_command)
        ],
        states={
            SELECTING_MODE: [CallbackQueryHandler(mode_button_callback)],
            CHATBOT_MODE: [MessageHandler(filters.ChatType.PRIVATE & (filters.TEXT | filters.VOICE | filters.PHOTO | filters.Document.IMAGE) & ~filters.COMMAND, handle_input)],
            JOURNAL_MODE: [MessageHandler(filters.ChatType.PRIVATE & (filters.TEXT | filters.VOICE | filters.PHOTO | filters.Document.IMAGE) & ~filters.COMMAND, handle_input)],
            OCR_MODE: [
                MessageHandler(filters.ChatType.PRIVATE & (filters.PHOTO | filters.Document.IMAGE) & ~filters.COMMAND, handle_input),
                MessageHandler(filters.ChatType.PRIVATE & (filters.TEXT | filters.VOICE) & ~filters.COMMAND, lambda u,c: u.message.reply_text("OCR mode requires an image."))
            ],
        },
        fallbacks=[
            CommandHandler('cancel', cancel_command),
            CommandHandler('end', end_session_command),
            CommandHandler('start', start_command),
            CommandHandler('mode', start_command),
            CommandHandler('changemode', start_command),
            CommandHandler('help', help_command),
            CommandHandler('setusername', set_username_command),
            CommandHandler('tokens', tokens_command),
            CommandHandler('search', search_command),
            CommandHandler('export', export_command),
            CommandHandler('analytics', analytics_command),
        ],
        allow_reentry=False
    )
    application.add_handler(conv_handler)

    # These handlers work outside the main conversation flow.
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("setusername", set_username_command))
    application.add_handler(CommandHandler("tokens", tokens_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("analytics", analytics_command))

    # This handler catches any message that isn't a command and isn't in a conversation.
    # It prompts the user to start the bot correctly.
    application.add_handler(MessageHandler(
        filters.UpdateType.MESSAGE & ~filters.COMMAND & filters.ChatType.PRIVATE,
        lambda u, c: u.message.reply_text("Please use /start or /mode to begin.")
    ))

    # --- INITIALIZE APPLICATION ---
    # This runs setup routines for the application instance, which is required for webhooks.
    logger.info("Initializing application...")
    await application.initialize()
    logger.info("Application initialized.")

    # --- WEBHOOK SETUP ---
    # Now that the app is initialized, we can set the webhook.
    webhook_full_url = f"{WEBHOOK_URL}/webhook"
    logger.info(f"Setting webhook to {webhook_full_url}...")
    await application.bot.set_webhook(url=webhook_full_url)
    logger.info("Webhook set successfully.")

    # --- INITIALIZE CUSTOM DATA ---
    # Set the database path and initialize the database.
    set_db_path(PROJECT_ROOT)
    await initialize_db()

    # Reset session token count (managed in-memory for current session).
    await initialize_token_data()
    logger.info("Bot setup complete.")

    # Set the bot commands menu
    await post_set_commands(application)
