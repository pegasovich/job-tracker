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

# Hybrid exception — allow hybrid jobs if their location matches
# any of these patterns (case-insensitive substring match).
# Cahersiveen (V23 DP40), County Kerry and nearby areas.
HYBRID_ALLOWED_LOCATIONS = [
    "kerry",
    "cahersiveen",
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
