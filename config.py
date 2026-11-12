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

# LinkedIn Search Time & Sort Settings
LINKEDIN_TIME_FILTER = "r86400"  # r86400 = Past 24 hours, None = All time
LINKEDIN_SORT_BY = "DD"          # DD = Most recent (date descending), None = Most relevant

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
]

# Target keywords to monitor for QA/SDET (Manual & Automation)
# Boolean targeted B2B/Contract queries + standard role titles
SEARCH_KEYWORDS = [
    '("SDET" OR "QA Automation") AND ("Contract" OR "B2B" OR "Deel")',
    '("QA Engineer" OR "Software Tester") AND ("Contract" OR "B2B" OR "Deel")',
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
# Djinni Country Filter (кандидат в Ирландии)
DJINNI_COUNTRY_FILTER = True
DJINNI_USER_COUNTRIES = ["IE", "IRL", "IRELAND"]
DJINNI_USER_REGIONS = ["EUROPE", "EU", "WORLDWIDE", "ANY", "ALL"]

# Database file
DATABASE_FILE = str(Path(__file__).parent / "jobs_seen.db")

# Fetch full description snippet for Telegram message
FETCH_SNIPPETS = True
