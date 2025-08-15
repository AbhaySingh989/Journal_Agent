# -*- coding: utf-8 -*-

# --- IMPORTS ---
import logging
import asyncio
import threading
from flask import Flask, request, jsonify
from telegram import Update

# Import the main bot setup function and the application object
from bot.core import main as initialize_bot, application
from bot.handlers import post_set_commands

# --- BASIC SETUP ---
# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# --- ASYNCIO EVENT LOOP IN A SEPARATE THREAD ---
# This is the standard pattern for using an asyncio library (like python-telegram-bot)
# with a synchronous web framework (like Flask).
# We create a single, persistent event loop in a background thread.
# The Flask app can then safely submit work to this loop from its request threads.

# 1. Create a new event loop that will run in the background.
loop = asyncio.new_event_loop()

# 2. Define the function that will run in the background thread.
def run_asyncio_loop():
    """Sets the event loop for the current thread and runs it forever."""
    asyncio.set_event_loop(loop)
    loop.run_forever()

# 3. Create and start the background thread.
thread = threading.Thread(target=run_asyncio_loop)
thread.daemon = True  # Allows main thread to exit even if this thread is running
thread.start()
logger.info("Asyncio event loop running in a background thread.")


# --- INITIALIZE THE BOT ---
# We use `run_coroutine_threadsafe` to schedule the bot's async initialization
# on the event loop we created in the background thread.
logger.info("Scheduling bot initialization...")
# This schedules the main() function from your bot script to run on the loop.
future = asyncio.run_coroutine_threadsafe(initialize_bot(), loop)
# We wait for the initialization to complete before starting the Flask app.
future.result()
logger.info("Bot initialization complete.")

# --- SET BOT COMMANDS ---
logger.info("Scheduling command menu update...")
# Explicitly set the commands after initialization is complete.
asyncio.run_coroutine_threadsafe(post_set_commands(application), loop).result()
logger.info("Command menu update complete.")


# --- FLASK APP INITIALIZATION ---
app = Flask(__name__)


# --- WEBHOOK ENDPOINT ---
@app.route('/webhook', methods=['POST'])
def webhook():
    """This endpoint receives updates from Telegram and schedules them on the event loop."""
    try:
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, application.bot)
        
        # Schedule the processing of the update on the event loop.
        # This is thread-safe and allows the async function to run in the background.
        asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
        
        # Return a 200 OK response to Telegram immediately.
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        app.logger.error(f"Error processing webhook: {e}", exc_info=True)
        return jsonify({"status": "error"}), 200

# --- HEALTH CHECK ENDPOINT ---
@app.route('/', methods=['GET'])
def index():
    """A simple health check endpoint to verify the server is running."""
    return "Hello, your bot is alive!", 200

# This script is intended to be run by a WSGI server (like Gunicorn or Waitress).