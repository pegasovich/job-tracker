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
ALLOW_HYBRID = False  # Global hybrid: False = block by default, allowed only for nearby locations

# Allowed locations for hybrid roles (reasonable commute from Cahersiveen, Co. Kerry)
HYBRID_ALLOWED_LOCATIONS = [
    "kerry",
    "county kerry",
    "co. kerry",
    "co kerry",
    "caherciveen",
    "cahirciveen",
    "cahirsiveen",
    "killarney",
    "tralee",
    "kenmare",
    "killorglin",
    "dingle",
    "listowel",
    "iveragh",
    "ring of kerry",
    "cork",          # ~2h drive, still reasonable for hybrid
]

# Target keywords to monitor for QA/SDET (Manual & Automation)
SEARCH_KEYWORDS = [
    "QA Engineer",
    "SDET",
    "Automation QA",
    "Test Automation",
    "Manual QA",
    "QA Tester",
    "Software Tester",
]

# Djinni.co Settings (Официальные категории Djinni для QA)
ENABLE_DJINNI = True
DJINNI_KEYWORDS = [
    "QA Automation",
    "QA Manual",
]
DJINNI_MAX_PAGES = 5
DJINNI_LIMIT = 60

# Database file
DATABASE_FILE = str(Path(__file__).parent / "jobs_seen.db")

# Fetch full description snippet for Telegram message
FETCH_SNIPPETS = True
