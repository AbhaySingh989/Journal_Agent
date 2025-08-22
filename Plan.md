# Journal Agent Refactoring and Enhancement Plan

This document outlines the step-by-step plan to refactor the Telegram Journal Bot for better stability, scalability, and functionality, with a specific focus on reliable deployment on the PythonAnywhere free tier.

---

### **Guiding Principles & Workflow**

*   **Iterative Approval:** After each step (product increment), the bot will be in a runnable state for you to test. Your explicit sign-off is required before moving to the next step.
*   **Incremental Planning:** Before starting work on a new step, I will present the detailed plan for that specific increment and get your approval.
*   **Readable Code:** I will add detailed comments throughout the code to explain the logic and make it easy to understand.
*   **PythonAnywhere Focus:** All architectural decisions will be made with the constraints and best practices of the PythonAnywhere free tier in mind.
*   **Scalable Design:** All refactoring will be done with a focus on creating a scalable structure that is easy to extend in the future.
*   **Continuous Documentation:** The `README.md` and `Product_Architecture.md` files will be updated after each product increment is approved to reflect the current state of the project.
*   **Track Progress in Plan:** After you approve the completion of a step, I will update this `Plan.md` file to mark the step as complete before presenting the plan for the next increment.
*   **Adhere to Workflow:** Always refer to the "Agreed Workflow" section below for the process of each iteration.

---

### **Agreed Workflow for Iterations**

To ensure a structured and transparent development process, we will follow these steps for each product increment:

1.  **Present Plan for Next Increment:** I will present a detailed plan for the upcoming step (product increment), outlining objectives, actions, and affected files.
2.  **User Approval of Plan:** You will review the presented plan and provide your explicit approval to proceed.
3.  **Execute Increment:** I will then implement the changes as per the approved plan.
4.  **User Testing & Sign-off:** After implementation, you will test the bot to ensure the changes are working correctly and provide your explicit sign-off on the *execution* of the step.
5.  **Update Documentation & Mark Completion:** Upon your sign-off, I will perform the following actions before starting the next iteration:
    *   Update this `Plan.md` file to mark the completed step as "Completed".
    *   Update the `README.md` with the latest development log.
    *   Update the `Product_Architecture.md` to reflect any architectural changes. (Note: This file will be created during its first required update and maintained thereafter).
6.  **Repeat:** We will then proceed to Step 1 for the next product increment.

---

### **Phase 1: Core Architectural Rework (For Stability & Scalability)**

*   **Step 1: Convert to a Webhook-based Application**
    *   **Status:** Completed
    *   **Action:** Introduce the `Flask` library to create a simple web server. The bot will no longer use `run_polling()`. Instead, it will be set up as a web app that Telegram sends messages to.
    *   **Reason:** This is the standard, most reliable way to run a bot on the PythonAnywhere free tier, ensuring it doesn't get shut down.
    *   **Files Affected:** `requirements.txt` (add Flask), create `app.py` (the new main file), modify `multimode_bot_final.py`.

*   **Step 2: Restructure the Project into Modules**
    *   **Status:** Completed
    *   **Action:** Break the single, large `multimode_bot_final.py` file into a logical directory structure.
        *   `main.py`: The new entry point, containing the Flask app.
        *   `bot/`: A new directory for all bot-related code.
            *   `__init__.py`: To make it a Python package.
            *   `core.py`: To set up the Telegram `Application` object.
            *   `handlers.py`: For all command and message handlers (e.g., `start_command`, `handle_journal_logic`).
            *   `utils.py`: For helper functions (e.g., Gemini API calls, file handling).
            *   `constants.py`: To store all constants.
            *   `prompts.py`: To store all prompts sent to the AI.
    *   **Reason:** This makes the code much easier to read, maintain, and add new features to without breaking existing ones.
    *   **Files Affected:** `multimode_bot_final.py` will be deleted and its contents distributed into the new files.

---

### **Phase 2: Data Layer Upgrade (For Performance & Reliability)**

*   **Step 3: Migrate All Data from Flat Files to SQLite Database**
    *   **Status:** Completed
    *   **Action:** Consolidate `journal.csv`, `user_profiles.json`, and `token_usage.json` into a single SQLite database. A new file, `bot/database.py`, will manage all database interactions (creating tables, adding/reading entries).
    *   **Reason:** SQLite is a file-based database that is fully supported on PythonAnywhere. It's significantly faster, safer (prevents data corruption), and more scalable than managing separate CSV and JSON files.
    *   **Files Affected:** Create `bot/database.py`, modify `bot/handlers.py` and `bot/utils.py` to use the new database functions. The `.csv` and `.json` data files will become obsolete.

*   **Step 4: Create a Data Migration Script**
    *   **Status:** Completed
    *   **Action:** Write a simple, one-time-use script (`migrate.py`) that you can run to transfer all your existing data from the old `journal.csv`, `user_profiles.json`, and `token_usage.json` files into the new SQLite database.
    *   **Reason:** This ensures you don't lose any of your historical data during the upgrade.
    *   **Files Affected:** Create `migrate.py`.

---

### **Phase 3: Feature Enhancements**

*   **Step 5: Implement Journal Search Functionality**
    *   **Status:** Completed
    *   **Action:** Add a new `/search <keyword>` command. This will allow you to search your entire journal history for specific words or phrases.
    *   **Reason:** This is a highly requested feature for any journaling application and is made easy by the new SQLite database.
    *   **Files Affected:** `bot/handlers.py` (new command handler), `bot/database.py` (new search function).

*   **Step 6: Implement Journal Export**
    *   **Status:** Completed
    *   **Action:** Add a new `/export` command that gathers all of a user's journal entries and sends them back as a single, downloadable `.txt` file.
    *   **Reason:** Gives users control over their data and allows for easy backups.
    *   **Files Affected:** `bot/handlers.py`, `bot/database.py`.

---

### **Phase 4: Quality and Deployment**

*   **Step 7: Introduce Automated Testing**
    *   **Status:** Completed
    *   **Action:** Set up the `pytest` framework and create a `tests/` directory. Write initial tests for critical, non-Telegram parts of the code, like database and utility functions.
    *   **Reason:** Automated tests act as a safety net, ensuring that future changes don't accidentally break existing functionality. This is a best practice for any serious project.
    *   **Files Affected:** Create `requirements-dev.txt`, create `tests/` directory with test files.

---

### **Phase 5: Feature Enhancements (New 07/05/2025)**

*   **Step 8: Implement Enhanced Journaling Analytics & Visualizations**
    *   **Status:** Not Started
    *   **Objective:** Provide users with deeper insights into their journaling patterns, sentiment trends, and recurring themes over time, presented with simple visualizations.
    *   **Actions:**
        *   **Database Queries:** Add new functions to `bot/database.py` to efficiently query journal entries for:
            *   Sentiment distribution over specified periods (e.g., daily, weekly, monthly).
            *   Frequency of specific topics and categories.
            *   Word count trends.
        *   **Data Processing & Visualization:** Develop functions in `bot/utils.py` to:
            *   Process the queried data into meaningful summaries.
            *   Generate simple text-based charts (e.g., bar charts using ASCII characters) or basic image-based visualizations (e.g., using `graphviz` for simple trend lines or pie charts, or exploring `matplotlib` if simple text/graphviz is insufficient and approved).
            *   Leverage the LLM (via `generate_gemini_response`) to provide narrative interpretations of the trends and insights.
        *   **Command Handlers:** Implement new command handlers in `bot/handlers.py` (e.g., `/analytics`, `/trends`) to allow users to request these insights.
    *   **Files Affected:** `bot/database.py`, `bot/utils.py`, `bot/handlers.py`, `bot/prompts.py` (for new analysis prompts), `requirements.txt` (if new visualization libraries are added).

*   **Step 9: Implement LLM-Driven Goal Setting & Progress Tracking - Database & Core Logic**
    *   **Status:** Not Started
    *   **Objective:** Establish the foundational database structure and core AI logic for intelligent goal suggestion and automated progress tracking.
    *   **Actions:**
        *   **Database Schema:** Update `bot/database.py` (`initialize_db` function) to create two new tables:
            *   `Goals`: `goal_id` (PK), `user_id` (FK), `goal_name` (TEXT), `description` (TEXT), `target_metric` (TEXT, e.g., "km", "books", "hours"), `target_value` (REAL/INTEGER), `current_value` (REAL/INTEGER), `start_date` (TEXT), `end_date` (TEXT), `status` (TEXT: 'active', 'completed', 'archived'), `tags` (JSON string), `created_at` (TIMESTAMP).
            *   `GoalProgress`: `progress_id` (PK), `goal_id` (FK), `logged_at` (TIMESTAMP), `progress_value` (REAL/INTEGER), `notes` (TEXT), `associated_entry_id` (FK to `JournalEntries.entry_id`).
        *   **Database CRUD:** Add new asynchronous CRUD (Create, Read, Update, Delete) functions to `bot/database.py` for the `Goals` and `GoalProgress` tables.
        *   **LLM Goal Inference:** Develop functions in `bot/utils.py` that utilize the Gemini LLM to:
            *   Analyze new journal entries for implicit goal suggestions (e.g., identifying recurring desires or future plans).
            *   Formulate prompts for the LLM to infer progress towards active goals from journal entry content, attempting to quantify progress based on `target_metric`.
        *   **Integration:** Integrate the LLM goal suggestion and progress inference into the `handle_journal_logic` in `bot/handlers.py` to run after a journal entry is processed.
    *   **Files Affected:** `bot/database.py`, `bot/utils.py`, `bot/handlers.py`, `bot/prompts.py` (for new goal-related prompts).

*   **Step 10: Implement LLM-Driven Goal Setting & Progress Tracking - User Commands & Summaries**
    *   **Status:** Not Started
    *   **Objective:** Provide user-facing commands for managing goals and viewing intelligent, narrative summaries of their progress.
    *   **Actions:**
        *   **Command Handlers:** Implement new command handlers in `bot/handlers.py` for:
            *   `/setgoal`: Guides the user through setting a new goal, potentially leveraging LLM suggestions from Step 11.
            *   `/mygoals`: Displays a list of active goals and provides LLM-generated narrative summaries of progress for each.
            *   `/updategoal`: Allows for manual progress updates, or confirms LLM-inferred updates.
            *   `/completegoal`: Marks a goal as completed.
            *   `/archivegoal`: Archives a goal.
        *   **LLM Summarization:** Develop functions in `bot/utils.py` that use the Gemini LLM to:
            *   Generate comprehensive, narrative summaries of a user's progress on a specific goal, drawing insights from `GoalProgress` entries and linked `JournalEntries`.
            *   Provide motivational insights or suggestions for next steps based on the analysis.
    *   **Files Affected:** `bot/handlers.py`, `bot/utils.py`, `bot/prompts.py`.