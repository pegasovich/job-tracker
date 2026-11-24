# Changelog

Notable project changes are recorded here.

## [Unreleased]

### Added

- Add `Workable` (`workable_scraper.py`) and hourly-polled `SmartRecruiters` (`smartrecruiters_scraper.py`) direct ATS integrations, expand `LEVER_COMPANIES` from 5 to 11 active boards, and add Irish contract terms (`"Daily Rate"`, `"Day Rate"`, `"FTC"`) to LinkedIn contract queries in `config.py`.
- Add `Working Nomads` (`workingnomads_scraper.py`) and three Irish IT contract/remote agencies — `Reperio Human Capital`, `RealTime Recruitment`, and `Archer Recruitment` (`irish_agencies_scraper.py`) — with hourly polling, daily-rate extraction, and strict remote/Kerry-hybrid filtering.
- Add `AGENTS.md` with repository map, architecture invariants, LinkedIn rotation details, and verification commands for AI assistants and GitHub contributors.
- Add click-to-run contact autofill for blank name, email, phone, and country fields across sites, including accessible embedded application frames. Cross-origin form frames request access to their detected origin; the extension does not submit forms.
- Add a LinkedIn alert reminder to review Easy Apply screening questions and use accurate experience figures. The LinkedIn guest API does not expose employer-added screening questions, so the alert says they may be missing from the card.
- Add TechJobs.ie and WorkRemotely.eu as hourly-polled sources. Their parsers keep concise listing metadata, require QA/SDET titles and Ireland-compatible remote scope, and reject explicit hybrid/on-site roles; WorkRemotely.eu is limited to its Ireland contractor/freelance results.
- Widen LinkedIn discovery from the past 24 hours to the past 7 days, retaining newest-first sorting and database deduplication.
- Rotate LinkedIn through one location/keyword search page per half-hour Actions run across 4 compact boolean keyword groups interleaved over 3 regions (12 slots total, ~6h full cycle, up to 10 cards per page). Persist the cursor in `jobs_seen.db`, cap detail fetches (`LINKEDIN_MAX_DETAIL_FETCHES=8`), halt remaining detail requests on 429, and let other sources finish before LinkedIn's 429 retry.

### Fixed

- Consolidate duplicated non-LinkedIn scraper loops in `main.py` into `process_standard_jobs` and `_deliver_job_alert`, ensuring failed Telegram deliveries stay unseen for retry instead of being marked seen.
- Add missing `WorkRemotely.eu` presentation (alongside `TechJobs.ie`) in `telegram_notifier.py`, deduplicate source badge/link resolution, escape URLs cleanly, and format boolean search queries in `<code>` tags.
- Close SQLite connections deterministically in `database.py` and `view_db.py`, and restrict HTML export links in `view_db.py` to `http://` / `https://` schemes.
- Run LinkedIn searches after the other sources so its synchronous 429 retry delay does not postpone their Telegram alerts.
- Filter remote contractor listings when an explicit `Locations:` country list excludes Ireland and does not include a broader eligible region such as Europe, the EU, EMEA, or Worldwide. A B2B contract label alone no longer makes a country-restricted role eligible.
- Reject Himalayas and Remotive jobs restricted to another country, including the UK and the Netherlands. Ireland-specific and broad scopes such as Europe, EMEA, or Worldwide remain eligible; UK-only search results are removed from LinkedIn targets.
