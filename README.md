# QA / SDET Remote Job Tracker & Test Automation Case Study 🇮🇪 🇬🇧 🌍

[![Tests & Quality Gate](https://github.com/pegasovich/job-tracker/actions/workflows/tests.yml/badge.svg)](https://github.com/pegasovich/job-tracker/actions/workflows/tests.yml)
![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)
![Test Framework](https://img.shields.io/badge/tested_with-pytest-0A9EDC.svg)
![Code Coverage](https://img.shields.io/badge/coverage-core%2090%25%2B-brightgreen.svg)
![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF.svg)

An automated job search and intelligence service designed for **QA / SDET professionals** looking for remote and relocation-friendly roles across **Ireland, the UK, Europe, and Worldwide**. 

Built with a production-grade **Test Automation Framework (TAF)** and automated **CI/CD Quality Gate** to guarantee zero regressions during continuous rule tuning.

---

## 🎯 Project Highlights

* **Multi-Source Scraping:** Aggregates job postings from **LinkedIn** (Guest API with zero authentication risk) and **Djinni.co** (Schema.org JSON-LD parser).
* **Intelligent Workplace & Geo Filtering:**
  * ✅ **Remote:** Accepted universally (worldwide / pan-European / Ireland).
  * ⚠️ **Hybrid:** Filtered using regex distance heuristics (only accepted if commutable to Co. Kerry / Cahersiveen / Tralee / Killarney).
  * 🚫 **On-Site & Domestic Restrictive:** Blocked automatically, including multi-lingual job boards with country-locked residency mandates (e.g. Poland-only, Germany-only clones).
* **Deduplication Engine:** SQLite storage with idempotency guarantees to prevent duplicate Telegram alerts across multi-device runs.
* **Instant Alerts:** Formatted Telegram cards with auto-extracted job description summaries.

---

## 🧪 SDET & Quality Engineering Architecture

Web scrapers and text-filtering rules operate in volatile environments where target DOM structures change and edge cases occur frequently. This project is structured around an automated **Quality Gate** that treats filters, parsers, and external integrations as mission-critical components.

```
job-tracker/
├── .github/workflows/
│   └── tests.yml            # CI/CD: Automated Pytest run & coverage on push/PR
├── tests/
│   ├── conftest.py          # Pytest fixtures (tmp_path DB, test clients, dummy jobs)
│   ├── test_filters.py      # Unit & parameterized tests for workplace/geo rules
│   ├── test_database.py     # SQLite persistence, idempotency & deduplication tests
│   └── test_notifier.py     # Telegram API client unit tests with HTTP mocks
├── pytest.ini               # Pytest configuration & test discovery settings
├── requirements-dev.txt     # Test dependencies (pytest, pytest-cov, flake8)
├── database.py              # SQLite storage layer
├── linkedin_scraper.py      # LinkedIn Guest API scraper & classifier
├── djinni_scraper.py        # Djinni JSON-LD scraper
└── telegram_notifier.py     # Telegram Bot API notification engine
```

### 1. Parameterized Filter & Regression Testing (`test_filters.py`)
* **Domestic Restriction Detection:** Parameterized test suite validating that roles masked as "Remote" but requiring domestic residency in Germany, Poland, France, the UK, Spain, or Latam are correctly flagged as `onsite/blocked`.
* **Pan-European Acceptance:** Verifies that genuine international/contractor roles (e.g. *"remote across Europe"*, *"B2B contractor"*, *"worldwide considered"*) are accepted.
* **Commuter Radius Verification:** Parameterized checks for hybrid locations against South-West Ireland (Kerry allowed; Dublin, Cork, London rejected).
* **JSON-LD Schema Verification:** Validates Djinni country/region eligibility algorithms.

### 2. State & Persistence Testing (`test_database.py`)
* Tests run against isolated, ephemeral SQLite databases created dynamically via `pytest`'s `tmp_path` fixture.
* **Idempotency & Deduplication:** Verifies that duplicate job IDs trigger `INSERT OR IGNORE` without error and maintain consistent record counts.

### 3. API Isolation & Resilience (`test_notifier.py`)
* Uses `unittest.mock.patch` to isolate HTTP requests to `api.telegram.org`.
* Verifies HTML character escaping (`<`, `>`, `&`) in job titles and companies to prevent Telegram API parsing errors.
* Simulates network timeouts and HTTP errors to confirm graceful fallback without application crashes.

### 4. Automated CI/CD Pipeline (GitHub Actions)
Every `git push` and Pull Request automatically triggers the test pipeline:
1. Provisions an Ubuntu runner on Python 3.12.
2. Installs dependencies from `requirements-dev.txt` with pip caching.
3. Runs the test suite with coverage collection (`pytest --cov=. --cov-report=term-missing`).
4. Enforces the Quality Gate before merging.

---

## 🚀 Quick Start

### 1. Prerequisites & Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/pegasovich/job-tracker.git
cd job-tracker

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install runtime and testing dependencies
pip install -r requirements-dev.txt
```

### 2. Running the Test Suite
Run the full test suite with verbose output:
```bash
pytest
```

Run tests with test coverage report:
```bash
pytest --cov=. --cov-report=term-missing
```

---

## ⚙️ Configuration & Execution

### 1. Environment Setup
Create a `.env` file in the root directory (refer to `.env.example`):
```env
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

### 2. Running the Tracker
```bash
# Dry run: search and display matches in the console without sending Telegram alerts
python main.py --dry-run

# Smoke test: single keyword and single region
python main.py --test

# Production run: execute scan and send new alerts to Telegram
python main.py

# Continuous monitoring: run scan periodically every N minutes
python main.py --interval 60
```

---

## 🛠 Tech Stack

* **Language:** Python 3.12
* **Testing:** Pytest, Pytest-Cov, Unittest.Mock
* **CI/CD:** GitHub Actions
* **Database:** SQLite
* **APIs & Web:** LinkedIn Guest API, Djinni JSON-LD Schema, Telegram Bot API
* **Form Automation:** JavaScript (`autofill.js`)

---

## 📄 License
This project is open-source and available under the [MIT License](LICENSE).
