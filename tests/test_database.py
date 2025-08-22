import pytest
import asyncio
import os
import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

from bot.database import (
    set_db_path, initialize_db, get_user_profile, update_user_profile,
    add_journal_entry, get_journal_entries, search_journal_entries,
    update_token_usage, get_token_summary, get_prompt,
    get_all_journal_entries_for_user, update_journal_entry
)

# Use a temporary in-memory database for testing
TEST_DB_PATH = ":memory:"

@pytest.fixture(autouse=True)
async def setup_and_teardown_db():
    """Fixture to set up and tear down the in-memory database for each test."""
    # Set the DB_FILE to an in-memory database for testing
    # We need to patch the global DB_FILE in the bot.database module
    with patch('bot.database.DB_FILE', TEST_DB_PATH):
        await initialize_db()  # Initialize tables for each test
        yield
        # No explicit teardown needed for :memory: database, it's cleared on close
        # but we can ensure the connection is closed if it were a file-based db
        # For :memory:, it's implicitly closed when the connection object is garbage collected.

@pytest.mark.asyncio
async def test_user_profile_crud():
    user_id = 12345
    telegram_id = 67890
    username = "testuser"

    # Test create/update user profile
    success = await update_user_profile(user_id, telegram_id=telegram_id, username=username, is_approved=True)
    assert success is True

    profile = await get_user_profile(user_id)
    assert profile is not None
    assert profile["user_id"] == user_id
    assert profile["telegram_id"] == telegram_id
    assert profile["username"] == username
    assert profile["is_approved"] == 1

    # Test update existing profile
    new_username = "updated_testuser"
    success = await update_user_profile(user_id, username=new_username, is_approved=False)
    assert success is True

    profile = await get_user_profile(user_id)
    assert profile["username"] == new_username
    assert profile["is_approved"] == 0

    # Test get non-existent profile
    non_existent_profile = await get_user_profile(99999)
    assert non_existent_profile is None

@pytest.mark.asyncio
async def test_journal_entry_crud():
    user_id = 12345
    entry_data = {
        "UserID": user_id,
        "Raw Text": "This is a test journal entry.",
        "Input Type": "text",
        "Word Count": 7,
        "Date": "2025-01-01",
        "Time": "10:00:00"
    }

    entry_id = await add_journal_entry(entry_data)
    assert entry_id is not None

    entries = await get_journal_entries(user_id=user_id)
    assert len(entries) == 1
    assert entries[0]["raw_content"] == "This is a test journal entry."
    assert entries[0]["entry_id"] == entry_id

    # Test update journal entry
    update_success = await update_journal_entry(entry_id, {"Raw Text": "Updated entry."})
    assert update_success is True

    updated_entries = await get_journal_entries(user_id=user_id)
    assert updated_entries[0]["raw_content"] == "Updated entry."

    # Test search journal entries
    search_results = await search_journal_entries(user_id, "Updated")
    assert len(search_results) == 1
    assert search_results[0]["entry_id"] == entry_id

    search_results_no_match = await search_journal_entries(user_id, "nonexistent")
    assert len(search_results_no_match) == 0

    # Test get all journal entries for user
    all_entries = await get_all_journal_entries_for_user(user_id)
    assert len(all_entries) == 1
    assert all_entries[0]["raw_content"] == "Updated entry."

@pytest.mark.asyncio
async def test_token_usage():
    user_id = 12345
    
    # Log some token usage
    await update_token_usage(user_id, 10, 20, "chatbot", "gemini-pro")
    await update_token_usage(user_id, 5, 10, "journal_analysis", "gemini-flash")

    today_str = datetime.now().strftime("%Y-%m-%d")
    summary = await get_token_summary(user_id, today_str)
    assert summary["daily_tokens"] == 45 # 10+20 + 5+10
    assert summary["total_tokens"] == 45

    # Log more for a different day
    with patch('bot.database.datetime') as mock_dt:
        mock_dt.now.return_value = datetime(2025, 1, 2)
        mock_dt.strftime = lambda x: datetime(2025, 1, 2).strftime(x)
        await update_token_usage(user_id, 100, 50, "ocr", "gemini-vision")
    
    summary_today_new = await get_token_summary(user_id, datetime(2025, 1, 2).strftime("%Y-%m-%d"))
    assert summary_today_new["daily_tokens"] == 150
    assert summary_today_new["total_tokens"] == 195 # 45 + 150

@pytest.mark.asyncio
async def test_get_prompt():
    # Prompts are populated during initialize_db
    prompt = await get_prompt("punctuation_prompt")
    assert prompt is not None
    assert "prompt_text" in prompt
    assert "category" in prompt

    non_existent_prompt = await get_prompt("non_existent_prompt")
    assert non_existent_prompt is None
