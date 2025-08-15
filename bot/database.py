# -*- coding: utf-8 -*-

# --- IMPORTS ---
import sqlite3
import logging
import os
import json
from datetime import datetime
import uuid # For generating unique IDs

# Local Imports
from .constants import (
    DATA_DIR_NAME, JOURNAL_HEADERS, JOURNAL_CATEGORIES_LIST
)
from .prompts import (
    PUNCTUATION_PROMPT, AUDIO_TRANSCRIPTION_PROMPT, CATEGORIZATION_PROMPT,
    THERAPIST_ANALYSIS_PROMPT, OCR_PROMPT
)

# --- BASIC SETUP ---
logger = logging.getLogger(__name__)

# --- GLOBAL VARIABLES ---
DB_FILE = ""



# --- INITIALIZATION FUNCTIONS (called from core.py) ---
def set_db_path(base_dir: str):
    """Sets the global database file path."""
    global DB_FILE
    # The database file will be named 'bot_data.db' and reside in the DATA_DIR
    data_dir = os.path.join(base_dir, DATA_DIR_NAME)
    os.makedirs(data_dir, exist_ok=True) # Ensure data directory exists
    DB_FILE = os.path.join(data_dir, "bot_data.db")
    logger.info(f"Database file path set to: {DB_FILE}")

async def initialize_db(db_path: str = None):
    """Initializes the SQLite database, creating tables if they don't exist and populating prompts."""
    conn = None
    try:
        conn = sqlite3.connect(db_path or DB_FILE, check_same_thread=False)
        cursor = conn.cursor()

        # Create Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Users (
                user_id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active_at TIMESTAMP,
                timezone TEXT,
                preferred_language TEXT,
                is_approved INTEGER DEFAULT 0,
                settings TEXT -- Stored as JSON string
            )
        """)

        # Create JournalEntries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS JournalEntries (
                entry_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                raw_content TEXT NOT NULL,
                input_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                entry_date TEXT,
                entry_time TEXT,
                word_count INTEGER,
                is_private INTEGER DEFAULT 1,
                location_data TEXT, -- Stored as JSON string
                device_info TEXT,
                ai_model_version TEXT
            )
        """)

        # Create AIInsights table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS AIInsights (
                insight_id TEXT PRIMARY KEY,
                entry_id TEXT NOT NULL,
                sentiment_score REAL,
                sentiment_label TEXT,
                detected_emotions TEXT, -- Stored as JSON string
                key_topics TEXT, -- Stored as JSON string
                named_entities TEXT, -- Stored as JSON string
                summary TEXT,
                reflection_questions TEXT, -- Stored as JSON string
                cognitive_distortions TEXT, -- Stored as JSON string
                ai_feedback_rating INTEGER,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create Prompts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Prompts (
                prompt_id TEXT PRIMARY KEY,
                prompt_text TEXT NOT NULL,
                category TEXT,
                is_guided INTEGER DEFAULT 0,
                created_by_user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create TokenUsage table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS TokenUsage (
                usage_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL,
                completion_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                feature_used TEXT,
                model_name TEXT,
                logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create UserMoods table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS UserMoods (
                mood_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                mood_label TEXT NOT NULL,
                mood_intensity INTEGER,
                logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                associated_entry_id TEXT,
                custom_tags TEXT -- Stored as JSON string
            )
        """)

        # Create UserActivities table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS UserActivities (
                activity_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                activity_label TEXT NOT NULL,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                category TEXT,
                associated_entry_id TEXT,
                notes TEXT
            )
        """)

        # Create Goals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Goals (
                goal_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                goal_name TEXT NOT NULL,
                description TEXT,
                target_metric TEXT,
                start_date TEXT NOT NULL,
                end_date TEXT,
                status TEXT DEFAULT 'active',
                priority INTEGER,
                tags TEXT -- Stored as JSON string
            )
        """)

        # Create GoalProgress table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS GoalProgress (
                progress_id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                progress_value REAL,
                notes TEXT,
                associated_entry_id TEXT
            )
        """)

        # Create PromptResponses table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS PromptResponses (
                response_id TEXT PRIMARY KEY,
                entry_id TEXT NOT NULL UNIQUE,
                prompt_id TEXT NOT NULL,
                responded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Add new columns if they don't exist
        journal_columns = [col[1] for col in cursor.execute("PRAGMA table_info(JournalEntries)").fetchall()]
        if 'Sentiment' not in journal_columns:
            cursor.execute("ALTER TABLE JournalEntries ADD COLUMN Sentiment TEXT")
        if 'Topics' not in journal_columns:
            cursor.execute("ALTER TABLE JournalEntries ADD COLUMN Topics TEXT")
        if 'Categories' not in journal_columns:
            cursor.execute("ALTER TABLE JournalEntries ADD COLUMN Categories TEXT")

        # Populate Prompts table with initial data if empty
        initial_prompts = [
            {"prompt_id": "punctuation_prompt", "prompt_text": PUNCTUATION_PROMPT, "category": "AI_Utility"},
            {"prompt_id": "audio_transcription_prompt", "prompt_text": AUDIO_TRANSCRIPTION_PROMPT, "category": "AI_Utility"},
            {"prompt_id": "categorization_prompt", "prompt_text": CATEGORIZATION_PROMPT, "category": "AI_Analysis"},
            {"prompt_id": "therapist_analysis_prompt", "prompt_text": THERAPIST_ANALYSIS_PROMPT, "category": "AI_Analysis"},
            {"prompt_id": "ocr_prompt", "prompt_text": OCR_PROMPT, "category": "AI_Utility"},
        ]

        for prompt in initial_prompts:
            cursor.execute("INSERT OR IGNORE INTO Prompts (prompt_id, prompt_text, category) VALUES (?, ?, ?)",
                           (prompt["prompt_id"], prompt["prompt_text"], prompt["category"]))
        
        conn.commit()
        logger.info("Database tables checked/created and Prompts populated successfully.")
    except sqlite3.Error as e:
        logger.error(f"Database initialization error: {e}", exc_info=True)
    finally:
        if conn: conn.close()

# --- CRUD OPERATIONS FOR USERS ---
async def get_user_profile(user_id: int, db_path: str = None) -> dict | None:
    """Retrieves a user profile by user ID."""
    conn = None
    try:
        conn = sqlite3.connect(db_path or DB_FILE, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            logger.info(f"Retrieved profile for user {user_id}.")
            return dict(row)
        logger.info(f"Profile not found for user {user_id}.")
        return None
    except sqlite3.Error as e:
        logger.error(f"Error retrieving user profile {user_id}: {e}", exc_info=True)
        return None
    finally:
        if conn: conn.close()

async def update_user_profile(user_id: int, telegram_id: int | None = None, username: str | None = None, is_approved: bool | None = None, created_at: datetime | None = None, last_active_at: datetime | None = None, timezone: str | None = None, preferred_language: str | None = None, settings: dict | None = None, db_path: str = None) -> bool:
    """Updates or creates a user profile."""
    conn = None
    try:
        conn = sqlite3.connect(db_path or DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        
        # Check if profile exists
        cursor.execute("SELECT 1 FROM Users WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone()

        if exists:
            set_clauses = []
            values = []
            if telegram_id is not None: set_clauses.append("telegram_id = ?"); values.append(telegram_id)
            if username is not None: set_clauses.append("username = ?"); values.append(username)
            if is_approved is not None: set_clauses.append("is_approved = ?"); values.append(1 if is_approved else 0)
            if created_at is not None: set_clauses.append("created_at = ?"); values.append(created_at.isoformat())
            if last_active_at is not None: set_clauses.append("last_active_at = ?"); values.append(last_active_at.isoformat())
            if timezone is not None: set_clauses.append("timezone = ?"); values.append(timezone)
            if preferred_language is not None: set_clauses.append("preferred_language = ?"); values.append(preferred_language)
            if settings is not None: set_clauses.append("settings = ?"); values.append(json.dumps(settings))

            if not set_clauses: return False # No valid fields to update

            values.append(user_id)
            query = f"UPDATE Users SET {', '.join(set_clauses)} WHERE user_id = ?"
            cursor.execute(query, tuple(values))
            logger.info(f"Updated profile for user {user_id}.")
        else:
            # Insert new profile
            cursor.execute("""
                INSERT INTO Users (user_id, telegram_id, username, is_approved, created_at, last_active_at, timezone, preferred_language, settings)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, telegram_id if telegram_id is not None else user_id, username,
                1 if is_approved else 0, created_at.isoformat() if created_at else datetime.now().isoformat(),
                last_active_at.isoformat() if last_active_at else datetime.now().isoformat(),
                timezone, preferred_language, json.dumps(settings) if settings else None
            ))
            logger.info(f"Created profile for new user {user_id}.")

        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating/creating user profile {user_id}: {e}", exc_info=True)
        return False
    finally:
        if conn: conn.close()

# --- CRUD OPERATIONS FOR AI INSIGHTS ---
async def add_ai_insight(entry_id: str, insight_data: dict, db_path: str = None) -> bool:
    """Adds AI-generated insights for a specific journal entry."""
    conn = None
    try:
        conn = sqlite3.connect(db_path or DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        insight_id = str(uuid.uuid4())

        cursor.execute("""
            INSERT INTO AIInsights (
                insight_id, entry_id, sentiment_score, sentiment_label, 
                detected_emotions, key_topics, named_entities, summary, 
                reflection_questions, cognitive_distortions
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            insight_id, entry_id, 
            insight_data.get('sentiment_score'), insight_data.get('sentiment_label'),
            json.dumps(insight_data.get('detected_emotions')), json.dumps(insight_data.get('key_topics')),
            json.dumps(insight_data.get('named_entities')), insight_data.get('summary'),
            json.dumps(insight_data.get('reflection_questions')), json.dumps(insight_data.get('cognitive_distortions'))
        ))
        conn.commit()
        logger.info(f"Added AI insight for entry ID: {entry_id}")
        return True
    except sqlite3.Error as e:
        logger.error(f"Error adding AI insight for entry {entry_id}: {e}", exc_info=True)
        return False
    finally:
        if conn: conn.close()

# --- CRUD OPERATIONS FOR JOURNAL ENTRIES ---
async def add_journal_entry(entry_data: dict, db_path: str = None) -> str | None:
    """Adds a new journal entry to the database."""
    conn = None
    try:
        conn = sqlite3.connect(db_path or DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        
        # Generate a unique entry ID if not provided
        entry_id = entry_data.get("entry_id", str(uuid.uuid4()))

        cursor.execute("""
            INSERT INTO JournalEntries (
                entry_id, user_id, raw_content, input_type, created_at,
                modified_at, entry_date, entry_time, word_count, is_private,
                location_data, device_info, ai_model_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry_id, entry_data["UserID"], entry_data["Raw Text"], entry_data["Input Type"],
            entry_data.get("Date", datetime.now().strftime("%Y-%m-%d")) + " " + entry_data.get("Time", datetime.now().strftime("%H:%M:%S")), # created_at
            entry_data.get("modified_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")), # modified_at
            entry_data.get("Date", datetime.now().strftime("%Y-%m-%d")), # entry_date
            entry_data.get("Time", datetime.now().strftime("%H:%M:%S")), # entry_time
            entry_data.get("Word Count", 0), entry_data.get("is_private", 1),
            json.dumps(entry_data.get("location_data")) if entry_data.get("location_data") else None,
            entry_data.get("device_info"), entry_data.get("ai_model_version")
        ))
        conn.commit()
        logger.info(f"Added journal entry ID: {entry_id}")
        return entry_id
    except sqlite3.Error as e:
        logger.error(f"Error adding journal entry: {e}", exc_info=True)
        return None
    finally:
        if conn: conn.close()

async def update_journal_entry(entry_id: str, update_data: dict, db_path: str = None) -> bool:
    """Updates an existing journal entry by its ID."""
    conn = None
    try:
        conn = sqlite3.connect(db_path or DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        set_clauses = []
        values = []
        
        # Mapping from old CSV headers to new DB column names
        column_map = {
            "Username": "username", "UserID": "user_id", "Date": "entry_date",
            "Time": "entry_time", "Raw Text": "raw_content", 
            "Sentiment": "Sentiment", "Topics": "Topics", "Categories": "Categories",
            "Word Count": "word_count", "Input Type": "input_type", "Entry ID": "entry_id",
            "is_private": "is_private", "location_data": "location_data",
            "device_info": "device_info", "ai_model_version": "ai_model_version"
        }

        for key, value in update_data.items():
            db_column = column_map.get(key, key) # Use mapped name or original key
            if db_column in [col[1] for col in cursor.execute("PRAGMA table_info(JournalEntries)").fetchall()]: # Check if column exists
                set_clauses.append(f"{db_column} = ?")
                if isinstance(value, dict): # Handle JSONB fields
                    values.append(json.dumps(value))
                else:
                    values.append(value)
        
        if not set_clauses: return False # No valid fields to update

        values.append(entry_id)
        query = f"UPDATE JournalEntries SET {', '.join(set_clauses)}, modified_at = CURRENT_TIMESTAMP WHERE entry_id = ?"
        cursor.execute(query, tuple(values))
        conn.commit()
        if cursor.rowcount > 0:
            logger.info(f"Updated journal entry ID: {entry_id}")
            return True
        else:
            logger.warning(f"Journal entry ID {entry_id} not found for update.")
            return False
    except sqlite3.Error as e:
        logger.error(f"Error updating journal entry {entry_id}: {e}", exc_info=True)
        return False
    finally:
        if conn: conn.close()

async def get_journal_entries(user_id: int | None = None, db_path: str = None) -> list[dict]:
    """Retrieves journal entries from the database, optionally filtered by user ID."""
    conn = None
    entries = []
    try:
        conn = sqlite3.connect(db_path or DB_FILE, check_same_thread=False)
        conn.row_factory = sqlite3.Row # Return rows as dict-like objects
        cursor = conn.cursor()
        query = "SELECT * FROM JournalEntries"
        params = ()
        if user_id is not None:
            query += " WHERE user_id = ?"
            params = (user_id,)
        query += " ORDER BY created_at"
        cursor.execute(query, params)
        for row in cursor.fetchall():
            entry = dict(row)
            # Convert JSON strings back to dicts if necessary
            if 'location_data' in entry and entry['location_data']:
                entry['location_data'] = json.loads(entry['location_data'])
            if 'Sentiment' in entry and entry['Sentiment']:
                # Sentiment is a string, no need to load JSON
                pass
            if 'Topics' in entry and entry['Topics'] is not None:
                raw_topics = str(entry['Topics']).strip()
                if raw_topics.startswith('[') and raw_topics.endswith(']'):
                    try:
                        entry['Topics'] = json.loads(raw_topics)
                    except json.JSONDecodeError:
                        logger.warning(f"Could not decode Topics JSON for entry {entry.get('entry_id')}. Falling back to comma split.")
                        entry['Topics'] = [t.strip() for t in raw_topics.split(',') if t.strip()]
                elif raw_topics:
                    entry['Topics'] = [t.strip() for t in raw_topics.split(',') if t.strip()]
                else:
                    entry['Topics'] = []
            else:
                entry['Topics'] = []

            if 'Categories' in entry and entry['Categories'] is not None:
                raw_categories = str(entry['Categories']).strip()
                if raw_categories.startswith('[') and raw_categories.endswith(']'):
                    try:
                        entry['Categories'] = json.loads(raw_categories)
                    except json.JSONDecodeError:
                        logger.warning(f"Could not decode Categories JSON for entry {entry.get('entry_id')}. Falling back to comma split.")
                        entry['Categories'] = [c.strip() for c in raw_categories.split(',') if c.strip()]
                elif raw_categories:
                    entry['Categories'] = [c.strip() for c in raw_categories.split(',') if c.strip()]
                else:
                    entry['Categories'] = []
            else:
                entry['Categories'] = []
            entries.append(entry)
        logger.info(f"Retrieved {len(entries)} journal entries for user {user_id if user_id else 'all'}.")
        return entries
    except sqlite3.Error as e:
        logger.error(f"Error retrieving journal entries: {e}", exc_info=True)
        return []
    finally:
        if conn: conn.close()

async def search_journal_entries(user_id: int, query: str, db_path: str = None) -> list[dict]:
    """Searches for journal entries for a specific user containing the query string."""
    conn = None
    entries = []
    try:
        conn = sqlite3.connect(db_path or DB_FILE, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        search_query = f"%{query}%"
        cursor.execute("SELECT * FROM JournalEntries WHERE user_id = ? AND raw_content LIKE ? ORDER BY created_at DESC", (user_id, search_query))
        for row in cursor.fetchall():
            entries.append(dict(row))
        logger.info(f"Found {len(entries)} journal entries for user {user_id} matching '{query}'.")
        return entries
    except sqlite3.Error as e:
        logger.error(f"Error searching journal entries for user {user_id}: {e}", exc_info=True)
        return []
    finally:
        if conn: conn.close()

async def get_all_journal_entries_for_user(user_id: int, db_path: str = None) -> list[dict]:
    """Retrieves all journal entries for a specific user."""
    conn = None
    entries = []
    try:
        conn = sqlite3.connect(db_path or DB_FILE, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT entry_date, entry_time, raw_content, input_type FROM JournalEntries WHERE user_id = ? ORDER BY created_at ASC", (user_id,))
        for row in cursor.fetchall():
            entries.append(dict(row))
        logger.info(f"Retrieved {len(entries)} journal entries for user {user_id}.")
        return entries
    except sqlite3.Error as e:
        logger.error(f"Error retrieving all journal entries for user {user_id}: {e}", exc_info=True)
        return []
    finally:
        if conn: conn.close()

# --- CRUD OPERATIONS FOR TOKEN USAGE ---
async def update_token_usage(user_id: int, prompt_tokens: int, completion_tokens: int, feature_used: str | None, model_name: str | None, db_path: str = None) -> bool:
    """Inserts a new token usage record for each API call."""
    conn = None
    try:
        conn = sqlite3.connect(db_path or DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        usage_id = str(uuid.uuid4())
        date_str = datetime.now().strftime("%Y-%m-%d")
        total_tokens = prompt_tokens + completion_tokens

        cursor.execute("""
            INSERT INTO TokenUsage (usage_id, user_id, date, prompt_tokens, completion_tokens, total_tokens, feature_used, model_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (usage_id, user_id, date_str, prompt_tokens, completion_tokens, total_tokens, feature_used, model_name))
        
        conn.commit()
        logger.info(f"Logged {total_tokens} tokens for user {user_id} using {feature_used}.")
        return True
    except sqlite3.Error as e:
        logger.error(f"Error logging token usage for user {user_id}: {e}", exc_info=True)
        return False
    finally:
        if conn: conn.close()

async def get_token_summary(user_id: int, date: str, db_path: str = None) -> dict:
    """Retrieves and calculates token usage summary for a specific user and date."""
    summary = {"daily_tokens": 0, "total_tokens": 0}
    conn = None
    try:
        conn = sqlite3.connect(db_path or DB_FILE, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Calculate daily tokens for the given date
        cursor.execute("SELECT SUM(total_tokens) FROM TokenUsage WHERE user_id = ? AND date = ?", (user_id, date))
        daily_result = cursor.fetchone()
        if daily_result and daily_result[0] is not None:
            summary["daily_tokens"] = daily_result[0]

        # Calculate total tokens for all time
        cursor.execute("SELECT SUM(total_tokens) FROM TokenUsage WHERE user_id = ?", (user_id,))
        total_result = cursor.fetchone()
        if total_result and total_result[0] is not None:
            summary["total_tokens"] = total_result[0]
        
        logger.info(f"Retrieved token summary for user {user_id}: {summary}")
        return summary
    except sqlite3.Error as e:
        logger.error(f"Error retrieving token summary for user {user_id}: {e}", exc_info=True)
        return summary # Return default summary on error
    finally:
        if conn: conn.close()

# --- CRUD OPERATIONS FOR PROMPTS ---
async def get_prompt(prompt_id: str) -> dict | None:
    """Retrieves a prompt by its ID."""
    conn = None
    try:
        conn = sqlite3.connect(db_path or DB_FILE, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Prompts WHERE prompt_id = ?", (prompt_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    except sqlite3.Error as e:
        logger.error(f"Error retrieving prompt {prompt_id}: {e}", exc_info=True)
        return None
    finally:
        if conn: conn.close()

# --- ANALYTICS FUNCTIONS ---
async def get_sentiment_distribution(user_id: int, period_days: int = 7, db_path: str = None) -> list[tuple]:
    """Retrieves the distribution of sentiment labels for a user over a specified period."""
    conn = None
    try:
        conn = sqlite3.connect(db_path or DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        
        query = """
            SELECT sentiment_label, COUNT(*)
            FROM AIInsights
            JOIN JournalEntries ON AIInsights.entry_id = JournalEntries.entry_id
            WHERE JournalEntries.user_id = ? AND JournalEntries.created_at >= date('now', '-' || ? || ' days')
            GROUP BY sentiment_label
        """
        
        cursor.execute(query, (user_id, period_days))
        results = cursor.fetchall()
        logger.info(f"Retrieved sentiment distribution for user {user_id} for the last {period_days} days.")
        return results
    except sqlite3.Error as e:
        logger.error(f"Error retrieving sentiment distribution for user {user_id}: {e}", exc_info=True)
        return []
    finally:
        if conn: conn.close()

async def get_topic_frequency(user_id: int, period_days: int = 7, db_path: str = None) -> list[tuple]:
    """Retrieves the frequency of topics for a user over a specified period.
    This function assumes topics are stored as a JSON string array in the key_topics column.
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path or DB_FILE, check_same_thread=False)
        cursor = conn.cursor()

        # This query is more complex as it needs to parse JSON.
        # It might be slow on large datasets.
        # For simplicity, we'll fetch the rows and process in Python.
        query = """
            SELECT key_topics
            FROM AIInsights
            JOIN JournalEntries ON AIInsights.entry_id = JournalEntries.entry_id
            WHERE JournalEntries.user_id = ? AND JournalEntries.created_at >= date('now', '-' || ? || ' days')
        """
        
        cursor.execute(query, (user_id, period_days))
        rows = cursor.fetchall()
        
        topic_counts = {}
        for row in rows:
            if row[0]:
                topics = json.loads(row[0])
                for topic in topics:
                    topic_counts[topic] = topic_counts.get(topic, 0) + 1
        
        # Sort by frequency
        sorted_topics = sorted(topic_counts.items(), key=lambda item: item[1], reverse=True)
        
        logger.info(f"Retrieved topic frequency for user {user_id} for the last {period_days} days.")
        return sorted_topics
    except sqlite3.Error as e:
        logger.error(f"Error retrieving topic frequency for user {user_id}: {e}", exc_info=True)
        return []
    finally:
        if conn: conn.close()

async def get_word_count_trends(user_id: int, period_days: int = 7, db_path: str = None) -> list[tuple]:
    """Retrieves the word count of journal entries for a user over a specified period."""
    conn = None
    try:
        conn = sqlite3.connect(db_path or DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        
        query = """
            SELECT date(created_at), SUM(word_count)
            FROM JournalEntries
            WHERE user_id = ? AND created_at >= date('now', '-' || ? || ' days')
            GROUP BY date(created_at)
            ORDER BY date(created_at)
        """
        
        cursor.execute(query, (user_id, period_days))
        results = cursor.fetchall()
        logger.info(f"Retrieved word count trends for user {user_id} for the last {period_days} days.")
        return results
    except sqlite3.Error as e:
        logger.error(f"Error retrieving word count trends for user {user_id}: {e}", exc_info=True)
        return []
    finally:
        if conn: conn.close()

async def get_top_topics_overall(user_id: int, limit: int = 7, db_path: str = None) -> list[str]:
    """Retrieves the most frequent topics for a user across all their entries."""
    conn = None
    try:
        conn = sqlite3.connect(db_path or DB_FILE, check_same_thread=False)
        cursor = conn.cursor()

        query = """
            SELECT key_topics
            FROM AIInsights
            JOIN JournalEntries ON AIInsights.entry_id = JournalEntries.entry_id
            WHERE JournalEntries.user_id = ?
        """
        
        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()
        
        topic_counts = {}
        for row in rows:
            if row[0]:
                try:
                    topics = json.loads(row[0])
                    for topic in topics:
                        topic_counts[topic] = topic_counts.get(topic, 0) + 1
                except json.JSONDecodeError:
                    # Handle cases where key_topics might not be a valid JSON array string
                    # This could happen with older data or if the string is just a simple topic
                    for topic in str(row[0]).split(','):
                        topic = topic.strip()
                        if topic:
                            topic_counts[topic] = topic_counts.get(topic, 0) + 1

        # Sort by frequency and return the top `limit` topics
        sorted_topics = sorted(topic_counts.items(), key=lambda item: item[1], reverse=True)
        top_topics = [topic for topic, count in sorted_topics[:limit]]
        
        logger.info(f"Retrieved top {len(top_topics)} overall topics for user {user_id}.")
        return top_topics
    except sqlite3.Error as e:
        logger.error(f"Error retrieving top overall topics for user {user_id}: {e}", exc_info=True)
        return []
    finally:
        if conn: conn.close()