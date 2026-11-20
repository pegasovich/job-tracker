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

# Geo & Region Filters for LinkedIn (кандидат в Ирландии / ЕС)
ENABLE_LINKEDIN_GEO_FILTER = True

# Disallowed countries/regions in job location (e.g. Argentina, Brazil, India, USA)
# Even if marked "Remote", these are domestic remote roles for local residents
LINKEDIN_BLOCKED_LOCATIONS = [
    # Latin America
    "argentina", "brazil", "brasil", "colombia", "mexico", "chile", "peru",
    "uruguay", "paraguay", "venezuela", "ecuador", "bolivia", "costa rica",
    "panama", "guatemala", "el salvador", "honduras", "nicaragua",
    "latam", "latin america", "south america",
    # North America (domestic US/Canada roles)
    "united states", r"\busa\b", r"\bu\.s\.a?\b", "canada",
    # Asia & Pacific
    "india", "pakistan", "bangladesh", "philippines", "vietnam", "indonesia",
    "malaysia", "singapore", "thailand", "china", "japan", "korea", "taiwan",
    "sri lanka", "nepal", "australia", "new zealand", "apac",
    # Africa
    "nigeria", "kenya", "south africa", "egypt", "ghana", "morocco", "uganda",
    # Middle East
    r"\buae\b", "united arab emirates", "dubai", "saudi arabia", "qatar", "israel", "turkey", "türkiye",
]

# Stop-phrases in description indicating regional restriction incompatible with Europe/Ireland
LINKEDIN_DESCRIPTION_STOP_PATTERNS = [
    # Explicit domestic role/candidate location restrictions (e.g. Jobgether country-specific clones, Expleo PT only, etc.)
    r'\blooking\s+for\s+(?:an?|the)\s+.*?\s+(?:based|living|residing|located)\s+in\s+(?!ireland|europe|the\s+eu\b|eu\b)(?:the\s+)?[a-z]{2,}(?:\s+[a-z]+)?\b',
    r'\b(?:role|position|job|engineer|tester|sdet|developer|candidate|applicant|someone|you|individual|person)\b[^\.\n;]{0,40}\b(?:based|living|residing|located)\s+in\s+(?!ireland|europe|the\s+eu\b|eu\b)(?:the\s+)?[a-z]{2,}(?:\s+[a-z]+)?\b',
    r'\b(?:must|should|need\s+to|required\s+to)\s+(?:already\s+|currently\s+)?(?:be\s+)?(?:based|located|resident|living|residing|live|reside)\s+in\s+(?!ireland|europe|the\s+eu\b|eu\b)(?:the\s+)?[a-z]{2,}(?:\s+[a-z]+)?\b',
    r'\b(?:remotely|remote[\s,-]+)\s*(?:based|located)\s+in\s+(?!ireland|europe|the\s+eu\b|eu\b)(?:the\s+)?[a-z]{2,}(?:\s+[a-z]+)?\b',
    r'\bbased\s+in\s+(?:germany|netherlands|romania|united\s+kingdom|uk\b|poland|france|spain|italy|portugal|sweden|denmark|norway|finland|austria|switzerland|belgium|czech(?:\s+republic)?|hungary|bulgaria|croatia|greece|slovakia)\s*[\(\[]?\s*remote',
    # Specific regional restrictions (Americas, Asia, Africa)
    r'\b(?:role|position|job|opportunity)\s+(?:is\s+)?(?:strictly\s+)?for\s+(?:latam|latin\s+america|apac|north\s+america|south\s+america)\b',
    r'\b(?:only\s+)?for\s+(?:latam|latin\s+america)\b',
    r'\b(?:remote\s+(?:role|position|opportunity)\s+)?for\s+latam\b',
    r'\b(?:fully\s+)?remote\s+role\s+for\s+(?!ireland|europe|eu\b|uk\b)[a-z\s]+',
    r'\b(?:must\s+be\s+)?(?:located|based|residing|living)\s+in\s+(?:latam|latin\s+america|south\s+america|north\s+america|apac|argentina|brazil|colombia|mexico|chile|india|philippines|pakistan|usa?|united\s+states|canada)\b',
    r'\b(?:latam|latin\s+america|south\s+america|apac|us|usa|canada)\s+only\b',
    r'\b(?:latam|latin\s+america)\s+candidates?\s+only\b',
    r'\bopen\s+only\s+to\s+(?:latam|latin\s+america|apac|us|usa)\b',
    r'\bresidents?\s+of\s+(?:latam|latin\s+america|argentina|brazil|colombia|mexico|usa?|united\s+states|india)\s+only\b',
    r'\btime\s*zones?\s*:\s*(?:est|pst|cst|mst|gmt-3|utc-3|utc-5)\s+only\b',
    r'\b(?:must\s+work\s+in|aligned\s+with)\s+(?:latam|est|pst|cst)\s+hours?\b',
]

# Title & Role Validation (отсекаем вакансии девелоперов, DevOps, PM и т.д.)
ENABLE_TITLE_FILTER = True

QA_TITLE_PATTERNS = [
    r'\bqa\b',
    r'\bsdet\b',
    r'\bqe\b',
    r'\bsqa\b',
    r'\baqa\b',
    r'\btests?\b',
    r'\btesters?\b',
    r'\btesting\b',
    r'\bquality\s+assurance\b',
    r'\bquality\s+engineers?\b',
    r'\bquality\s+analyst\b',
    r'\bquality\s+specialist\b',
    r'\bquality\s+lead\b',
    r'\bquality\s+manager\b',
    r'\bquality\s+control\b',
]

# Explicit non-QA overrides (чистые dev/ops роли, даже если в тексте заголовка случайно попалось слово вроде "testing")
NON_QA_OVERRIDE_PATTERNS = [
    r'\btest[\s-]driven\s+dev',
    r'\b(?:software\s+engineer|developer|programmer)\s*[,-]?\s*(?:backend|frontend|full[\s-]?stack|devops|sre|platform|mobile|ios|android|embedded|cloud)\b',
    r'\b(?:backend|frontend|full[\s-]?stack|devops|sre|site\s+reliability|data|platform|systems?|infrastructure|firmware|hardware|cloud)\s+(?:engineer|developer|architect|lead)\b',
    r'\b(?:product|project|program|release|delivery)\s+manager\b',
    r'\b(?:scrum\s+master|agile\s+coach)\b',
    r'\bengineering\s+operations\b',
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

# DOU Settings (jobs.dou.ua RSS feed)
ENABLE_DOU = True
DOU_CATEGORY = "QA"
DOU_REMOTE_ONLY = True
DOU_LIMIT = 50

# No Fluff Jobs Settings (nofluffjobs.com API)
ENABLE_NOFLUFF = True
NOFLUFF_CATEGORY = "testing"
NOFLUFF_REMOTE_ONLY = True
NOFLUFF_CURRENCY = "EUR"
NOFLUFF_LIMIT = 50

# JustJoin.it Settings (justjoin.it candidate API)
ENABLE_JUSTJOIN = True
JUSTJOIN_CATEGORY = "testing"
JUSTJOIN_REMOTE_ONLY = True
JUSTJOIN_CURRENCY = "EUR"
JUSTJOIN_MAX_PAGES = 3
JUSTJOIN_LIMIT = 30

# Adzuna API Settings (https://developer.adzuna.com/)
ENABLE_ADZUNA = True
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "").strip()
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "").strip()
ADZUNA_COUNTRIES = ["ie", "gb"]  # Ireland and UK
ADZUNA_KEYWORDS = [
    "QA Engineer",
    "SDET",
    "QA Automation",
]
ADZUNA_REMOTE_ONLY = True
ADZUNA_MAX_PAGES = 1
ADZUNA_RESULTS_PER_PAGE = 20

# Arbeitnow Settings (https://www.arbeitnow.com/api/job-board-api)
ENABLE_ARBEITNOW = True
ARBEITNOW_REMOTE_ONLY = True
ARBEITNOW_MAX_PAGES = 2
ARBEITNOW_LIMIT = 50

# Database file
DATABASE_FILE = str(Path(__file__).parent / "jobs_seen.db")

# Fetch full description snippet for Telegram message
FETCH_SNIPPETS = True
