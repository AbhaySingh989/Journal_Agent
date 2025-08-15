# -*- coding: utf-8 -*-

# --- CONSTANTS AND FILE PATHS ---

# Conversation states for the ConversationHandler.
SELECTING_MODE, CHATBOT_MODE, JOURNAL_MODE, OCR_MODE, SETTING_USERNAME = ("SELECTING_MODE", "CHATBOT_MODE", "JOURNAL_MODE", "OCR_MODE", "SETTING_USERNAME")
END = "END"

# Define directory and file paths for data storage.
# BASE_DIR will be set dynamically in core.py or main.py
DATA_DIR_NAME = "bot_data"
TEMP_DIR_NAME = "temp"
JOURNAL_FILE_NAME = "journal.csv"
PROFILES_FILE_NAME = "user_profiles.json"
TOKEN_USAGE_FILE_NAME = "token_usage.json"
VISUALIZATIONS_DIR_NAME = "visualizations"

# Headers for the journal CSV file.
JOURNAL_HEADERS = ["Username", "UserID", "Date", "Time", "Raw Text", "Sentiment", "Topics", "Categories", "Word Count", "Input Type", "Entry ID"]
JOURNAL_CATEGORIES_LIST = ["Emotional", "Family", "Grief", "Workplace", "Technology", "AI", "Spouse", "Kid", "Personal Reflection", "Health", "Finance", "Social", "Hobby", "Other"]
