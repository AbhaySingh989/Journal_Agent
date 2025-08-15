# -*- coding: utf-8 -*-

# --- IMPORTS ---
import logging
import os
import re
import json # Added for JSON operations
from datetime import datetime

# Telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ContextTypes, ConversationHandler, Application
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

# Local Imports
from .constants import (
    SELECTING_MODE, CHATBOT_MODE, JOURNAL_MODE, OCR_MODE, END,
    TEMP_DIR_NAME, JOURNAL_CATEGORIES_LIST
)
from .utils import (
    increment_token_usage, generate_gemini_response, add_punctuation_with_gemini,
    transcribe_audio_with_gemini, generate_mind_map_image, TEMP_DIR,
    generate_sentiment_pie_chart, generate_word_count_trend_chart, get_analytics_summary, generate_historical_mind_map
)
from .database import (
    get_user_profile, update_user_profile, get_token_summary,
    add_journal_entry, update_journal_entry, get_journal_entries, search_journal_entries, get_all_journal_entries_for_user, add_ai_insight
)
from .prompts import (
    PUNCTUATION_PROMPT, AUDIO_TRANSCRIPTION_PROMPT, CATEGORIZATION_PROMPT,
    THERAPIST_ANALYSIS_PROMPT, OCR_PROMPT
)

# --- BASIC SETUP ---
logger = logging.getLogger(__name__)

# --- TELEGRAM COMMAND HANDLERS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Handles the /start command, presenting mode selection buttons."""
    user = update.effective_user
    user_id = user.id # Use integer user_id for database
    user_profile = await get_user_profile(user_id)
    
    # If user profile doesn't exist, create a basic one
    if not user_profile:
        await update_user_profile(user_id, username=user.full_name, is_approved=False) # Default to not approved
        user_profile = await get_user_profile(user_id) # Re-fetch the newly created profile

    username = user_profile.get("username", "there")
    logger.info(f"User {user_id} ({user.username or 'NoUsername'}) executed /start. Name in profile: {username}")
    context.user_data.pop('current_mode', None)
    keyboard = [
        [InlineKeyboardButton(f"💬 {CHATBOT_MODE}", callback_data=CHATBOT_MODE)],
        [InlineKeyboardButton(f"📓 {JOURNAL_MODE}", callback_data=JOURNAL_MODE)],
        [InlineKeyboardButton(f"📄 {OCR_MODE}", callback_data=OCR_MODE)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"Hi {username}! Please choose a mode:", reply_markup=reply_markup)
    return SELECTING_MODE

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the help message with available commands and modes."""
    help_text = '''*Multi-Mode Bot Help*

Use /start or /mode to select a mode:
• *Chatbot:* General conversation.
• *Journal:* Personal notes with AI analysis & mind maps.
• *OCR:* Extract text directly from images.

*Other Commands:*
/setusername <name> - Set display name
/tokens - Check AI token usage
/search <keyword> - Search your journal entries
/end - End current session/mode
/cancel - Cancel current action & return to mode select
/help - Show this message

Send text, voice, or image after selecting a mode. Commands like /end or /cancel should work anytime.
'''
    await update.message.reply_text(escape_markdown(help_text, version=2), parse_mode=ParseMode.MARKDOWN_V2)

async def set_username_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allows users to set or change their display username."""
    user = update.effective_user
    user_id = user.id
    if not context.args:
        await update.message.reply_text("Usage: `/setusername Your Name Here`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    new_username = " ".join(context.args).strip()
    if not new_username or len(new_username) > 50:
        await update.message.reply_text("Invalid username. Must be between 1 and 50 characters.")
        return
    
    if await update_user_profile(user_id, username=new_username):
        logger.info(f"User {user_id} set username to '{new_username}'")
        await update.message.reply_text(f"Username set to: {new_username}")
    else:
        await update.message.reply_text("An error occurred while saving your username.")

async def tokens_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the current AI token usage statistics for the user."""
    user_id = update.effective_user.id
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Retrieve token summary from the database
    token_summary = await get_token_summary(user_id, today_str)
    
    daily_count = token_summary.get("daily_tokens", 0)
    total_count = token_summary.get("total_tokens", 0)
    session_count = context.user_data.get("session_tokens", 0) # Session tokens are in-memory

    message = f'''*Token Usage:*
• Session (since last restart): {session_count:,}
• Today ({today_str}): {daily_count:,}
• Total (all time): {total_count:,}'''
    await update.message.reply_text(escape_markdown(message, version=2), parse_mode=ParseMode.MARKDOWN_V2)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Cancels the current operation and returns to mode selection."""
    user = update.effective_user
    current_mode = context.user_data.get('current_mode')
    logger.info(f"User {user.id} issued /cancel (current mode: {current_mode}). Returning to mode selection.")
    context.user_data.pop('current_mode', None)
    await update.message.reply_text("Operation cancelled. Returning to the main menu.")
    return await start_command(update, context)

async def end_session_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Ends the current bot session."""
    user = update.effective_user
    current_mode = context.user_data.get('current_mode')
    logger.info(f"User {user.id} issued /end (current mode: {current_mode}). Ending session.")
    context.user_data.pop('current_mode', None)
    await update.message.reply_text("✅ Session ended. Use /start to begin a new one.")
    return END

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Searches journal entries for a given query."""
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Please provide a keyword to search for.\nUsage: `/search <keyword>`.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    query = " ".join(context.args).strip()
    logger.info(f"User {user_id} initiated a search for: '{query}'")
    
    status_msg = await update.message.reply_text(f"Searching for entries containing \"{query}\"..." )

    results = await search_journal_entries(user_id, query)

    if not results:
        await status_msg.edit_text(f"No journal entries found matching \"{query}\".")
        return

    response_text = f"Found {len(results)} entries matching \"{query}\":\n\n"
    for entry in results:
        # Safely get the date and a snippet of the content
        entry_date = entry.get('entry_date', 'Unknown Date')
        snippet = entry.get('raw_content', '')[:100] # Get first 100 chars
        response_text += f"*On {escape_markdown(entry_date, version=2)}:*\n`...{escape_markdown(snippet, version=2)}...`\n\n"

    # For long results, we might need to paginate, but for now, send as one message
    # Note: Telegram has a message length limit of 4096 characters.
    if len(response_text) > 4096:
        response_text = response_text[:4090] + "\n... *[truncated]*"

    await status_msg.edit_text(response_text, parse_mode=ParseMode.MARKDOWN_V2)

async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Exports all journal entries for the user as a .txt file."""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} initiated journal export.")

    status_msg = await update.message.reply_text("Gathering your journal entries for export...")

    entries = await get_all_journal_entries_for_user(user_id)

    if not entries:
        await status_msg.edit_text("You don't have any journal entries to export yet.")
        return

    export_content = []
    for entry in entries:
        entry_date = entry.get('entry_date', 'Unknown Date')
        entry_time = entry.get('entry_time', 'Unknown Time')
        raw_content = entry.get('raw_content', 'No content')
        input_type = entry.get('input_type', 'text')
        export_content.append(f"--- Entry on {entry_date} at {entry_time} (Input Type: {input_type}) ---")
        export_content.append(raw_content)
        export_content.append("\n")

    full_export_text = "\n".join(export_content)
    
    # Save to a temporary file
    export_file_path = os.path.join(TEMP_DIR, f"journal_export_{user_id}.txt")
    try:
        with open(export_file_path, "w", encoding="utf-8") as f:
            f.write(full_export_text)
        
        await status_msg.edit_text("Sending your journal export file...")
        await update.message.reply_document(document=open(export_file_path, 'rb'), filename=f"journal_export_{user_id}.txt")
        await status_msg.delete()
        logger.info(f"Successfully exported journal for user {user_id} to {export_file_path}")
    except Exception as e:
        logger.error(f"Error during journal export for user {user_id}: {e}", exc_info=True)
        await status_msg.edit_text("An error occurred while exporting your journal. Please try again later.")
    finally:
        if os.path.exists(export_file_path):
            try:
                os.remove(export_file_path)
                logger.info(f"Deleted temporary export file: {export_file_path}")
            except OSError as e_del:
                logger.error(f"Error deleting temporary export file {export_file_path}: {e_del}")

# --- ANALYTICS COMMAND HANDLERS ---

async def analytics_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provides an analytics overview with visualizations."""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} requested analytics.")

    status_msg = await update.message.reply_text("Generating your analytics report...")

    # Generate visualizations
    sentiment_chart_path = await generate_sentiment_pie_chart(user_id)
    word_count_chart_path = await generate_word_count_trend_chart(user_id)
    
    # Generate text summary
    summary_text = await get_analytics_summary(user_id, context=context)

    await status_msg.edit_text(summary_text)

    if sentiment_chart_path:
        try:
            await update.message.reply_photo(photo=open(sentiment_chart_path, 'rb'), caption="Sentiment Distribution")
            os.remove(sentiment_chart_path)
        except Exception as e:
            logger.error(f"Error sending sentiment chart: {e}")
            await update.message.reply_text("Could not send sentiment chart.")

    if word_count_chart_path:
        try:
            await update.message.reply_photo(photo=open(word_count_chart_path, 'rb'), caption="Word Count Trend")
            os.remove(word_count_chart_path)
        except Exception as e:
            logger.error(f"Error sending word count chart: {e}")
            await update.message.reply_text("Could not send word count chart.")

# --- CALLBACK QUERY HANDLER ---

async def mode_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Handles the mode selection button presses. Sets mode and next state."""
    query = update.callback_query
    user = query.from_user
    await query.answer()
    chosen_mode = query.data
    context.user_data['current_mode'] = chosen_mode
    mode_texts = {CHATBOT_MODE: "Chatbot 💬", JOURNAL_MODE: "Journal 📓", OCR_MODE: "OCR 📄"}
    mode_text = mode_texts.get(chosen_mode, "Unknown")
    next_state = END
    try:
        message_text = f"Mode set to: *{escape_markdown(mode_text, version=2)}*\n"
        if chosen_mode == CHATBOT_MODE:
            next_state = CHATBOT_MODE
            message_text += escape_markdown("You can now send text, audio, or an image for a chat conversation.", version=2)
        elif chosen_mode == JOURNAL_MODE:
            next_state = JOURNAL_MODE
            message_text += escape_markdown("You can now send text, audio, or an image for your journal entry.", version=2)
        elif chosen_mode == OCR_MODE:
            next_state = OCR_MODE
            message_text += escape_markdown("Please send an image to extract text.", version=2)
        else:
            await query.edit_message_text(text="Invalid mode selected. Please use /start again.")
            context.user_data.pop('current_mode', None)
            return END
        await query.edit_message_text(text=message_text, parse_mode=ParseMode.MARKDOWN_V2)
        logger.info(f"User {user.id} entered {mode_text} mode.")
        return next_state
    except Exception as e:
        logger.error(f"Error in mode_button_callback: {e}", exc_info=True)
        try:
            await query.edit_message_text(text=f"An error occurred. Mode set to: {mode_text}.")
        except Exception as fallback_e:
            logger.error(f"Failed to send fallback message in mode_button_callback: {fallback_e}")
        return chosen_mode if chosen_mode in [CHATBOT_MODE, JOURNAL_MODE, OCR_MODE] else END

# --- INPUT PROCESSING & MODE-SPECIFIC LOGIC ---

async def get_text_from_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> tuple[str | None, str | None, str | None]:
    """
    Determines input type, extracts/enhances text, handles errors, cleans up.
    Uses Gemini for both audio transcription and punctuation.
    Shows enhanced audio transcript to user.
    Returns (final_text, input_type, error_message).
    """
    message = update.effective_message
    user_id = update.effective_user.id
    text_input, voice_input, photo_input = message.text, message.voice, message.photo
    temp_file_path, status_msg = None, None
    final_text, input_type = None, None
    try:
        if text_input:
            return text_input, "text", None
        elif voice_input:
            input_type = "audio"
            status_msg = await message.reply_text("⬇️ Downloading audio...")
            temp_file_path = os.path.join(TEMP_DIR, f"{user_id}_{voice_input.file_unique_id}.ogg")
            audio_file = await voice_input.get_file()
            await audio_file.download_to_drive(temp_file_path)
            logger.info(f"Audio downloaded to {temp_file_path}")
            await status_msg.edit_text("🧠 Transcribing audio with AI...")
            raw_text = await transcribe_audio_with_gemini(temp_file_path, context)
            if raw_text is None or "[" in raw_text:
                error_msg = raw_text or "❌ Transcription failed (Unknown error)."
                if status_msg: await status_msg.delete()
                return None, input_type, error_msg
            await status_msg.edit_text("✍️ Enhancing transcript...")
            punctuated_text = await add_punctuation_with_gemini(raw_text, context)
            if status_msg: await status_msg.delete()
            header_text = escape_markdown("*Audio Transcript* (AI Enhanced):", version=2)
            await message.reply_text(header_text, parse_mode=ParseMode.MARKDOWN_V2)
            safe_display_transcript = escape_markdown(punctuated_text, version=2)
            max_len = 4000
            chunks = [safe_display_transcript[i:i+max_len] for i in range(0, len(safe_display_transcript), max_len)]
            for chunk in chunks:
                await message.reply_text(f"```\n{chunk}\n```", parse_mode=ParseMode.MARKDOWN_V2)
            final_text = punctuated_text
        elif photo_input:
            input_type = "image"
            status_msg = await message.reply_text("⬇️ Downloading image...")
            photo = photo_input[-1]
            temp_file_path = os.path.join(TEMP_DIR, f"{user_id}_{photo.file_unique_id}.jpg")
            img_file = await photo.get_file()
            await img_file.download_to_drive(temp_file_path)
            logger.info(f"Image downloaded to {temp_file_path}")
            await status_msg.edit_text("📄 Processing image with AI Vision (OCR)...")
            try:
                with PIL.Image.open(temp_file_path) as img:
                    extracted_text_result, _ = await generate_gemini_response([OCR_PROMPT, img], context=context)
            except Exception as img_err:
                logger.error(f"Error processing image {temp_file_path}: {img_err}")
                return None, input_type, "Error processing image file."
            if status_msg: await status_msg.delete()
            if extracted_text_result is None or "[API ERROR:" in extracted_text_result:
                return None, input_type, extracted_text_result or "❌ AI Vision OCR failed."
            if "[BLOCKED:" in extracted_text_result:
                return None, input_type, f"❌ AI Vision OCR failed ({extracted_text_result})."
            if not extracted_text_result or "[No text content received]" in extracted_text_result:
                return None, input_type, "AI Vision found no text in the image."
            final_text = extracted_text_result
        else:
            return None, None, "Unsupported message type."
        return final_text, input_type, None
    except Exception as e:
        logger.error(f"Error in get_text_from_input: {e}", exc_info=True)
        if status_msg: await status_msg.delete()
        return None, input_type, "An unexpected error occurred processing your input."
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"Temp file deleted: {temp_file_path}")
            except OSError as e_del:
                logger.error(f"Error deleting temp file {temp_file_path}: {e_del}")

async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Routes incoming messages to the appropriate mode handler."""
    user_id = update.effective_user.id
    context.user_data['user_id'] = user_id # Store user_id in context for use in utils.py
    mode = context.user_data.get('current_mode')
    if not mode:
        await update.message.reply_text("Please select a mode first using /start.")
        return
    extracted_text, input_type, error_message = await get_text_from_input(update, context)
    if error_message:
        await update.message.reply_text(error_message)
        return
    if extracted_text is None:
        await update.message.reply_text("Input could not be processed into text.")
        return
    if mode == CHATBOT_MODE:
        await handle_chatbot_logic(update, context, extracted_text)
    elif mode == JOURNAL_MODE:
        await handle_journal_logic(update, context, extracted_text, input_type)
    elif mode == OCR_MODE:
        await handle_ocr_logic(update, context, extracted_text, input_type)
    else:
        logger.error(f"Invalid mode '{mode}' in handle_input")
        await update.message.reply_text("Internal error: Invalid mode.")

async def handle_chatbot_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Handles messages when the bot is in Chatbot mode."""
    user_id = update.effective_user.id
    logger.info(f"Chatbot logic received text (len: {len(text)}) from user {user_id}")
    status_msg = await update.message.reply_text("🤔 Thinking...")
    response_text, _ = await generate_gemini_response([text], context=context)
    if response_text is None or "[API ERROR:" in response_text:
        await status_msg.edit_text(f"Sorry, there was an error contacting the AI. {response_text or ''}")
    elif "[BLOCKED:" in response_text:
        await status_msg.edit_text(f"My response was blocked by the safety filter: {response_text}")
    else:
        await status_msg.edit_text(response_text, parse_mode=None)

async def handle_journal_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, input_type: str):
    """Handles messages in Journal mode, saving, analyzing, and generating a mind map."""
    user = update.effective_user
    user_id = user.id
    user_profile = await get_user_profile(user_id)
    username = user_profile.get("username", f"User_{user_id}") if user_profile else f"User_{user_id}"
    now = datetime.now()
    date_str, time_str = now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")
    logger.info(f"Journal logic received '{input_type}' (len: {len(text)}) from user {user_id}")

    # 1. Save initial entry
    status_msg = await update.message.reply_text("💾 Saving journal entry...")
    entry_data = {
        "UserID": user_id,
        "Raw Text": text,
        "Input Type": input_type,
        "Word Count": len(text.split()),
        "Date": date_str,
        "Time": time_str,
    }
    entry_id = await add_journal_entry(entry_data)
    if not entry_id:
        await status_msg.edit_text("❌ An error occurred while saving your journal entry.")
        return

    # 2. Categorize the entry
    await status_msg.edit_text("📊 Analyzing and categorizing entry...")
    categorization_prompt = CATEGORIZATION_PROMPT.format(text=text, categories_list=", ".join(JOURNAL_CATEGORIES_LIST))
    categorization_response, _ = await generate_gemini_response([categorization_prompt], context=context)

    sentiment, topics, categories = "N/A", "N/A", "N/A"
    if categorization_response and "[BLOCKED:" not in categorization_response and "[API ERROR:" not in categorization_response:
        sentiment = (re.search(r"Sentiment:\s*(.*)", categorization_response, re.I) or ["","N/A"])[1].strip()
        topics = (re.search(r"Topics:\s*(.*)", categorization_response, re.I) or ["","N/A"])[1].strip()
        categories = (re.search(r"Categories:\s*(.*)", categorization_response, re.I) or ["","N/A"])[1].strip()
        logger.info(f"Categorization for entry {entry_id}: S={sentiment}, T={topics}, C={categories}")
        
        # 3. Update entry with categorization
        update_data = {"Sentiment": sentiment, "Topics": topics, "Categories": categories}
        if not await update_journal_entry(entry_id, update_data):
            logger.warning(f"Failed to update journal entry {entry_id} with categorization.")
    else:
        logger.warning(f"Categorization failed or was blocked for entry {entry_id}: {categorization_response}")
        await update.message.reply_text(f"⚠️ AI categorization failed. {categorization_response or ''}")

    # 4. Perform therapist-like analysis and get mind map DOT code
    await status_msg.edit_text("🧠 Performing deeper analysis...")
    all_entries = await get_journal_entries(user_id=user_id)
    
    history_context = "\n\nPrevious Entries (Summary of up to 5 most recent):\n" if len(all_entries) > 1 else "\n\nThis is the user's first entry."
    if len(all_entries) > 1:
        # Create a summary of the last 5 entries (excluding the current one)
        history_summary = [f"- On {e.get('Date')}, you felt '{e.get('Sentiment')}' and wrote about: {e.get('Topics')}." for e in all_entries[-6:-1]]
        history_context += "\n".join(history_summary)

    current_entry_summary = f"Today's Entry ({date_str} {time_str}):\nSentiment: {sentiment}\nTopics: {topics}\nCategories: {categories}\n---\n{text}\n---"
    
    analysis_prompt = THERAPIST_ANALYSIS_PROMPT.format(current_entry_summary=current_entry_summary, history_context=history_context)
    analysis_response_text, _ = await generate_gemini_response([analysis_prompt], context=context)
    
    # Clean the response of markdown backticks before processing
    cleaned_response_text = analysis_response_text.strip()
    if cleaned_response_text.startswith("```") and cleaned_response_text.endswith("```"):
        # It's a markdown block, let's strip the markers and the language hint (e.g., ```dot)
        cleaned_response_text = cleaned_response_text[3:-3].strip()
        if cleaned_response_text.startswith("dot"):
            cleaned_response_text = cleaned_response_text[3:].strip()
    else:
        cleaned_response_text = analysis_response_text

    analysis_output = "Analysis failed."
    dot_code = None
    # Use the CLEANED text for matching
    if cleaned_response_text and "[BLOCKED:" not in cleaned_response_text and "[API ERROR:" not in cleaned_response_text:
        dot_match = re.search(r"---\s*DOT START\s*---(.*)---\s*DOT END\s*---", cleaned_response_text, re.DOTALL | re.I)
        if dot_match:
            dot_code = dot_match.group(1).strip()

            # The AI might still wrap the inner DOT code with markdown, so clean it.
            if dot_code.startswith("```") and dot_code.endswith("```"):
                dot_code = dot_code[3:-3].strip()
            if dot_code.startswith("dot"): # Also remove the language hint
                dot_code = dot_code[3:].strip()

            # The analysis is everything EXCEPT the dot block
            analysis_output = re.sub(r"---\s*DOT START\s*---.*---\s*DOT END\s*---", "", cleaned_response_text, flags=re.DOTALL | re.I).strip()
            logger.info(f"Extracted and cleaned DOT code (len: {len(dot_code)}) for entry {entry_id}")
        else:
            analysis_output = cleaned_response_text # Use the cleaned text for output
            logger.warning(f"DOT markers were missing in the analysis response for entry {entry_id}")
    elif analysis_response_text: # Fallback to original response text for error messages
        analysis_output = f"Analysis failed or was blocked: {analysis_response_text}"
        logger.warning(f"Analysis failed/blocked for entry {entry_id}: {analysis_response_text}")

    # 5. Send the analysis text
    await status_msg.edit_text(analysis_output, parse_mode=None)

    # 6. Generate and send the mind map
    if dot_code:
        map_status = await update.message.reply_text("🗺️ Generating mind map...")
        mind_map_image_path = await generate_mind_map_image(dot_code, user_id, is_historical=False)
        if mind_map_image_path:
            try:
                await update.message.reply_photo(photo=open(mind_map_image_path, 'rb'), caption="Here is a mind map of your current entry.")
                await map_status.delete()
            except Exception as e:
                logger.error(f"Error sending mind map photo for entry {entry_id}: {e}")
                await map_status.edit_text("⚠️ An error occurred while sending the mind map.")
            finally:
                 if os.path.exists(mind_map_image_path):
                     try: os.remove(mind_map_image_path)
                     except OSError as e_del: logger.error(f"Error deleting mind map image: {e_del}")
        else:
            await map_status.edit_text("⚠️ Could not generate the mind map image.")
    else:
        await update.message.reply_text("(A mind map for the current entry was not generated.)")

    await update.message.reply_text("✅ Journal entry processed successfully.")

async def handle_ocr_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, input_type: str):
    """Handles messages when the bot is in OCR mode, displaying extracted text."""
    if input_type != "image":
         await update.message.reply_text("OCR mode requires an image input. Please send an image.")
         return
    logger.info(f"OCR mode sending extracted text (len: {len(text)}) to user {update.effective_user.id}")
    header_text = escape_markdown("*Extracted Text (AI Vision OCR):*", version=2)
    try:
        await update.message.reply_text(header_text, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
         logger.error(f"Error sending OCR header: {e}. Sending plain text fallback.")
         await update.message.reply_text("Extracted Text (AI Vision OCR):")
    safe_extracted_text = escape_markdown(text, version=2)
    max_len = 4000
    chunks = [safe_extracted_text[i:i+max_len] for i in range(0, len(safe_extracted_text), max_len)]
    for i, chunk in enumerate(chunks):
        message_text = f"```\n{chunk}\n```"
        try:
            await update.message.reply_text(message_text, parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as e:
            logger.error(f"Error sending OCR chunk {i+1}: {e}. Sending plain text.")
            plain_text_chunk = text[i*max_len:(i+1)*max_len]
            await update.message.reply_text(plain_text_chunk)

# --- POST INIT FUNCTION ---
async def post_set_commands(application: Application) -> None:
    """Sets the bot's command list in Telegram."""
    commands = [
        BotCommand("start", "Start the bot and select a mode"),
        BotCommand("mode", "Go back to the mode selection menu"),
        BotCommand("changemode", "Alias for /mode"),
        BotCommand("setusername", "Set your display name"),
        BotCommand("tokens", "Check your AI token usage"),
        BotCommand("search", "Search your journal entries"),
        BotCommand("export", "Export all your journal entries"),
        BotCommand("analytics", "Get a visual report of your journaling habits"),
        BotCommand("end", "End the current session"),
        BotCommand("help", "Show the help message"),
        BotCommand("cancel", "Cancel the current action")
    ]
    try:
        await application.bot.set_my_commands(commands)
        logger.info("Bot commands menu updated successfully.")
    except Exception as e:
        logger.error(f"Failed to set bot commands: {e}")

# --- GLOBAL ERROR HANDLER ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Logs errors caused by Updates and notifies the user."""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("Sorry, an unexpected error occurred. Please try again later or use /start.")
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")