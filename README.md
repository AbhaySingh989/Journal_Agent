# Multimode Telegram Bot

This is a sophisticated, multi-functional Telegram bot designed to serve as a personal assistant. It can handle text, voice, and image inputs, and it offers a wide range of features, including real-time conversation, journaling, data visualization, and user profile management.

## Features

- **Multi-modal Communication:** Interact with the bot using text, voice messages, or images.
- **Journaling:** Keep a personal journal. The bot can store, retrieve, and analyze your journal entries.
- **Data Visualization:** Generate mind maps of your journal data using `graphviz`.
- **User Profiles:** The bot maintains user profiles to provide a personalized experience.
- **Token Usage Tracking:** Monitors and logs the token usage for the generative AI models.
- **Access Control:** A system for approving new users, managed by an administrator.
- **Error Handling:** Robust error handling to ensure a smooth user experience.

## Project Structure

```
.
├── .env
├── app.py
├── requirements.txt
├── bot_data/
│   ├── temp/
│   └── visualizations/
│   └── bot_data.db
├── bot/
│   ├── __init__.py
│   ├── core.py
│   ├── handlers.py
│   ├── utils.py
│   ├── constants.py
│   ├── prompts.py
│   └── database.py
└── venv/
```

- **`.env`**: Stores environment variables, including API keys and webhook URL.
- **`app.py`**: The Flask application that serves as the webhook endpoint for Telegram.
- **`requirements.txt`**: A list of the Python packages required for the project.
- **`bot_data/`**: A directory containing the bot's data.
  - **`temp/`**: A temporary directory for storing files during processing.
  - **`visualizations/`**: Stores the generated data visualizations.
  - **`bot_data.db`**: The SQLite database file that stores all bot data.
- **`bot/`**: Contains the core logic of the Telegram bot, broken down into modules:
  - **`__init__.py`**: Makes `bot/` a Python package.
  - **`core.py`**: Main bot setup, application builder, and webhook configuration.
  - **`handlers.py`**: All Telegram command and message handler functions.
  - **`utils.py`**: Helper functions for AI interactions and file operations (now uses `database.py` for data persistence).
  - **`constants.py`**: Global constants and configuration values.
  - **`prompts.py`**: Centralized storage for all AI prompts.
  - **`database.py`**: Manages all interactions with the SQLite database.
- **`venv/`**: The Python virtual environment.

## Getting Started

### Prerequisites

- Python 3.7+
- A Telegram Bot Token
- A Google API Key for Generative AI
- `graphviz` (system-wide installation)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Abhay-2004/Journal-Agent.git
    cd Journal-Agent
    ```

2.  **Install `graphviz`:**
    - **Windows:** `choco install graphviz`
    - **macOS:** `brew install graphviz`
    - **Linux (Debian/Ubuntu):** `sudo apt-get install graphviz`

3.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

4.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Set up your environment variables:**
    Create a `.env` file in the root directory of the project and add your API keys and the webhook URL. For local testing, you'll use `ngrok` to get an `https` URL.
    ```
    TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
    GEMINI_API_KEY="your_google_api_key"
    WEBHOOK_URL="your_webhook_url_from_ngrok_or_pythonanywhere"
    ```

### Running the Bot (Local Development with ngrok)

1.  **Start ngrok:**
    Open a terminal and run ngrok to expose your local Flask server to the internet. This will provide you with an `https` URL.
    ```bash
    ngrok http 5000
    ```
    Copy the `https` forwarding URL (e.g., `https://xxxx-xxxx-xxxx-xxxx.ngrok-free.app`).

2.  **Update `.env`:**
    Paste the copied `ngrok` URL into your `.env` file as the `WEBHOOK_URL`.

3.  **Run the Flask application:**
    Open a *separate* terminal, activate your virtual environment, and run the Flask app. This will set the webhook with Telegram using the `ngrok` URL.
    ```bash
    set FLASK_APP=app.py  # For Windows Command Prompt
    # $env:FLASK_APP = "app.py" # For PowerShell
    python -m flask run
    ```
    Your bot should now be live and accessible via Telegram.

### Running the Bot (PythonAnywhere Deployment)

Deploying on PythonAnywhere's free tier is a great way to keep your bot running 24/7. This guide will walk you through the process step-by-step.

**Prerequisites:**
*   A free [PythonAnywhere](https://www.pythonanywhere.com/) account.
*   Your code pushed to a GitHub repository.

**Step 1: Get Your Code on PythonAnywhere**

1.  Log in to your PythonAnywhere account.
2.  Open a **Bash Console** from your Dashboard.
3.  In the console, clone your GitHub repository. Replace `<your-github-repo-url>` with your actual repository URL.
    ```bash
    git clone <your-github-repo-url>
    ```
4.  This will create a directory with your project's name. Navigate into it:
    ```bash
    cd your-project-name
    ```
    *(Note: Your project name is likely `Journal-Agent`)*

**Step 2: Set Up the Virtual Environment**

1.  Still in the Bash console, navigate into your project directory:
    ```bash
    cd ~/Journal-Agent
    ```
2.  Create a virtual environment *inside* this directory using the specific Python version you need. This is more reliable than the global `mkvirtualenv` command.
    ```bash
    python3.11 -m venv venv
    ```
3.  Activate the new virtual environment:
    ```bash
    source venv/bin/activate
    ```
    *(Your command prompt should now start with `(venv)`)*

4.  Install all the required packages from your `requirements.txt` file:
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: `graphviz` is pre-installed on PythonAnywhere, so you don't need to install it at the system level.)*

**Step 3: Configure the Web App**

1.  Go to the **Web** tab from the top menu in PythonAnywhere.
2.  Click **"Add a new web app"**.
3.  Your web app domain will be `your-username.pythonanywhere.com`. Click **Next**.
4.  Select the **Flask** framework.
5.  Select the **Python version** you used for the virtual environment (e.g., Python 3.11).
6.  PythonAnywhere will create a basic Flask app for you. We now need to configure it to use *our* app.

**Step 4: Point to Your Code (WSGI Configuration)**

1.  On the **Web** tab, scroll down to the "Code" section.
2.  Click on the **WSGI configuration file** link (it will look something like `/var/www/your-username_pythonanywhere_com_wsgi.py`).
3.  **Delete all the content** in this file.
4.  Replace it with the following code, which tells PythonAnywhere how to find and run your Flask app (`app.py`).

    *   **Important:** Replace `your-username` and `your-project-name` with your actual PythonAnywhere username and the name of the folder you cloned from GitHub.

    ```python
    import sys
    import os

    # Add your project's directory to the Python path
    path = '/home/your-username/your-project-name'
    if path not in sys.path:
        sys.path.insert(0, path)

    # Set the FLASK_APP environment variable
    os.environ['FLASK_APP'] = 'app.py'

    # Import the Flask app instance
    from app import app as application
    ```
5.  **Save** the file.

**Step 5: Set Environment Variables (Crucial for Secrets!)**

1.  Go back to the **Web** tab.
2.  Scroll down to the **"Virtualenv"** section and ensure your virtual environment name (`my-bot-venv`) is entered.
3.  **Option A: Using the Environment Variables section (Preferred if available)**
    *   Scroll down to the **"Code"** section again. Look for the **"Environment variables"** subsection.
    *   Add your secrets there:
        *   `TELEGRAM_BOT_TOKEN` = `your_telegram_bot_token`
        *   `GEMINI_API_KEY` = `your_google_api_key`
        *   `WEBHOOK_URL` = `https://your-username.pythonanywhere.com/webhook`
4.  **Option B: Adding to WSGI file (If Environment Variables section is missing)**
    *   If you don't see the "Environment variables" section, you can add them directly to your WSGI configuration file.
    *   Go back to the **WSGI configuration file** (from Step 4).
    *   Add the following lines *after* the `os.environ['FLASK_APP'] = 'app.py'` line, replacing the placeholder values:
        ```python
        os.environ['TELEGRAM_BOT_TOKEN'] = 'your_telegram_bot_token'
        os.environ['GEMINI_API_KEY'] = 'your_google_api_key'
        os.environ['WEBHOOK_URL'] = 'https://your-username.pythonanywhere.com/webhook'
        ```
5.  **Important:** The `WEBHOOK_URL` must be the full URL of your web app, ending in `/webhook`.

**Step 6: Set the Telegram Webhook**

Your bot code automatically tries to set the webhook when it starts. All you need to do is load the web app.

1.  Go to the top of the **Web** tab.
2.  Click the big green **Reload** button to apply all your changes.
3.  Go to the **"Log files"** section and check your **"Error log"** and **"Server log"**. Look for any error messages. If you see a message indicating the webhook was set successfully, you're good to go!

**Step 7: Test Your Bot!**

Open Telegram and send the `/start` command to your bot. It should now be running live from your PythonAnywhere web app.

## Usage

Upon starting the bot, you will be presented with a choice of modes: Chatbot, Journal, or OCR. Select a mode to begin interacting with the bot.

### User Commands

-   `/start`: Start the conversation with the bot.
-   `/mode` or `/changemode`: Re-select the mode (Chatbot, Journal, or OCR).
-   `/setusername <name>`: Set your display name.
-   `/tokens`: Check your AI token usage.
-   `/search`: Search your journal entries.
-   `/export`: Export all your journal entries.
-   `/end`: End the current session.
-   `/help`: Show the help message.
-   `/cancel`: Cancel the current action and return to the mode selection.

### Admin Commands

-   `/approve <UserID>`: Approve a new user to use the bot. (Note: `ADMIN_USER_ID` is currently hardcoded in `bot/core.py` and will be moved to configuration in a later step).

## Running Tests

To run the automated tests, first install the development dependencies:

```bash
pip install -r requirements-dev.txt
```

Then, run `pytest` from the project root directory:

```bash
pytest
```

## Contributing

Contributions are welcome! If you have any ideas, suggestions, or bug reports, please open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.