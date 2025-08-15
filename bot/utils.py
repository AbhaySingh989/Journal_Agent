# -*- coding: utf-8 -*-

# --- IMPORTS ---
import logging
import os
import json
from datetime import datetime, timedelta
import asyncio
import functools

# Telegram
from telegram.ext import ContextTypes

# Google Gemini
import google.generativeai as genai
from google.generativeai.types import SafetySettingDict, HarmCategory, HarmBlockThreshold
from google.generativeai import types as genai_types

# File / Environment
import PIL.Image # Pillow for image handling

# Visualization
import graphviz

# Local Imports
from .constants import (
    DATA_DIR_NAME, TEMP_DIR_NAME, VISUALIZATIONS_DIR_NAME, JOURNAL_HEADERS, JOURNAL_CATEGORIES_LIST
)
from .prompts import (
    PUNCTUATION_PROMPT, AUDIO_TRANSCRIPTION_PROMPT, CATEGORIZATION_PROMPT,
    THERAPIST_ANALYSIS_PROMPT, OCR_PROMPT
)
from .database import (
    get_user_profile, update_user_profile,
    add_journal_entry, update_journal_entry, get_journal_entries, update_token_usage,
    get_sentiment_distribution, get_topic_frequency, get_word_count_trends, get_top_topics_overall
)

# --- BASIC SETUP ---
logger = logging.getLogger(__name__)

# --- GLOBAL VARIABLES (initialized in core.py) ---
genai_model = None
safety_settings: list[SafetySettingDict] = []

# --- DYNAMIC PATHS (set during initialization) ---
BASE_DIR = ""
DATA_DIR = ""
TEMP_DIR = ""
VISUALIZATIONS_DIR = ""

# --- TOKEN TRACKING CACHE ---
token_data_cache = {"session": 0} # In-memory cache for session tokens

# --- INITIALIZATION FUNCTIONS (called from core.py) ---
def set_global_paths(base_dir: str):
    """Sets the global data directory paths and ensures they exist."""
    global BASE_DIR, DATA_DIR, TEMP_DIR, VISUALIZATIONS_DIR
    BASE_DIR = base_dir
    DATA_DIR = os.path.join(BASE_DIR, DATA_DIR_NAME)
    TEMP_DIR = os.path.join(DATA_DIR, TEMP_DIR_NAME)
    VISUALIZATIONS_DIR = os.path.join(DATA_DIR, VISUALIZATIONS_DIR_NAME)
    # Ensure directories exist
    for dir_path in [DATA_DIR, TEMP_DIR, VISUALIZATIONS_DIR]:
        os.makedirs(dir_path, exist_ok=True)
    logger.info(f"Data directories ensured: {DATA_DIR}, {TEMP_DIR}, {VISUALIZATIONS_DIR}")

def set_gemini_model(model):
    """Sets the global Gemini model instance."""
    global genai_model
    genai_model = model

def set_safety_settings(settings: list[SafetySettingDict]):
    """Sets the global Gemini safety settings."""
    global safety_settings
    safety_settings = settings

# --- HELPER FUNCTIONS ---

async def load_profiles(user_id: int) -> dict:
    """Loads a single user profile from the database."""
    profile = await get_user_profile(user_id)
    return profile if profile else {}

async def save_profiles(user_id: int, username: str | None = None, is_approved: bool | None = None) -> bool:
    """Saves or updates a user profile in the database."""
    return await update_user_profile(user_id, username, is_approved)

async def initialize_token_data():
    """Initializes token data for a new session, resetting session count."""
    global token_data_cache
    # When the bot starts, reset session token count.
    # Daily and total counts are managed by the database.
    token_data_cache['session'] = 0
    logger.info("Token data initialized for new session.")

async def increment_token_usage(prompt_tokens: int = 0, candidate_tokens: int = 0, user_id: int = 0, feature_used: str | None = None, model_name: str | None = None) -> None:
    """Increments the token usage counts (session, daily, total) in the database."""
    global token_data_cache
    total_increment = prompt_tokens + candidate_tokens

    # Update in-memory session cache
    token_data_cache["session"] = token_data_cache.get("session", 0) + total_increment

    # Log the token usage in the database
    if not await update_token_usage(user_id, prompt_tokens, candidate_tokens, feature_used, model_name):
        logger.error("Failed to save updated token data to DB!")
    
    logger.info(f"Tokens Used - Prompt: {prompt_tokens}, Candidate: {candidate_tokens}, Session: {token_data_cache['session']}")

async def generate_gemini_response(prompt_parts: list, safety_settings_override=None, context: ContextTypes.DEFAULT_TYPE = None) -> tuple[str | None, dict | None]:
    """Sends a prompt to the Gemini model and returns the response and usage metadata."""
    if not genai_model:
        logger.error("Gemini model not initialized.")
        return None, None
    usage_metadata = None
    text_response = None
    try:
        logger.info(f"Sending request to Gemini ({len(prompt_parts)} parts)...")
        response = await genai_model.generate_content_async(prompt_parts, safety_settings=safety_settings_override if safety_settings_override else safety_settings)
        if hasattr(response, 'usage_metadata'):
            usage_metadata = response.usage_metadata
            # Pass user_id, feature_used, model_name to increment_token_usage
            user_id = context.user_data.get('user_id', 0) if context else 0
            feature_used = context.user_data.get('current_mode', 'unknown') if context else 'unknown'
            model_name = genai_model.model_name if genai_model else 'unknown'
            await increment_token_usage(usage_metadata.prompt_token_count, usage_metadata.candidates_token_count, user_id=user_id, feature_used=feature_used, model_name=model_name)
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            block_reason = response.prompt_feedback.block_reason
            logger.warning(f"Gemini request blocked: {block_reason}")
            return f"[BLOCKED: {block_reason}]", usage_metadata
        if hasattr(response, 'text'):
            text_response = response.text
            logger.info(f"Received response from Gemini ({len(text_response) if text_response else 0} chars).")
        elif not (response.prompt_feedback and response.prompt_feedback.block_reason):
            logger.warning("Gemini returned no text content.")
            text_response = "[No text content received]"
        return text_response, usage_metadata
    except (genai_types.BlockedPromptException, genai_types.StopCandidateException) as safety_exception:
        logger.warning(f"Gemini Safety Exception ({type(safety_exception).__name__}): {safety_exception}")
        response_obj = getattr(safety_exception, 'response', None)
        text_response = "[BLOCKED/STOPPED]"
        if response_obj:
             if hasattr(response_obj, 'text'):
                 text_response = response_obj.text + f" [{type(safety_exception).__name__}]"
             if hasattr(response_obj, 'usage_metadata'):
                 usage_metadata = response_obj.usage_metadata
                 # Pass user_id, feature_used, model_name to increment_token_usage
                 user_id = context.user_data.get('user_id', 0) if context else 0
                 feature_used = context.user_data.get('current_mode', 'unknown') if context else 'unknown'
                 model_name = genai_model.model_name if genai_model else 'unknown'
                 await increment_token_usage(usage_metadata.prompt_token_count, usage_metadata.candidates_token_count, user_id=user_id, feature_used=feature_used, model_name=model_name)
        return text_response, usage_metadata
    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}", exc_info=True)
        return f"[API ERROR: {type(e).__name__}]", None

async def add_punctuation_with_gemini(raw_text: str, context: ContextTypes.DEFAULT_TYPE = None) -> str:
    """Uses Gemini to add punctuation and capitalization to raw text."""
    if not raw_text or raw_text.strip() == "": return raw_text
    if not genai_model:
        logger.warning("Gemini unavailable for punctuation.")
        return raw_text
    prompt = PUNCTUATION_PROMPT.format(raw_text=raw_text)
    logger.info("Sending raw transcript to Gemini for punctuation...")
    formatted_text, _ = await generate_gemini_response([prompt], context=context)
    if formatted_text and "[BLOCKED:" not in formatted_text and "[API ERROR:" not in formatted_text and "[No text content received]" not in formatted_text:
        logger.info("Punctuation added successfully.")
        return formatted_text.strip()
    else:
        logger.warning(f"Failed to punctuate: {formatted_text}. Returning raw.")
        return raw_text

async def transcribe_audio_with_gemini(audio_path: str, context: ContextTypes.DEFAULT_TYPE = None) -> str | None:
    """Transcribes audio file directly using Gemini."""
    if not os.path.exists(audio_path):
        logger.error(f"Audio file not found for Gemini transcription: {audio_path}")
        return "[File Not Found Error]"
    if not genai_model:
        logger.error("Gemini model not available for audio transcription.")
        return "[AI Service Unavailable]"
    try:
        logger.info(f"Uploading audio file {os.path.basename(audio_path)} to Gemini...")
        audio_file_obj = genai.upload_file(path=audio_path)
        logger.info(f"Completed uploading '{audio_file_obj.display_name}'.")
        prompt = AUDIO_TRANSCRIPTION_PROMPT
        logger.info("Sending audio transcription request to Gemini...")
        response = await genai_model.generate_content_async([prompt, audio_file_obj])
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            block_reason = response.prompt_feedback.block_reason
            logger.warning(f"Gemini audio transcription blocked: {block_reason}")
            return f"[BLOCKED: {block_reason}]"
        if hasattr(response, 'text'):
            raw_text = response.text.strip()
            logger.info(f"Gemini raw transcription successful ({len(raw_text)} chars).")
            try:
                genai.delete_file(audio_file_obj.name)
                logger.info(f"Deleted uploaded file '{audio_file_obj.name}' from Gemini.")
            except Exception as del_e:
                logger.warning(f"Could not delete uploaded audio file {audio_file_obj.name} from Gemini: {del_e}")
            return raw_text
        else:
            logger.warning("Gemini audio transcription returned no text content.")
            return "[No transcription content]"
    except Exception as e:
        logger.error(f"Error during Gemini audio transcription: {e}", exc_info=True)
        return f"[AI Transcription Error: {type(e).__name__}]"

async def generate_mind_map_image(dot_string: str, user_id: int, is_historical: bool = False) -> str | None:
    """
    Generates a high-quality mind map image from a DOT string.
    Renders at a high DPI and then resizes for clarity.
    """
    if not dot_string or "digraph" not in dot_string.lower():
        logger.warning(f"Invalid DOT string for user {user_id}.")
        return None

    # Add a high DPI attribute to the graph for a high-resolution render.
    # This is a minimal injection that improves quality without overriding style.
    if 'dpi=' not in dot_string.lower():
        insert_pos = dot_string.find('{') + 1
        dpi_attr = 'graph [dpi="300"];'
        dot_string = dot_string[:insert_pos] + dpi_attr + dot_string[insert_pos:]

    file_suffix = "history_map" if is_historical else "jmap"
    output_base_path = os.path.join(VISUALIZATIONS_DIR, f"{user_id}_{file_suffix}_{datetime.now().strftime('%Y%m%d%H%M%S')}")
    temp_png_path = output_base_path + "_temp.png"
    final_png_path = output_base_path + ".png"

    try:
        logger.info(f"Generating high-quality mind map for user {user_id}")
        
        s = graphviz.Source(dot_string, engine='dot')
        
        loop = asyncio.get_running_loop()
        def _render_sync():
            return s.render(temp_png_path, format='png', cleanup=False)

        rendered_temp_path = await loop.run_in_executor(None, _render_sync)

        if not rendered_temp_path or not os.path.exists(rendered_temp_path):
            logger.error(f"Graphviz render failed or temp file not found: {rendered_temp_path}.")
            return None

        # Resize with Pillow/PIL for a crisp final image
        with PIL.Image.open(rendered_temp_path) as img:
            # Resize to a clear but Telegram-friendly size, maintaining aspect ratio
            img.thumbnail((1280, 1280), PIL.Image.LANCZOS)
            img.save(final_png_path, "PNG", optimize=True)
        
        logger.info(f"Mind map PNG generated and resized: {final_png_path}")
        return final_png_path

    except graphviz.backend.execute.ExecutableNotFound:
        logger.error("Graphviz executable not found.")
        return None
    except Exception as e:
        logger.error(f"Error generating mind map image: {e}", exc_info=True)
        return None
    finally:
        # Clean up the large temporary file
        if os.path.exists(temp_png_path):
            os.remove(temp_png_path)

# --- ANALYTICS AND VISUALIZATION FUNCTIONS ---

async def generate_sentiment_pie_chart(user_id: int, period_days: int = 7) -> str | None:
    """Generates a pie chart for sentiment distribution."""
    sentiment_data = await get_sentiment_distribution(user_id, period_days)
    if not sentiment_data:
        return None

    dot = graphviz.Digraph(comment=f'Sentiment Analysis for User {user_id}')
    dot.attr('node', shape='plaintext')

    total_entries = sum(count for _, count in sentiment_data)
    
    # Define colors for sentiments
    sentiment_colors = {
        'positive': '#4CAF50', # Green
        'negative': '#F44336', # Red
        'neutral': '#9E9E9E',  # Grey
        'mixed': '#FFC107'     # Amber
    }

    # Create a single node with a pie chart
    label_html = f"""<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0">
<TR><TD COLSPAN="2"><B>Sentiment Last {period_days} Days</B></TD></TR>
"""

    for sentiment, count in sentiment_data:
        percentage = (count / total_entries) * 100
        color = sentiment_colors.get(sentiment.lower(), '#FFFFFF')
        label_html += f"""<TR><TD BGCOLOR="{color}">{sentiment.capitalize()}</TD><TD>{percentage:.1f}%</TD></TR>
"""
    
    label_html += "</TABLE>>"
    dot.node('sentiment_pie', label=label_html)

    output_path = os.path.join(VISUALIZATIONS_DIR, f"{user_id}_sentiment_pie_{datetime.now().strftime('%Y%m%d%H%M%S')}")
    try:
        s = graphviz.Source(dot.source, filename=output_path, format="png")
        loop = asyncio.get_running_loop()
        rendered_path = await loop.run_in_executor(None, s.render, None, VISUALIZATIONS_DIR, False, True)
        return rendered_path
    except Exception as e:
        logger.error(f"Error generating sentiment pie chart: {e}", exc_info=True)
        return None

async def generate_word_count_trend_chart(user_id: int, period_days: int = 7) -> str | None:
    """Generates a line chart for word count trends."""
    word_count_data = await get_word_count_trends(user_id, period_days)
    if not word_count_data:
        return None

    dot = graphviz.Digraph(comment=f'Word Count Trend for User {user_id}')
    dot.attr(rankdir='LR', splines='line')
    dot.attr('node', shape='point')

    # Create nodes for each day
    for i, (date, count) in enumerate(word_count_data):
        dot.node(str(i), label=f'{date}\n{count}')

    # Create edges to form the line chart
    for i in range(len(word_count_data) - 1):
        dot.edge(str(i), str(i+1))

    output_path = os.path.join(VISUALIZATIONS_DIR, f"{user_id}_word_trend_{datetime.now().strftime('%Y%m%d%H%M%S')}")
    try:
        s = graphviz.Source(dot.source, filename=output_path, format="png")
        loop = asyncio.get_running_loop()
        rendered_path = await loop.run_in_executor(None, s.render, None, VISUALIZATIONS_DIR, False, True)
        return rendered_path
    except Exception as e:
        logger.error(f"Error generating word count trend chart: {e}", exc_info=True)
        return None

async def get_analytics_summary(user_id: int, period_days: int = 7, context: ContextTypes.DEFAULT_TYPE = None) -> str:
    """Generates a text summary of user analytics."""
    sentiment_data = await get_sentiment_distribution(user_id, period_days)
    topic_data = await get_topic_frequency(user_id, period_days)
    word_count_data = await get_word_count_trends(user_id, period_days)

    if not sentiment_data and not topic_data and not word_count_data:
        return "Not enough data available for analysis. Keep journaling to see your trends!"

    prompt = "Analyze the following user journal data and provide a brief, insightful summary.\n\n"
    if sentiment_data:
        prompt += f"Sentiment Distribution: {json.dumps(dict(sentiment_data))}\n"
    if topic_data:
        prompt += f"Top Topics: {json.dumps(dict(topic_data[:5]))}\n" # Top 5 topics
    if word_count_data:
        prompt += f"Word Count Trend: {json.dumps(dict(word_count_data))}\n"

    summary, _ = await generate_gemini_response([prompt], context=context)
    return summary if summary else "Could not generate a summary at this time."

async def generate_historical_mind_map(user_id: int) -> str | None:
    """Generates an 'Evolving Timeline' mind map for the last 3 months with a clear linear flow."""
    three_months_ago = datetime.now() - timedelta(days=90)
    entries = await get_journal_entries(user_id=user_id)
    if not entries:
        return None

    # Filter for the last 3 months and sort chronologically
    recent_entries = [e for e in entries if datetime.strptime(e['created_at'], "%Y-%m-%d %H:%M:%S") > three_months_ago]
    if not recent_entries:
        return None
    recent_entries.sort(key=lambda x: datetime.strptime(x['created_at'], "%Y-%m-%d %H:%M:%S"))

    # Group entries by month and then by week
    monthly_summaries = {}
    for entry in recent_entries:
        entry_date = datetime.strptime(entry['created_at'], "%Y-%m-%d %H:%M:%S")
        month_year = entry_date.strftime("%B %Y")
        week_num = (entry_date.day - 1) // 7 + 1

        if month_year not in monthly_summaries:
            monthly_summaries[month_year] = {'weeks': {}}
        
        if week_num not in monthly_summaries[month_year]['weeks']:
            monthly_summaries[month_year]['weeks'][week_num] = {'sentiments': [], 'topics': [], 'entry_count': 0}

        monthly_summaries[month_year]['weeks'][week_num]['entry_count'] += 1

        if entry.get('Sentiment'):
            monthly_summaries[month_year]['weeks'][week_num]['sentiments'].append(entry['Sentiment'])
        if entry.get('Topics'):
            topics_data = entry['Topics']
            if isinstance(topics_data, str):
                try:
                    topics_list = json.loads(topics_data)
                    monthly_summaries[month_year]['weeks'][week_num]['topics'].extend(topics_list)
                except json.JSONDecodeError:
                    # Fallback for plain string topics if not valid JSON
                    monthly_summaries[month_year]['weeks'][week_num]['topics'].extend([t.strip() for t in topics_data.split(',')])
            elif isinstance(topics_data, list):
                # If it's already a list, just extend
                monthly_summaries[month_year]['weeks'][week_num]['topics'].extend(topics_data)


    # --- Create the Graph ---
    dot = graphviz.Digraph(comment=f'Evolving Timeline for User {user_id}')
    dot.attr(rankdir='TB', splines='ortho', nodesep='0.5', ranksep='1.2') # Top-to-Bottom, clean lines

    # --- Create and Connect Nodes ---
    month_start_nodes = []

    sorted_months = sorted(monthly_summaries.items(), key=lambda item: datetime.strptime(item[0], "%B %Y"))

    for month_year, month_data in sorted_months:
        # Create a cluster for each month to group its weeks
        with dot.subgraph(name=f'cluster_{month_year.replace(" ", "")}') as c:
            c.attr(style='invis')
            
            weekly_nodes_in_month = []
            sorted_weeks = sorted(month_data['weeks'].items())

            for week_num, week_data in sorted_weeks:
                week_sent_counts = {s: week_data['sentiments'].count(s) for s in set(week_data['sentiments'])}
                dom_week_sent = max(week_sent_counts, key=week_sent_counts.get) if week_sent_counts else "Neutral"
                
                topic_counts = {t: week_data['topics'].count(t) for t in set(week_data['topics'])}
                top_topics = sorted(topic_counts, key=topic_counts.get, reverse=True)[:2] if topic_counts else ["No Topics"]
                entries_in_week = len(week_data['sentiments']) # This is the count of entries for the week

                week_color = {'Positive': '#A8D8B9', 'Negative': '#F8BABA', 'Neutral': '#B9D4E4', 'Mixed': '#FDFD96'}.get(dom_week_sent, '#E0E0E0')
                
                # Using HTML-like labels for better formatting
                topics_str = "<BR/>".join(top_topics)
                week_label = f"""<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="4" BGCOLOR="{week_color}">
<TR><TD COLSPAN="2"><B>Week {week_num}</B><BR/>({month_year.split()[0]})</TD></TR>
<TR><TD ALIGN="LEFT"><B>Sentiment:</B> {dom_week_sent}</TD></TR>
<TR><TD ALIGN="LEFT"><B>Entries:</B> {entries_in_week}</TD></TR>
<TR><TD ALIGN="LEFT"><B>Top Topics:</B><BR/>{topics_str}</TD></TR>
</TABLE>>"""

                node_name = f'{month_year.replace(" ", "")}_W{week_num}'
                c.node(node_name, label=week_label, shape='plaintext', fontsize='24') # Further increased fontsize for better readability
                weekly_nodes_in_month.append(node_name)
            
            # Create invisible edges to align weeks horizontally
            if len(weekly_nodes_in_month) > 1:
                for i in range(len(weekly_nodes_in_month) - 1):
                    dot.edge(weekly_nodes_in_month[i], weekly_nodes_in_month[i+1], style='invis')
            
            if weekly_nodes_in_month:
                month_start_nodes.append(weekly_nodes_in_month[0])

    # Connect the first week of each month to the first week of the next month
    if len(month_start_nodes) > 1:
        for i in range(len(month_start_nodes) - 1):
            dot.edge(month_start_nodes[i], month_start_nodes[i+1], arrowhead='normal', color='#FFFFFF', style='solid', penwidth='2')

    # Generate the image using the main generation function
    return await generate_mind_map_image(dot.source, user_id, is_historical=True)