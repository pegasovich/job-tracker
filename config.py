"""
Configuration settings for Ireland Remote QA/SDET Job Tracker.
"""

import os
from pathlib import Path

# Load from .env if present
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=env_path)
    except ImportError:
        pass

# Telegram configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Target Search Settings (Широкий поиск по всем доступным регионам)
TARGET_LOCATIONS = [
    "Ireland",
    "United Kingdom",
    "Europe",
    "Worldwide",
]
REMOTE_ONLY = True  # LinkedIn filter f_WT=2

# Strict Remote Filters
ALLOW_ONSITE = False
ALLOW_HYBRID = True  # Allows hybrid if mentioned; False = 100% remote only

# Target keywords to monitor for QA/SDET
SEARCH_KEYWORDS = [
    "QA Engineer",
    "SDET",
    "Automation QA",
    "Test Automation",
]

# Djinni.co Settings
ENABLE_DJINNI = True
DJINNI_KEYWORDS = [
    "QA Automation",
    "SDET",
    "QA Manual",
]

# Database file
DATABASE_FILE = str(Path(__file__).parent / "jobs_seen.db")

# Fetch full description snippet for Telegram message
FETCH_SNIPPETS = True
