# AGENTS.md — AI Engineering & Architecture Guide

This repository (`job-tracker`) is an automated multi-source **Remote QA / SDET / Test Automation Job Tracker** tailored for a candidate based in **Ireland (Co. Kerry / Cahersiveen)**, paired with a Manifest V3 **Chrome Extension** (`chrome-extension/`) for Gemini-assisted applications and contact autofill.

This file gives coding agents (Codex, Antigravity, Cursor, Claude Code, Copilot) immediate context on architecture, invariants, and verification commands.

---

## 1. Target Candidate & Filtering Rules

- **Allowed roles:** QA Engineer, SDET, QA Automation, Test Automation, Manual QA, Software Tester, Performance Test Engineer (`LinkedInJobScraper.is_qa_title` in `linkedin_scraper.py`, rules in `config.py`). Rejects pure Dev/DevOps/SRE/PM, pen-testing, compliance/SOX/audit, clinical/lab/industrial/A-B testing, and non-English native-speaker roles.
- **Allowed locations & remote scope:**
  - `Ireland`, pan-European (`Europe`, `EU`, `EMEA`), or `Worldwide` / `Anywhere`.
  - Rejects `UK-only`, `US-only`, `Canada`, `Latam`, `APAC`, and country-locked European roles excluding Ireland (e.g., `"must reside in Germany"`, `"Locations: Poland, Portugal"`, US salary range tables) via `is_location_blocked`, `is_description_blocked`, `detect_workplace_type`, and source-specific checks.
  - Rejects `onsite` (`ALLOW_ONSITE = False`) and `hybrid` (`ALLOW_HYBRID = False`) **unless** `hybrid` is within commuting distance of Co. Kerry (`HYBRID_ALLOWED_LOCATIONS` in `config.py` / `is_hybrid_nearby` in `main.py`).
- **Language filter:** English-only (`config.has_non_allowed_language_requirement` and `config.is_polish_domestic_title`).

---

## 2. Repository Map

| Path | Role |
|---|---|
| `main.py` | Entrypoint (`main`, `run_tracker`), `tracker.lock` single-instance lock, unified non-LinkedIn pipeline (`process_standard_jobs`, `process_remote_feed_jobs`, `_deliver_job_alert`), LinkedIn rotation (`build_linkedin_rotation_queries`, `process_linkedin_jobs`). |
| `config.py` | All feature flags (`ENABLE_*`), LinkedIn query groups & rate-limit tuning, geo/title/language regex patterns, `HYBRID_ALLOWED_LOCATIONS`, ATS company slugs. |
| `database.py` | `JobDatabase` SQLite wrapper (`jobs_seen.db`). Manages `seen_jobs`, `source_sync_state` (hourly poll throttling), `rotation_state` (LinkedIn round-robin cursor), and `merge_from()` for GitHub Actions concurrency safety. |
| `telegram_notifier.py` | `TelegramNotifier` using Telegram Bot API HTML mode. `_SOURCE_PRESENTATIONS` maps source names to badges & link labels; escapes HTML text/URLs and adds Easy Apply screening reminder for LinkedIn alerts. |
| `linkedin_scraper.py` | `LinkedInJobScraper` (Guest API `seeMoreJobPostings` + `jobPosting/{id}`), adaptive 429 retry (`LINKEDIN_MAX_RETRIES=1`), title/geo/workplace classifiers reused across all scrapers. |
| `*_scraper.py` | Provider scrapers. **Enabled:** `djinni_scraper.py`, `dou_scraper.py`, `arbeitnow_scraper.py`, `greenhouse_scraper.py`, `lever_scraper.py`, `ashby_scraper.py`, `workable_scraper.py`, `smartrecruiters_scraper.py`, `himalayas_scraper.py`, `remotive_scraper.py`, `weworkremotely_scraper.py`, `jobicy_scraper.py`, `remoteok_scraper.py`, `workremotely_eu_scraper.py`, `techjobs_ie_scraper.py`, `workingnomads_scraper.py`, `irish_agencies_scraper.py` (`ReperioJobScraper`, `RealTimeJobScraper`, `ArcherJobScraper`). **Disabled (`ENABLE_* = False`):** `nofluff_scraper.py`, `justjoin_scraper.py`, `adzuna_scraper.py`. |
| `view_db.py` | CLI inspector (`--limit`, `--search`, `--csv`, `--html`) for `jobs_seen.db`. |
| `chrome-extension/` | Manifest V3 extension: `background.js` (Gemini API cover letters), `content.js` / `content.css` (DOU/Djinni/LinkedIn/ATS button injection), `popup.html` / `popup.js`, `universal-autofill.js` (frame-aware contact/address autofill), `tests/universal-autofill.test.js`. |
| `.github/workflows/tracker_cron.yml` | Cloud runner triggered via `workflow_dispatch` every ~30 min (external scheduler). Runs `python main.py` and merges/commits `jobs_seen.db` back to `main` (`[skip ci]`). |
| `.github/workflows/tests.yml` | CI quality gate on push/PR: runs `node --test chrome-extension/tests/universal-autofill.test.js` and `pytest --cov=. --cov-report=term-missing`. |
| `tests/` | Pytest suite (351 tests). `conftest.py` provides `memory_db`, `sample_job`, `linkedin_scraper`, and `notifier_*` fixtures. |

---

## 3. Critical Architectural Invariants

1. **LinkedIn runs LAST (`main.py`):**
   - All faster/non-throttled APIs & ATS boards run before LinkedIn so LinkedIn `429` backoff never delays their Telegram alerts.
2. **LinkedIn Cloud Rotation & `429` Protection (`config.py`, `main.py`, `database.py`):**
   - GitHub Actions `ubuntu-latest` IPs are heavily rate-limited by LinkedIn Guest API.
   - `SEARCH_KEYWORDS` has **2 compact boolean groups** (<= 4 phrases each) across **3 regions** (`TARGET_LOCATIONS = ["Ireland", "Europe", "Worldwide"]`).
   - `build_linkedin_rotation_queries()` interleaves regions across keyword groups (`[(loc, kw) for kw in keywords for loc in locations]`) -> **6 slots total** (~3-hour full cycle at 30-min Actions schedule; each region polled every ~1 hour).
   - Each scheduled run fetches **1 search page** (`max_pages=1`, `LINKEDIN_SEARCH_LIMIT=10`, matching LinkedIn Guest API's 10 cards/page) advancing `rotation_state` in `jobs_seen.db`.
   - Local filters (`db.is_seen`, `is_qa_title`, `is_location_blocked`) execute **before** `get_job_description()`.
   - Detail HTTP requests are capped (`LINKEDIN_MAX_DETAIL_FETCHES=8`, `1` in `--test`) and **halt immediately** (`detail_rate_limited = True`) on any exhausted `429`, leaving remaining candidates unseen rather than hammering LinkedIn.
3. **Never Mark Failed Deliveries as Seen:**
   - `_deliver_job_alert()` only calls `db.add_job(job)` on `dry_run=True` or when `notifier.send_job_alert(...)` returns `True`.
   - When `get_job_description()` hits `429` or `detail_rate_limited`/`max_detail_fetches` defers a card, it must NOT be added to `seen_jobs`.
4. **Git-Persisted State (`jobs_seen.db`):**
   - `jobs_seen.db` is committed to `main` by `tracker_cron.yml` via `JobDatabase.merge_from()`. Note that `rotation_state` updates on every scheduled `main.py` run, and `source_sync_state` enforces 1-hour minimum poll intervals for `jobicy`, `workremotely_eu`, `techjobs_ie`, `working_nomads`, `reperio`, `realtime`, `archer`, and `smartrecruiters`.
   - Always use `tmp_path` (`memory_db` fixture) in tests — never touch the repository's `jobs_seen.db`.
5. **CLI Side-Effect Note:**
   - `python main.py --dry-run` still writes processed jobs into `config.DATABASE_FILE` (`jobs_seen.db`), whereas `--test` pins LinkedIn rotation to index `0` without advancing `rotation_state`.
6. **Chrome Extension Constraints:**
   - Autofill is user-triggered only (`activeTab` + `optional_host_permissions`), supports accessible child frames, and **never** auto-submits forms.
   - Cover letter prompts enforce truthful non-hallucinating positioning and paste-ready text output only.

---

## 4. Common Commands

```bash
# Run Python unit test suite (351 tests)
pytest -q

# Run full Python test suite with coverage (CI gate)
pytest --cov=. --cov-report=term-missing

# Run Chrome extension autofill tests (requires Node.js 22+)
node --test chrome-extension/tests/universal-autofill.test.js

# Inspect seen jobs database
python view_db.py --limit 20
python view_db.py --search "Ireland"

# Smoke test (runs real scrapers with index 0 & limit=1, writes to local jobs_seen.db)
python main.py --test --dry-run
```

---

## 5. Git & Delivery Workflow

- Unless the user explicitly asks for read-only analysis or not to push, **always commit and push to `origin/main` automatically** once code/doc changes are verified by passing tests (`pytest -q`, plus `node --test chrome-extension/tests/universal-autofill.test.js` if `chrome-extension/` changed).
- Before committing/pushing, run `git fetch origin` and fast-forward (`git merge --ff-only origin/main`) so automated `jobs_seen.db` commits from `tracker_cron.yml` do not cause push conflicts; stage only the intended project files explicitly.
