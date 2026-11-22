# 🎯 QA / SDET Remote Job Intelligence & Automation Platform 🇮🇪 🇬🇧 🇪🇺 🌍

[![Tests & Quality Gate](https://github.com/pegasovich/job-tracker/actions/workflows/tests.yml/badge.svg)](https://github.com/pegasovich/job-tracker/actions/workflows/tests.yml)
![Python Version](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue.svg)
![Test Framework](https://img.shields.io/badge/tested_with-pytest-0A9EDC.svg)
![Test Count](https://img.shields.io/badge/tests-246%20passed-brightgreen.svg)
![Code Coverage](https://img.shields.io/badge/coverage-core%2090%25%2B-brightgreen.svg)
![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF.svg)

An automated, multi-source job intelligence engine engineered for **QA & SDET professionals** seeking **Remote (Worldwide / Pan-European / Ireland)** and **B2B / Contractor** positions.

The platform continuously aggregates, parses, filters, deduplicates, and alerts on verified openings across **direct ATS systems, curated remote portals, and APIs**, eliminating recruiter noise, domestic residency restrictions, and misleading "remote" listings.

Built with a production-grade **Test Automation Framework (TAF)** and an automated **CI/CD Quality Gate** (246 unit & parameterized tests) ensuring zero regressions during continuous rule tuning.

---

## 💡 What This Application Does

Searching for genuine international remote QA roles is fraught with friction:
1. **"Fake Remote" Listings:** Roles tagged as "Remote" that actually require domestic residency in Germany, Poland, France, Spain, or the UK due to local labor tax laws.
2. **False Positives:** Non-QA roles (Backend Engineers doing TDD, DevOps, Scrum Masters) cluttering search feeds.
3. **Information Fragmentation:** Tech jobs are scattered across global portals (LinkedIn), startup boards (Djinni), direct company ATS systems (Greenhouse, Lever), curated remote aggregators (Remotive, WeWorkRemotely), European tech hubs (DOU), and open APIs (Arbeitnow).
4. **Duplicate Spam:** The same role reposted across different boards or multi-device tracker runs.

**This application solves all of the above automatically:**
* 📡 **Aggregates Multiple High-Quality Sources** simultaneously with zero authentication risk.
* 🛡 **Applies Multi-Level Quality Filters** (Role Title Validation, Geo Eligibility, Strict Remote vs Commutable Hybrid Heuristics).
* 💰 **Extracts Transparent Salaries & B2B Rates** directly from structured API payloads and descriptions.
* 💾 **Deduplicates Across Runs** using an idempotent SQLite storage layer.
* 📱 **Dispatches Instant Telegram Alerts** with formatted cards, tech stack tags, salary badges, and direct links.

---

## 🌐 Integrated Job Providers

| Provider | Integration Type | Regional Focus | Highlights & Data Extracted | Status |
|---|---|---|---|---|
| 🔵 **LinkedIn** | Guest API (`seeMoreJobPostings`) | Ireland, UK, Europe, Worldwide | Zero login/cookie risk; searches multiple targeted regions; cloud-optimized adaptive rate-limit backoff (10-15s). | ✅ Enabled |
| 🟢 **Djinni.co** | Schema.org JSON-LD Parser | Pan-European & Worldwide | Structured Schema microdata; applicant location requirement validation; USD salary parsing. | ✅ Enabled |
| 🟡 **DOU** | Official RSS Feed (`feeds/?category=QA&remote`) | Europe, CEE, Remote & B2B | Real-time XML feed; full descriptions; automated B2B salary and country extraction. | ✅ Enabled |
| 🌐 **Arbeitnow** | Open REST API (`api/job-board-api`) | European Union & Remote | Free public European API; zero authentication/keys needed; non-English heuristics filter. | ✅ Enabled |
| 🌱 **Greenhouse** | Direct Company ATS (`boards-api.greenhouse.io`) | Worldwide & Remote-first | Direct carrier portal API for 40+ top tech companies (Stripe, Cloudflare, Datadog, Elastic, Toast, Intercom, etc.); zero recruiter middleman. | ✅ Enabled |
| ⚡ **Lever** | Direct Company ATS (`api.lever.co/v0/postings`) | Worldwide & Remote-first | Direct carrier portal API for top tech companies (Palantir, Spotify, Wealthfront, Outreach, Glide); clean plain text descriptions. | ✅ Enabled |
| 🪐 **Ashby** | Direct Company ATS (`api.ashbyhq.com/posting-api`) | Worldwide & Remote-first | Direct carrier portal API for top modern tech/AI companies (Linear, Synthesia, Notion, PostHog, Snyk, Zapier, OpenAI, Cursor, Modal); zero middleman. | ✅ Enabled |
| 🏔️ **Himalayas** | Curated Remote REST API (`himalayas.app/jobs/api`) | Global & EMEA Remote | Pure 100% remote board; structured location & timezone restrictions (UTC+0/+1 Irish overlap verification); salary parsing. | ✅ Enabled |
| 🚀 **Remotive** | Curated Remote API (`remotive.com/api/remote-jobs`) | Worldwide & Pan-European | Curated 100% remote positions with structured candidate location requirements validation; salary extraction. | ✅ Enabled |
| 💼 **WeWorkRemotely** | Curated Remote RSS Feed (`weworkremotely.com`) | Worldwide & Global Remote | Leading global remote tech board with real-time XML streaming; automated title and salary extraction. | ✅ Enabled |
| 🔴 **No Fluff Jobs** | Internal REST API (`api/search/posting`) | Central & Western Europe | Polish domestic B2B market (JDG/PL residency required). | ❌ Disabled |
| 🟣 **JustJoin.it** | Candidate REST API (`api/candidate-api/offers`) | Europe, CEE & Global Remote | Polish domestic market (PLN currency / Polish B2B tax residency). | ❌ Disabled |
| 🟧 **Adzuna** | Official REST API (`api.adzuna.com`) | Ireland (`ie`) & UK (`gb`) | Paid developer subscription model; no dedicated Ireland endpoint. | ❌ Disabled |

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
[ Level 2.5: Polish Domestic Filter ] ─► (Reject Polish language requirements & domestic titles)
         │                                (pl jobLanguage, (k/m), Tester Manualny, etc.)
         ▼
[ Level 3: Country Eligibility ] ──────► (Verify Ireland / EU / Worldwide applicant suitability)
         │
         ▼
[ Formatting & Telegram Dispatch ] ────► (Send alert card & persist to SQLite with timestamp)
```

### 1. Level 0: Strict QA Title Validation & Non-QA Overrides
* **Positive Patterns:** Identifies genuine QA, SDET, SQA, Automation, Performance, and Software Testing titles.
* **Negative Overrides:** Eliminates false positives where "testing" or "quality" appears in non-IT or non-QA domains:
  * Pure Dev/Ops: *Software Engineer (Backend/Frontend/DevOps/SRE/Platform)*, *Scrum Master*, *Engineering Ops*.
  * Regulatory & Legal: *Compliance Lead (Testing)*, *Regulatory Testing Analyst*, *Internal Audit & Controls*, *SOX/KYC/AML*.
  * Cybersecurity & Pen-Testing: *Penetration Tester / Pen-Test Consultant*, *Ethical Hacker*.
  * Medical & Laboratory: *Clinical Testing Coordinator*, *Lab / Chemical / Swab Testing*.
  * Industrial & Materials: *Non-Destructive Testing (NDT)*, *Soil & Concrete Testing*, *Materials Testing Technician*.
  * Marketing & Growth: *A/B Testing Specialist*, *Conversion Rate Optimization (CRO)*.

### 2. Level 1: Idempotent Deduplication
Stores processed IDs in SQLite (`jobs_seen.db`). Duplicate items trigger `INSERT OR IGNORE`, preventing redundant alerts and guaranteeing idempotency across parallel or multi-machine runs.

### 3. Level 2: Cross-Source Geo-Blocking (US Domestic & Overseas Restrictions)
* **Universal Remote:** Roles open to candidates Worldwide, Pan-European, EU, or Ireland are approved.
* **Domestic US & Incompatible Region Block:** Blocks domestic remote positions labeled as `Remote US`, `US Remote`, `Remote (US)`, `United States`, `Canada`, `Latam`, `APAC`, `India`, etc., directly across all providers (Greenhouse, Lever, Arbeitnow, Remotive, WWR, DOU, Djinni, LinkedIn).
* **Commutable Hybrid Radius:** Hybrid roles are rejected unless within reasonable daily/weekly commute distance to South-West Ireland (Co. Kerry, Cahersiveen, Tralee, Killarney).

### 4. Level 3: Description Stop-Pattern & Domestic Salary Gate
* Scans full job descriptions for domestic restrictions:
  * US state compensation disclosures (*"USA base pay range"*, *"base pay range (all other U.S. states)"*).
  * Domestic work authorization mandates (*"authorized to work in the US"*, *"remote within the US only"*).
  * Foreign country residency locked clauses (*"must be resident in Germany"*, *"looking for an SDET based in Poland"*).

### 5. Level 3.5: Polish Domestic & Language Filtering
* **No Fluff Jobs:** Rejects offers tagged with `pl` / `jobLanguage: pl` requirements.
* **JustJoin.it:** Rejects offers requiring Polish language (`code: pl`).
* **Title Filtering:** Drops Polish-domestic titles (`Tester Manualny`, `Tester Automatyzujący`, `Specjalista ds. Testów`, and gender parity markers `(k/m)`, `(m/k)`).
* **Benefit:** Eliminates 80-90% of Poland-locked internal noise, forwarding only genuine English-language international contracts.

---

## 🧪 SDET & Quality Engineering Architecture

Web scrapers and regex filters operate in volatile environments where target DOM structures change and edge cases occur frequently. This project treats test automation as a first-class citizen:

```
job-tracker/
├── .github/workflows/
│   └── tests.yml            # CI/CD: Automated Pytest run & coverage on push/PR
├── chrome-extension/        # Manifest V3 AI Job Application Assistant
│   ├── manifest.json        # Extension manifest (DOU, Djinni, LinkedIn, ATS)
│   ├── background.js        # Service worker (Gemini Flash API & multi-model fallback)
│   ├── content.js           # DOM parser for <textarea> & Froala rich-text editors
│   ├── content.css          # Injected UI toolbar styles
│   ├── popup.html           # Settings UI (API keys, Candidate Profile, Tone)
│   ├── popup.js             # Storage management & key validator
│   └── icons/               # Extension icons
├── tests/
│   ├── conftest.py          # Pytest fixtures (tmp_path DB, test clients, dummy jobs)
│   ├── test_filters.py      # Unit & parameterized tests for workplace/geo/Polish rules (60+ cases)
│   ├── test_database.py     # SQLite persistence, idempotency & deduplication tests
│   ├── test_notifier.py     # Telegram API client unit tests with HTTP mocks
│   ├── test_dou.py          # DOU RSS feed parsing & salary extraction tests
│   ├── test_nofluff.py      # No Fluff Jobs REST API parser & Polish filter tests
│   ├── test_justjoin.py     # JustJoin.it Candidate API pagination & B2B salary tests
│   ├── test_adzuna.py       # Adzuna API client, HTML stripping & unconfigured fallback tests
│   ├── test_arbeitnow.py    # Arbeitnow REST API parsing & remote filtering tests
│   └── test_greenhouse.py   # Greenhouse direct company ATS parsing & remote tests
├── pytest.ini               # Pytest configuration & test discovery settings
├── requirements-dev.txt     # Test dependencies (pytest, pytest-cov, flake8)
├── database.py              # SQLite storage layer with safe merge capability
├── linkedin_scraper.py      # LinkedIn Guest API scraper & classifier
├── djinni_scraper.py        # Djinni JSON-LD scraper & geo verification
├── dou_scraper.py           # DOU RSS feed scraper
├── nofluff_scraper.py       # No Fluff Jobs REST API scraper with Polish filtering
├── justjoin_scraper.py      # JustJoin.it candidate API scraper with language filtering
├── adzuna_scraper.py        # Adzuna REST API scraper (IE & UK)
├── arbeitnow_scraper.py     # Arbeitnow open REST API scraper (EU & Remote)
├── greenhouse_scraper.py    # Greenhouse Direct Company ATS scraper
└── telegram_notifier.py     # Telegram Bot API notification engine
```

### Automated CI/CD Pipeline (GitHub Actions)
Every `git push` and Pull Request automatically triggers the test pipeline:
1. Provisions an Ubuntu runner on Python 3.12.
2. Installs runtime and testing dependencies with pip caching.
3. Runs all **246 tests** with coverage collection (`pytest --cov=. --cov-report=term-missing`).
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
# Run all 246 tests
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

### 5. ☁️ 24/7 Cloud Automation via External Scheduler (cron-job.org)
The platform includes an automated cloud workflow (`.github/workflows/tracker_cron.yml`) triggered 24/7 via GitHub REST API dispatch (`workflow_dispatch`), running completely free on GitHub-hosted runners without keeping your local computer powered on:

1. **Why External Dispatch?**
   * GitHub Actions native cron schedules (`schedule:`) suffer from significant delays (up to several hours) or dropped runs during shared queue congestion.
   * Triggering via `workflow_dispatch` through the GitHub REST API bypasses the delayed cron queue entirely and starts the job immediately (within 5–10 seconds).
2. **Setting Up 24/7 Free Scheduler (e.g. [cron-job.org](https://cron-job.org)):**
   * **Target URL:** `https://api.github.com/repos/pegasovich/job-tracker/actions/workflows/tracker_cron.yml/dispatches`
   * **Method:** `POST`
   * **Schedule:** Every 30 minutes (or custom cron `15,45 * * * *`)
   * **Headers:**
     * `Accept: application/vnd.github+json`
     * `Authorization: Bearer <GITHUB_TOKEN>` (token with `workflow` scope, e.g. from `gh auth token`)
     * `Content-Type: application/json`
     * `X-GitHub-Api-Version: 2022-11-28`
     * `User-Agent: cron-job-org`
   * **Request Body:** `{"ref":"main"}`
3. **State Persistence (Git Scraping):** Automatically commits and pushes the updated `jobs_seen.db` back to the repository so duplicate alerts are never sent across runs.
4. **Cloud-Optimized Rate Limiting:**
   * Unlike residential home IPs, cloud data centers (e.g. GitHub/Azure) encounter aggressive `429 Too Many Requests` thresholds from LinkedIn's guest API.
   * The scraper employs an **adaptive fast backoff** (`LINKEDIN_MAX_RETRIES=1`, `LINKEDIN_RETRY_BASE_WAIT=10s`, `LINKEDIN_SEARCH_LIMIT=6`).
   * When LinkedIn rate-limits a detail fetch, the job is **gracefully skipped without marking it as seen in SQLite**, preserving it to be inspected cleanly on the very next hourly cycle without blocking the run for 10+ minutes.
   * The other 7 sources (DOU, No Fluff Jobs, JustJoin.it, Arbeitnow, Greenhouse ATS, Adzuna, Djinni) operate via open APIs / RSS feeds and run in seconds with zero rate-limit friction.
5. **Repository Secrets:** Add your credentials under **Settings ➔ Secrets and variables ➔ Actions ➔ New repository secret**:
   * `TELEGRAM_BOT_TOKEN`
   * `TELEGRAM_CHAT_ID`
   * `ADZUNA_APP_ID` *(optional)*
   * `ADZUNA_APP_KEY` *(optional)*
6. **Manual Run:** Trigger anytime from the **Actions** tab ➔ **Remote QA Job Tracker** ➔ **Run workflow**.

---

## 🧩 Chrome Extension: Job Apply AI (Gemini Powered)

Located in [`chrome-extension/`](./chrome-extension/): A lightweight Manifest V3 browser extension that automatically analyzes job descriptions and drafts tailored, honest cover letters directly into application forms.

* **Supported Platforms:** DOU (`jobs.dou.ua`), Djinni (`djinni.co`), LinkedIn, PeopleForce ATS (`*.peopleforce.io`), Greenhouse, Lever, Workable, Breezy HR, and standard job boards.
* **Rich-Text & Plain Text Support:** Seamlessly autofills both native `<textarea>` and rich-text editors (Froala, contenteditable) with proper DOM change events.
* **AI Engine:** Powered by Google's free **Gemini API** (`gemini-2.0-flash` / `gemini-3.8-flash` with automatic fallback).
* **Anti-Hallucination & Transferable Skills:** Strictly enforces truthful positioning based on the candidate's actual profile; bridges skill gaps via fundamental engineering concepts without fabricating experience.
* **Installation:** Open `chrome://extensions/` ➔ Enable Developer Mode ➔ **Load unpacked** ➔ Select `chrome-extension/`.

---

## 🛠 Tech Stack

* **Language:** Python 3.12
* **Testing Framework:** Pytest 9, Pytest-Cov, Unittest.Mock (246 automated tests)
* **CI/CD:** GitHub Actions 24/7 Cloud Automation & Quality Gate
* **Persistence:** SQLite3 (WAL mode, idempotent schemas, Git-backed sync)
* **Networking & Parsing:** Standard library (`urllib.request`), JSON, XML (`xml.etree.ElementTree`)
* **Integrations:** Telegram Bot API, LinkedIn Guest API, Djinni Schema.org, DOU RSS, No Fluff Jobs API, JustJoin.it API, Adzuna API, Arbeitnow API, Greenhouse ATS
* **AI Extension:** Chrome Manifest V3, Google Gemini API (2.0/3.8 Flash), Froala & DOM parser

---

## 💻 Continuing Work on a Laptop (Step-by-Step Guide)

When switching to your laptop, follow this quick checklist to resume seamlessly:

### 1. Pull the Latest Repository
```bash
git pull origin main
```
*(Or `git clone https://github.com/pegasovich/job-tracker.git` if cloning fresh).*

### 2. Environment Setup
```bash
# Python 3.12+ recommended
python -m venv .venv

# Activate on Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 3. Configure Local Credentials
Create a `.env` file in the project root:
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
ADZUNA_APP_ID=your_adzuna_app_id
ADZUNA_APP_KEY=your_adzuna_app_key
```

### 4. Verify Local Tests
```bash
pytest -q
# Expecting: 246 passed
```

### 5. Load the Chrome Extension on Laptop
1. Open Google Chrome on your laptop and go to `chrome://extensions/`.
2. Enable **Developer mode** (top-right).
3. Click **Load unpacked** (top-left) and select the `chrome-extension/` folder from this repo.
4. Click the extension icon ✨ in Chrome and confirm your Gemini API key and profile details are saved (settings automatically sync if signed into the same Chrome profile).

### 6. Cloud Automation (24/7 Monitoring)
* **Zero laptop dependencies:** The tracker is already scheduled in the cloud via `cron-job.org` calling the GitHub Actions `workflow_dispatch` API every 30 minutes.
* It runs 24/7 even when your laptop is turned off or asleep.
* Any seen jobs are automatically synchronized and merged back into `jobs_seen.db`.

---

## 📄 License
This project is open-source and available under the [MIT License](LICENSE).
