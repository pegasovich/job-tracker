# 🎯 QA / SDET Remote Job Intelligence & Automation Platform 🇮🇪 🇬🇧 🇪🇺 🌍

[![Tests & Quality Gate](https://github.com/pegasovich/job-tracker/actions/workflows/tests.yml/badge.svg)](https://github.com/pegasovich/job-tracker/actions/workflows/tests.yml)
![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)
![Test Framework](https://img.shields.io/badge/tested_with-pytest-0A9EDC.svg)
![Test Count](https://img.shields.io/badge/tests-123%20passed-brightgreen.svg)
![Code Coverage](https://img.shields.io/badge/coverage-core%2090%25%2B-brightgreen.svg)
![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF.svg)

An automated, multi-source job intelligence engine engineered for **QA & SDET professionals** seeking **Remote (Worldwide / Pan-European / Ireland)** and **B2B / Contractor** positions.

The platform continuously aggregates, parses, filters, deduplicates, and alerts on verified openings across **8 major tech job boards, direct ATS systems, and APIs**, eliminating recruiter noise, domestic residency restrictions, and misleading "remote" listings.

Built with a production-grade **Test Automation Framework (TAF)** and an automated **CI/CD Quality Gate** (123 unit & parameterized tests) ensuring zero regressions during continuous rule tuning.

---

## 💡 What This Application Does

Searching for genuine international remote QA roles is fraught with friction:
1. **"Fake Remote" Listings:** Roles tagged as "Remote" that actually require domestic residency in Germany, Poland, France, Spain, or the UK due to local labor tax laws.
2. **False Positives:** Non-QA roles (Backend Engineers doing TDD, DevOps, Scrum Masters) cluttering search feeds.
3. **Information Fragmentation:** Tech jobs are scattered across global portals (LinkedIn), startup boards (Djinni), European tech hubs (No Fluff Jobs, JustJoin.it, DOU), open APIs (Arbeitnow), and regional aggregator networks (Adzuna).
4. **Duplicate Spam:** The same role reposted across different boards or multi-device tracker runs.

**This application solves all of the above automatically:**
* 📡 **Aggregates 8 Sources** simultaneously with zero authentication risk.
* 🛡 **Applies Multi-Level Quality Filters** (Role Title Validation, Geo Eligibility, Strict Remote vs Commutable Hybrid Heuristics).
* 💰 **Extracts Transparent Salaries & B2B Rates** directly from structured API payloads and descriptions.
* 💾 **Deduplicates Across Runs** using an idempotent SQLite storage layer.
* 📱 **Dispatches Instant Telegram Alerts** with formatted cards, tech stack tags, salary badges, and direct links.

---

## 🌐 Integrated Job Providers (8 Sources)

| Provider | Integration Type | Regional Focus | Highlights & Data Extracted |
|---|---|---|---|
| 🔵 **LinkedIn** | Guest API (`seeMoreJobPostings`) | Ireland, UK, Europe, Worldwide | Zero login/cookie risk; searches multiple targeted regions; cloud-optimized adaptive rate-limit backoff (10-15s) with non-destructive retry in next hourly cycle. |
| 🟢 **Djinni.co** | Schema.org JSON-LD Parser | Pan-European & Worldwide | Structured Schema microdata; applicant location requirement validation; USD salary parsing. |
| 🟡 **DOU** | Official RSS Feed (`feeds/?category=QA&remote`) | Europe, CEE, Remote & B2B | Real-time XML feed; full descriptions; automated B2B salary and country extraction. |
| 🔴 **No Fluff Jobs** | Internal REST API (`api/search/posting`) | Central & Western Europe | 100% transparent B2B & Permanent salary brackets in EUR; tech stack tags and skill tiles. |
| 🟣 **JustJoin.it** | Candidate REST API (`api/candidate-api/offers`) | Europe, CEE & Global Remote | Poland & Europe's top tech board; multi-currency conversions (EUR/USD); seniority & skill levels. |
| 🌐 **Arbeitnow** | Open REST API (`api/job-board-api`) | European Union & Remote | Free public European API; zero authentication/keys needed; 300 jobs/page; tag extraction. |
| 🟧 **Adzuna** | Official REST API (`api.adzuna.com`) | Ireland (`ie`) & UK (`gb`) | Official developer API; EUR (€) and GBP (£) salary ranges; contract type tags; graceful fallback. |
| 🌱 **Greenhouse** | Direct Company ATS (`boards-api.greenhouse.io`) | Worldwide & Remote-first | Direct carrier portal API for top tech companies (Canonical, Cloudflare, GitLab, Stripe, etc.); zero recruiter middleman. |

---

## 🔍 Multi-Level Quality & Filtering Pipeline

Every incoming job posting passes through an automated filtering pipeline before an alert is dispatched:

```
Raw Job from Scraper
         │
         ▼
[ Level 0: Title & Role Validation ] ──► (Reject Non-QA Developer / DevOps / PM roles)
         │
         ▼
[ Level 1: Duplicate Check ] ──────────► (Skip if ID already seen in SQLite database)
         │
         ▼
[ Level 2: Workplace & Geo Filter ] ───► (Reject Onsite & Domestic Residency Locked roles)
         │                                (Allow Commutable Hybrid only for Co. Kerry, IE)
         ▼
[ Level 3: Country Eligibility ] ──────► (Verify Ireland / EU / Worldwide applicant suitability)
         │
         ▼
[ Formatting & Telegram Dispatch ] ────► (Send alert card & persist to SQLite with timestamp)
```

### 1. Level 0: Strict QA Title Validation
Ensures roles like *"Software Engineer, Backend (Unit Testing)"*, *"PLC Automation Engineer"*, *"Scrum Master"*, or *"DevOps"* are immediately dropped, while accepting genuine QA, SDET, SQA, Automation, and Testing titles.

### 2. Level 1: Idempotent Deduplication
Stores processed IDs in SQLite (`jobs_seen.db`). Duplicate items trigger `INSERT OR IGNORE`, preventing redundant alerts and guaranteeing idempotency across parallel or multi-machine runs.

### 3. Level 2: Domestic Restriction & Commuter Heuristics
* **Universal Remote:** Roles open to candidates Worldwide, Pan-European, EU, or Ireland are approved.
* **Domestic Remote Block:** Identifies regex patterns indicating local residency requirements (e.g. *"must be resident in Germany"*, *"looking for an SDET based in Poland"*).
* **Commutable Hybrid Radius:** Hybrid roles are rejected unless within reasonable daily/weekly commute distance to South-West Ireland (Co. Kerry, Cahersiveen, Tralee, Killarney).

---

## 🧪 SDET & Quality Engineering Architecture

Web scrapers and regex filters operate in volatile environments where target DOM structures change and edge cases occur frequently. This project treats test automation as a first-class citizen:

```
job-tracker/
├── .github/workflows/
│   └── tests.yml            # CI/CD: Automated Pytest run & coverage on push/PR
├── tests/
│   ├── conftest.py          # Pytest fixtures (tmp_path DB, test clients, dummy jobs)
│   ├── test_filters.py      # Unit & parameterized tests for workplace/geo rules (50+ cases)
│   ├── test_database.py     # SQLite persistence, idempotency & deduplication tests
│   ├── test_notifier.py     # Telegram API client unit tests with HTTP mocks
│   ├── test_dou.py          # DOU RSS feed parsing & salary extraction tests
│   ├── test_nofluff.py      # No Fluff Jobs REST API parser & currency formatting tests
│   ├── test_justjoin.py     # JustJoin.it Candidate API pagination & B2B salary tests
│   ├── test_adzuna.py       # Adzuna API client, HTML stripping & unconfigured fallback tests
│   ├── test_arbeitnow.py    # Arbeitnow REST API parsing & remote filtering tests
│   └── test_greenhouse.py   # Greenhouse direct company ATS parsing & remote tests
├── pytest.ini               # Pytest configuration & test discovery settings
├── requirements-dev.txt     # Test dependencies (pytest, pytest-cov, flake8)
├── database.py              # SQLite storage layer
├── linkedin_scraper.py      # LinkedIn Guest API scraper & classifier
├── djinni_scraper.py        # Djinni JSON-LD scraper
├── dou_scraper.py           # DOU RSS feed scraper
├── nofluff_scraper.py       # No Fluff Jobs REST API scraper
├── justjoin_scraper.py      # JustJoin.it candidate API scraper
├── adzuna_scraper.py        # Adzuna REST API scraper (IE & UK)
├── arbeitnow_scraper.py     # Arbeitnow open REST API scraper (EU & Remote)
├── greenhouse_scraper.py    # Greenhouse Direct Company ATS scraper
└── telegram_notifier.py     # Telegram Bot API notification engine
```

### Automated CI/CD Pipeline (GitHub Actions)
Every `git push` and Pull Request automatically triggers the test pipeline:
1. Provisions an Ubuntu runner on Python 3.12.
2. Installs runtime and testing dependencies with pip caching.
3. Runs all **120 tests** with coverage collection (`pytest --cov=. --cov-report=term-missing`).
4. Enforces the Quality Gate before merging.

---

## 🚀 Quick Start

### 1. Prerequisites & Installation
```bash
git clone https://github.com/pegasovich/job-tracker.git
cd job-tracker

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install runtime and testing dependencies
pip install -r requirements-dev.txt
```

### 2. Configuration Setup
Create a `.env` file in the root directory (refer to `.env.example`):
```env
# Required for Telegram notifications:
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_CHAT_ID=your_telegram_chat_id

# Optional: Adzuna API (free registration on https://developer.adzuna.com/)
ADZUNA_APP_ID=your_adzuna_app_id
ADZUNA_APP_KEY=your_adzuna_app_key
```
*(If Adzuna credentials are left empty, the tracker will automatically skip Adzuna and run all other 7 providers without errors.)*

### 3. Running the Test Suite
```bash
# Run all 120 tests
pytest -q

# Run with coverage report
pytest --cov=. --cov-report=term-missing
```

### 4. Running the Tracker Locally
```bash
# Dry run: search and display matches in the console without sending Telegram messages
python main.py --dry-run

# Smoke test: runs a single query to verify connectivity
python main.py --test --dry-run

# Production run: execute scan across all providers and dispatch alerts
python main.py

# Continuous monitoring: run scan periodically every N minutes (e.g. every 60 mins)
python main.py --interval 60
```

### 5. ☁️ 24/7 Cloud Automation & Cloud Rate-Limit Optimization
The platform includes an automated cloud workflow (`.github/workflows/tracker_cron.yml`) that executes every hour without keeping your computer on:
1. **Zero Infrastructure Cost:** Runs on GitHub-hosted Ubuntu runners for 100% free.
2. **State Persistence (Git Scraping):** Automatically commits and pushes the updated `jobs_seen.db` back to the repository so duplicate alerts are never sent across runs.
3. **Cloud-Optimized Rate Limiting:**
   * Unlike residential home IPs, cloud data centers (e.g. GitHub/Azure) encounter aggressive `429 Too Many Requests` thresholds from LinkedIn's guest API.
   * The scraper employs an **adaptive fast backoff** (`LINKEDIN_MAX_RETRIES=1`, `LINKEDIN_RETRY_BASE_WAIT=10s`, `LINKEDIN_SEARCH_LIMIT=6`).
   * When LinkedIn rate-limits a detail fetch, the job is **gracefully skipped without marking it as seen in SQLite**, preserving it to be inspected cleanly on the very next hourly cycle without blocking the run for 10+ minutes.
   * The other 7 sources (DOU, No Fluff Jobs, JustJoin.it, Arbeitnow, Greenhouse ATS, Adzuna, Djinni) operate via open APIs / RSS feeds and run in seconds with zero rate-limit friction.
4. **Repository Secrets:** Add your credentials under **Settings ➔ Secrets and variables ➔ Actions ➔ New repository secret**:
   * `TELEGRAM_BOT_TOKEN`
   * `TELEGRAM_CHAT_ID`
   * `ADZUNA_APP_ID` *(optional)*
   * `ADZUNA_APP_KEY` *(optional)*
5. **Manual Run:** Trigger anytime from the **Actions** tab ➔ **Hourly Remote QA Job Tracker** ➔ **Run workflow**.

---

## 🛠 Tech Stack

* **Language:** Python 3.12
* **Testing Framework:** Pytest 9, Pytest-Cov, Unittest.Mock (123 automated tests)
* **CI/CD:** GitHub Actions Quality Gate & Hourly Automated Cron Engine
* **Persistence:** SQLite3 (WAL mode, idempotent schemas, Git-backed sync)
* **Networking & Parsing:** Standard library (`urllib.request`), JSON, XML (`xml.etree.ElementTree`)
* **Integrations:** Telegram Bot API, LinkedIn Guest API, Djinni Schema.org, DOU RSS, No Fluff Jobs API, JustJoin.it API, Adzuna API, Arbeitnow API, Greenhouse ATS
* **Form Automation:** JavaScript (`autofill.js`)

---

## 📄 License
This project is open-source and available under the [MIT License](LICENSE).
