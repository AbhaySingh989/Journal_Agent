# -*- coding: utf-8 -*-

# --- IMPORTS ---
import asyncio
import os
import json
import csv
import logging
from datetime import datetime

# Local Imports
from bot.database import (
    set_db_path, initialize_db, add_journal_entry, update_user_profile, update_token_usage, get_user_profile
)
from bot.constants import (
    DATA_DIR_NAME, JOURNAL_FILE_NAME, PROFILES_FILE_NAME, TOKEN_USAGE_FILE_NAME,
    JOURNAL_HEADERS
)

# --- BASIC SETUP ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- FILE PATHS (Old) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OLD_DATA_DIR = os.path.join(BASE_DIR, DATA_DIR_NAME)
OLD_JOURNAL_FILE = os.path.join(OLD_DATA_DIR, JOURNAL_FILE_NAME)
OLD_PROFILES_FILE = os.path.join(OLD_DATA_DIR, PROFILES_FILE_NAME)
OLD_TOKEN_USAGE_FILE = os.path.join(OLD_DATA_DIR, TOKEN_USAGE_FILE_NAME)

async def migrate_data():
    """Main asynchronous function to orchestrate the data migration."""
    logger.info("Starting data migration process...")

    # 1. Set up database path and initialize DB
    set_db_path(BASE_DIR) # This also ensures bot_data directory exists
    await initialize_db()

    # 2. Migrate User Profiles
    logger.info(f"Migrating user profiles from {OLD_PROFILES_FILE}...")
    if os.path.exists(OLD_PROFILES_FILE):
        try:
            with open(OLD_PROFILES_FILE, 'r', encoding='utf-8') as f:
                old_profiles = json.load(f)
            for user_id_str, profile_data in old_profiles.items():
                user_id = int(user_id_str)
                username = profile_data.get("username", f"User_{user_id}")
                # Assuming all existing users are approved for migration purposes
                is_approved = profile_data.get("is_approved", True) 
                await update_user_profile(user_id, username=username, is_approved=is_approved)
            logger.info(f"Successfully migrated {len(old_profiles)} user profiles.")
        except Exception as e:
            logger.error(f"Error migrating user profiles: {e}", exc_info=True)
    else:
        logger.warning(f"Old user profiles file not found: {OLD_PROFILES_FILE}. Skipping migration.")

    # 3. Migrate Token Usage Data
    logger.info(f"Migrating token usage data from {OLD_TOKEN_USAGE_FILE}...")
    if os.path.exists(OLD_TOKEN_USAGE_FILE):
        try:
            with open(OLD_TOKEN_USAGE_FILE, 'r', encoding='utf-8') as f:
                old_token_data = json.load(f)
            
            # The old token_usage.json had 'total', 'daily', 'session'
            # We need to extract daily counts and update the DB.
            # Note: 'session' tokens are ephemeral and not migrated.
            
            # Migrate historical daily data if available
            if "daily" in old_token_data and "date" in old_token_data["daily"] and "count" in old_token_data["daily"]:
                daily_date = old_token_data["daily"]["date"]
                daily_count = old_token_data["daily"]["count"]
                # For simplicity, we'll assume prompt_tokens = daily_count and completion_tokens = 0 for old daily data
                # A more complex migration might try to infer these if possible.
                await update_token_usage(daily_date, daily_count, 0)
                logger.info(f"Migrated daily token usage for {daily_date}.")
            else:
                logger.warning("No daily token usage found in old data to migrate.")

            # If there's a total from previous runs, ensure it's reflected (this might be tricky with daily granularity)
            # For now, we rely on daily updates to build total. If old total is much higher, it implies past days not captured.
            # This part might need manual adjustment or more sophisticated logic if historical daily data is missing.
            logger.info("Token usage migration completed. Totals will accumulate from daily entries.")

        except Exception as e:
            logger.error(f"Error migrating token usage data: {e}", exc_info=True)
    else:
        logger.warning(f"Old token usage file not found: {OLD_TOKEN_USAGE_FILE}. Skipping migration.")

    # 4. Migrate Journal Entries
    logger.info(f"Migrating journal entries from {OLD_JOURNAL_FILE}...")
    if os.path.exists(OLD_JOURNAL_FILE):
        try:
            migrated_count = 0
            with open(OLD_JOURNAL_FILE, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    logger.warning("Old journal CSV is empty or has no headers. Skipping migration.")
                    return
                for row in reader:
                    # Ensure all expected headers are present in the row, even if empty
                    entry_data = {header: row.get(header, "") for header in JOURNAL_HEADERS}
                    # Convert UserID to int if it's a string
                    try:
                        entry_data["UserID"] = int(entry_data["UserID"])
                    except (ValueError, TypeError):
                        logger.warning(f"Skipping journal entry with invalid UserID: {entry_data.get('UserID')}")
                        continue
                    
                    # Add entry to DB. add_journal_entry generates a new entry_id.
                    # We need to ensure the old entry_id is preserved if it exists and is unique.
                    # For simplicity, we'll let add_journal_entry generate a new one for now.
                    # A more robust migration would check for existing entry_id and update if found.
                    await add_journal_entry(entry_data)
                    migrated_count += 1
            logger.info(f"Successfully migrated {migrated_count} journal entries.")
        except Exception as e:
            logger.error(f"Error migrating journal entries: {e}", exc_info=True)
    else:
        logger.warning(f"Old journal file not found: {OLD_JOURNAL_FILE}. Skipping migration.")

    logger.info("Data migration process completed.")
    logger.info("Please verify the data in the new SQLite database (bot_data/bot_data.db).")
    logger.info("Once verified, you can safely delete the old data files: journal.csv, user_profiles.json, token_usage.json from the bot_data directory.")

if __name__ == "__main__":
    asyncio.run(migrate_data())
