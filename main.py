"""
Main Runner for LinkedIn Remote QA/SDET Job Tracker (Ireland).
"""

import argparse
import sys
import io
import time
import random
import logging
from typing import List, Dict, Optional, Callable

# Ensure UTF-8 stdout/stderr on Windows when running in a console
if sys.platform == "win32":
    if sys.stdout and hasattr(sys.stdout, "encoding") and sys.stdout.encoding:
        if sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr and hasattr(sys.stderr, "encoding") and sys.stderr.encoding:
        if sys.stderr.encoding.lower() != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure working directory is the script's directory
import os
from pathlib import Path
os.chdir(Path(__file__).parent.resolve())

def acquire_lock():
    """Prevent duplicate concurrent executions using a file lock (Windows msvcrt / POSIX fcntl)."""
    lock_file_path = Path(__file__).parent / "tracker.lock"
    try:
        lock_handle = open(lock_file_path, "w")
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            try:
                import fcntl
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (ImportError, AttributeError):
                pass
        return lock_handle
    except OSError:
        if sys.stdout:
            print("⚠️ Другой экземпляр трекера уже запущен. Пропуск запуска.")
        sys.exit(0)

import config
from config import is_polish_domestic_title
from linkedin_scraper import LinkedInJobScraper
from djinni_scraper import DjinniJobScraper, is_djinni_country_eligible
from dou_scraper import DouJobScraper
from nofluff_scraper import NoFluffJobScraper
from justjoin_scraper import JustJoinJobScraper
from adzuna_scraper import AdzunaJobScraper
from arbeitnow_scraper import ArbeitnowJobScraper
from greenhouse_scraper import GreenhouseJobScraper
from lever_scraper import LeverJobScraper
from ashby_scraper import AshbyJobScraper
from himalayas_scraper import HimalayasJobScraper, is_himalayas_location_eligible
from remotive_scraper import RemotiveJobScraper
from weworkremotely_scraper import WeWorkRemotelyJobScraper
from jobicy_scraper import JobicyJobScraper
from remoteok_scraper import RemoteOKJobScraper
from workremotely_eu_scraper import WorkRemotelyEUScraper
from techjobs_ie_scraper import TechJobsIEScraper
from workingnomads_scraper import WorkingNomadsJobScraper
from irish_agencies_scraper import ReperioJobScraper, RealTimeJobScraper, ArcherJobScraper
from workable_scraper import WorkableJobScraper
from smartrecruiters_scraper import SmartRecruitersJobScraper
from database import JobDatabase
from telegram_notifier import TelegramNotifier

log_handlers = [
    logging.FileHandler(Path(__file__).parent / "tracker.log", encoding="utf-8")
]
if sys.stdout is not None:
    log_handlers.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=log_handlers,
)
logger = logging.getLogger("Tracker")


def is_hybrid_nearby(job_location: str) -> bool:
    """
    Check if a hybrid job's location is close enough to Cahersiveen, Co. Kerry.
    Returns True if the location matches any pattern in HYBRID_ALLOWED_LOCATIONS.
    """
    loc_lower = job_location.lower()
    for pattern in config.HYBRID_ALLOWED_LOCATIONS:
        if pattern in loc_lower:
            return True
    return False


def log_and_track_batch(source_name: str, jobs: List[Dict], db: JobDatabase) -> tuple[int, int]:
    """
    Log clear status of scraped cards: how many total, how many already seen in db,
    and how many are new candidates for filtering.
    Returns (already_seen_count, new_candidates_count).
    """
    total = len(jobs)
    if total == 0:
        logger.info(f"[{source_name}] Найдено карточек: 0")
        return 0, 0
    seen = sum(1 for j in jobs if db.is_seen(j.get("id", "")))
    new_cand = total - seen
    if seen == total:
        logger.info(f"[{source_name}] Найдено карточек: {total} (все {total} уже есть в базе jobs_seen.db — пропуск повторов)")
    elif seen > 0:
        logger.info(f"[{source_name}] Найдено карточек: {total} ({seen} уже в базе, {new_cand} новых отправлены на проверку фильтрами)")
    else:
        logger.info(f"[{source_name}] Найдено карточек: {total} (все {total} новые, отправлены на проверку фильтрами)")
    return seen, new_cand


def _deliver_job_alert(
    source_name: str,
    job: Dict,
    snippet: str,
    workplace_type: str,
    db: JobDatabase,
    notifier: TelegramNotifier,
    dry_run: bool,
    region_label: str = "",
) -> bool:
    """Print (dry-run) or send a Telegram alert and persist only on successful delivery."""
    logger.info("✨ [%s] Новая вакансия [%s] (%s): %s @ %s", source_name, job["id"], workplace_type, job["title"], job["company"])
    if dry_run:
        header_meta = f"{workplace_type.upper()} | {region_label}" if region_label else workplace_type.upper()
        print("\n" + "=" * 60)
        print(f"[DRY RUN / {source_name}] Новая вакансия ({header_meta}):")
        print(f"Позиция: {job['title']}")
        print(f"Компания: {job['company']}")
        print(f"Локация: {job['location']}")
        if job.get("employment_type"):
            print(f"Тип: {job['employment_type']}")
        if job.get("salary"):
            print(f"Зарплата: {job['salary']}")
        print(f"Ссылка: {job['url']}")
        if snippet:
            print(f"Фрагмент описания: {snippet[:200]}...")
        print("=" * 60 + "\n")
        db.add_job(job)
        return True

    if notifier.send_job_alert(job, snippet=snippet, workplace_type=workplace_type):
        logger.info("✅ Отправлено в Telegram: %s", job["id"])
        db.add_job(job)
        time.sleep(1.5)
        return True

    # Leave unseen so the next scheduled run can retry delivery.
    logger.error("❌ Ошибка отправки в Telegram: %s; вакансия будет повторно проверена", job["id"])
    return False


def process_standard_jobs(
    source_name: str,
    jobs: List[Dict],
    db: JobDatabase,
    notifier: TelegramNotifier,
    dry_run: bool,
    *,
    require_confirmed_remote: bool = False,
    check_location_geo: bool = True,
    check_description_geo: bool = True,
    check_language: bool = True,
    check_polish: bool = True,
    allow_nearby_hybrid: bool = False,
    extra_filter: Optional[Callable[[Dict], str]] = None,
) -> tuple[int, int]:
    """Filter, deduplicate, and deliver alerts for a non-LinkedIn scraper batch."""
    new_count = 0
    filtered_count = 0

    for job in jobs:
        job_id = job["id"]
        if db.is_seen(job_id):
            continue

        title = job.get("title", "")
        location = job.get("location", "")
        description = job.get("description", "")
        workplace_type = job.get("workplace_type", "remote")

        reason = ""
        if not LinkedInJobScraper.is_qa_title(title):
            reason = "not a QA/SDET role"
        elif require_confirmed_remote and workplace_type != "remote":
            reason = "not confirmed fully remote"
        elif check_polish and getattr(config, "EXCLUDE_POLISH_DOMESTIC_ROLES", True) and is_polish_domestic_title(title):
            reason = "Polish domestic role"
        elif check_location_geo and LinkedInJobScraper.is_location_blocked(location):
            reason = "location is incompatible"
        elif check_description_geo and LinkedInJobScraper.is_description_blocked(description):
            reason = "description restricts candidate location"
        elif check_language and config.has_non_allowed_language_requirement(f"{title} {description}"):
            reason = "requires a non-English language"
        elif workplace_type == "hybrid" and not config.ALLOW_HYBRID:
            if allow_nearby_hybrid and is_hybrid_nearby(location):
                logger.info("✅ [ГИБРИД РЯДОМ / %s] Пропущена через фильтр: %s @ %s (%s)", source_name, title, job.get("company"), location)
            else:
                reason = "hybrid role outside allowed area"

        if not reason and extra_filter is not None:
            reason = extra_filter(job) or ""

        if reason:
            logger.info("🚫 [%s] Пропуск (%s): %s @ %s", source_name, reason, title, job.get("company"))
            filtered_count += 1
            db.add_job(job)
            continue

        snippet = description[:350].rstrip() + "..." if len(description) > 350 else description
        if _deliver_job_alert(source_name, job, snippet, workplace_type, db, notifier, dry_run):
            new_count += 1

    return new_count, filtered_count


def process_remote_feed_jobs(source_name: str, jobs: List[Dict], db: JobDatabase,
                             notifier: TelegramNotifier, dry_run: bool) -> tuple[int, int]:
    """Apply the shared QA/remote filters and deliver jobs from remote-only feeds."""
    return process_standard_jobs(
        source_name,
        jobs,
        db,
        notifier,
        dry_run,
        require_confirmed_remote=True,
    )


def build_linkedin_rotation_queries(locations: List[str], keywords: List[str]) -> List[tuple[str, str]]:
    """Interleave regions across keyword groups so every region is polled evenly."""
    return [(loc, kw) for kw in keywords for loc in locations]


def process_linkedin_jobs(
    jobs: List[Dict],
    location: str,
    scraper: LinkedInJobScraper,
    db: JobDatabase,
    notifier: TelegramNotifier,
    dry_run: bool,
    max_detail_fetches: int = 8,
) -> tuple[int, int]:
    """Filter, fetch details with 429 protection, and notify on unseen LinkedIn cards."""
    new_count = 0
    filtered_count = 0
    detail_fetches = 0
    detail_rate_limited = False
    detail_cap_logged = False

    for job in jobs:
        job_id = job["id"]
        job["region"] = location
        if db.is_seen(job_id):
            continue

        # Level 0: Validate role title locally (0 HTTP requests)
        if not scraper.is_qa_title(job.get("title", "")):
            logger.info(
                f"🚫 [НЕ QA РОЛЬ] Отклонена по названию: '{job['title']}' @ {job['company']}"
            )
            filtered_count += 1
            db.add_job(job)
            continue

        # Level 1: Geo-filter card locally before spending a detail HTTP request
        if scraper.is_location_blocked(job.get("location", "")):
            logger.info(
                f"🚫 [ГЕО-БЛОКИРОВКА] Отклонена по локации: {job['title']} @ {job['company']} (Локация: {job['location']})"
            )
            filtered_count += 1
            db.add_job(job)
            continue

        if detail_rate_limited:
            continue

        if detail_fetches >= max_detail_fetches:
            if not detail_cap_logged:
                logger.info(
                    "⏸️ Достигнут лимит запросов описаний LinkedIn (%s) за запуск; "
                    "остальные новые карточки оставлены до следующего цикла.",
                    max_detail_fetches,
                )
                detail_cap_logged = True
            continue

        time.sleep(random.uniform(1.5, 2.5))
        detail_fetches += 1
        full_desc = scraper.get_job_description(job_id)
        if not full_desc and getattr(scraper, "last_hit_rate_limit", False):
            detail_rate_limited = True
            logger.warning(
                f"⏳ Пропускаем вакансию '{job['title']}' @ {job['company']} из-за лимита 429 LinkedIn "
                "(дальнейшие запросы описаний в этом запуске остановлены)."
            )
            continue

        snippet = full_desc[:350].rstrip() + "..." if len(full_desc) > 350 else full_desc
        workplace_type = scraper.detect_workplace_type(job["title"], job["location"], full_desc)

        if workplace_type == "onsite" and not config.ALLOW_ONSITE:
            logger.info(
                f"🚫 [СТРОГИЙ ФИЛЬТР] Отклонена On-site вакансия: {job['title']} @ {job['company']} (Локация: {job['location']})"
            )
            filtered_count += 1
            db.add_job(job)
            continue

        if workplace_type == "hybrid" and not config.ALLOW_HYBRID:
            if is_hybrid_nearby(job["location"]):
                logger.info(
                    f"✅ [ГИБРИД РЯДОМ] Пропущена через фильтр: {job['title']} @ {job['company']} (Локация: {job['location']})"
                )
            else:
                logger.info(
                    f"🚫 [СТРОГИЙ ФИЛЬТР] Отклонена Hybrid вакансия (далеко): {job['title']} @ {job['company']} (Локация: {job['location']})"
                )
                filtered_count += 1
                db.add_job(job)
                continue

        if workplace_type == "unclear":
            loc_stripped = job.get("location", "").strip().lower()
            is_generic_ireland = loc_stripped in ("ireland", "")
            if not is_generic_ireland and not is_hybrid_nearby(job.get("location", "")):
                logger.info(
                    f"🚫 [СТРОГИЙ ФИЛЬТР] Отклонена вакансия с неясным форматом: {job['title']} @ {job['company']} (Локация: {job['location']})"
                )
                filtered_count += 1
                db.add_job(job)
                continue
            logger.info(
                f"🟡 [UNCLEAR → ПРОПУСК] Вакансия с неясным форматом, но generic Ireland/nearby: {job['title']} @ {job['company']} (Локация: {job['location']})"
            )

        if _deliver_job_alert("LinkedIn", job, snippet, workplace_type, db, notifier, dry_run, region_label=location):
            new_count += 1

    return new_count, filtered_count


def run_tracker(dry_run: bool = False, test_mode: bool = False):
    locations = config.TARGET_LOCATIONS if not test_mode else [config.TARGET_LOCATIONS[0]]
    logger.info(f"--- Запуск трекера вакансий (Регионы: {', '.join(locations)}, Remote={config.REMOTE_ONLY}) ---")

    db = JobDatabase(config.DATABASE_FILE)
    notifier = TelegramNotifier(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)

    if not dry_run and not notifier.is_configured:
        logger.warning(
            "⚠️ Telegram bot не настроен (TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID не заполнены в .env)."
        )
        logger.warning("Запуск переведён в режим --dry-run (вывод только в консоль).")
        dry_run = True

    total_scanned = 0
    total_already_seen = 0
    total_filtered = 0
    total_new = 0
    keywords = config.SEARCH_KEYWORDS if not test_mode else [config.SEARCH_KEYWORDS[0]]

    def collect_and_process(source_name: str, jobs: List[Dict], **process_kwargs):
        nonlocal total_scanned, total_already_seen, total_new, total_filtered
        seen_cnt, _ = log_and_track_batch(source_name, jobs, db)
        total_scanned += len(jobs)
        total_already_seen += seen_cnt
        new_count, filtered_count = process_standard_jobs(
            source_name, jobs, db, notifier, dry_run, **process_kwargs
        )
        total_new += new_count
        total_filtered += filtered_count

    # --- Djinni.co ---
    if config.ENABLE_DJINNI:
        djinni = DjinniJobScraper()
        djinni_keywords = config.DJINNI_KEYWORDS if not test_mode else [config.DJINNI_KEYWORDS[0]]
        user_countries = getattr(config, "DJINNI_USER_COUNTRIES", ["IE", "IRL", "IRELAND"])
        user_regions = getattr(config, "DJINNI_USER_REGIONS", ["EUROPE", "EU", "WORLDWIDE", "ANY", "ALL"])

        def _djinni_extra(job: Dict) -> str:
            if getattr(config, "DJINNI_COUNTRY_FILTER", True) and not is_djinni_country_eligible(
                job, user_countries=user_countries, user_regions=user_regions
            ):
                return "country is ineligible for Ireland"
            return ""

        for kw in djinni_keywords:
            logger.info(f"🟢 Поиск на Djinni.co по слову: '{kw}'...")
            max_pages = getattr(config, "DJINNI_MAX_PAGES", 5)
            limit = getattr(config, "DJINNI_LIMIT", 60)
            djinni_jobs = djinni.search_jobs(keyword=kw, max_pages=max_pages, limit=limit)
            collect_and_process(
                f"Djinni / {kw}",
                djinni_jobs,
                allow_nearby_hybrid=True,
                extra_filter=_djinni_extra,
            )
            time.sleep(2.0)

    # --- DOU (jobs.dou.ua) ---
    if getattr(config, "ENABLE_DOU", True):
        dou = DouJobScraper()
        dou_category = getattr(config, "DOU_CATEGORY", "QA")
        dou_remote = getattr(config, "DOU_REMOTE_ONLY", True)
        dou_limit = getattr(config, "DOU_LIMIT", 50) if not test_mode else 10
        logger.info(f"🟡 Поиск на DOU (jobs.dou.ua, Категория: {dou_category}, Remote={dou_remote})...")
        dou_jobs = dou.search_jobs(category=dou_category, remote_only=dou_remote, limit=dou_limit)
        collect_and_process("DOU", dou_jobs)

    # --- No Fluff Jobs (nofluffjobs.com) ---
    if getattr(config, "ENABLE_NOFLUFF", True):
        nofluff = NoFluffJobScraper()
        nfj_category = getattr(config, "NOFLUFF_CATEGORY", "testing")
        nfj_remote = getattr(config, "NOFLUFF_REMOTE_ONLY", True)
        nfj_currency = getattr(config, "NOFLUFF_CURRENCY", "EUR")
        nfj_limit = getattr(config, "NOFLUFF_LIMIT", 50) if not test_mode else 10
        logger.info(f"🔴 Поиск на No Fluff Jobs (Категория: {nfj_category}, Remote={nfj_remote}, Валюта={nfj_currency})...")
        nfj_jobs = nofluff.search_jobs(category=nfj_category, remote_only=nfj_remote, currency=nfj_currency, limit=nfj_limit)
        collect_and_process(
            "No Fluff Jobs",
            nfj_jobs,
            check_location_geo=False,
            check_description_geo=False,
        )

    # --- JustJoin.it (justjoin.it) ---
    if getattr(config, "ENABLE_JUSTJOIN", True):
        justjoin = JustJoinJobScraper()
        jjit_category = getattr(config, "JUSTJOIN_CATEGORY", "testing")
        jjit_remote = getattr(config, "JUSTJOIN_REMOTE_ONLY", True)
        jjit_currency = getattr(config, "JUSTJOIN_CURRENCY", "EUR")
        jjit_pages = getattr(config, "JUSTJOIN_MAX_PAGES", 3) if not test_mode else 1
        jjit_limit = getattr(config, "JUSTJOIN_LIMIT", 30) if not test_mode else 10
        logger.info(f"🟣 Поиск на JustJoin.it (Категория: {jjit_category}, Remote={jjit_remote}, Валюта={jjit_currency})...")
        jjit_jobs = justjoin.search_jobs(
            category=jjit_category,
            remote_only=jjit_remote,
            currency=jjit_currency,
            max_pages=jjit_pages,
            limit=jjit_limit,
        )
        collect_and_process(
            "JustJoin.it",
            jjit_jobs,
            check_location_geo=False,
            check_description_geo=False,
        )

    # --- Adzuna (api.adzuna.com) ---
    if getattr(config, "ENABLE_ADZUNA", True):
        adzuna = AdzunaJobScraper()
        if not adzuna.is_configured:
            logger.info("ℹ️ Adzuna API не настроен (ADZUNA_APP_ID или ADZUNA_APP_KEY не заполнены в .env). Пропуск.")
        else:
            adzuna_kws = getattr(config, "ADZUNA_KEYWORDS", ["QA Engineer", "SDET"]) if not test_mode else [getattr(config, "ADZUNA_KEYWORDS", ["QA Engineer"])[0]]
            adzuna_remote = getattr(config, "ADZUNA_REMOTE_ONLY", True)
            adzuna_pages = getattr(config, "ADZUNA_MAX_PAGES", 1)
            adzuna_limit = getattr(config, "ADZUNA_RESULTS_PER_PAGE", 20) if not test_mode else 10
            logger.info(f"🟧 Поиск на Adzuna (Страны: {', '.join(adzuna.countries)}, Remote={adzuna_remote})...")
            adzuna_jobs = adzuna.search_jobs(
                keywords=adzuna_kws,
                remote_only=adzuna_remote,
                max_pages=adzuna_pages,
                results_per_page=adzuna_limit,
            )
            collect_and_process(
                "Adzuna",
                adzuna_jobs,
                check_location_geo=False,
                check_description_geo=False,
            )

    # --- Arbeitnow (arbeitnow.com) ---
    if getattr(config, "ENABLE_ARBEITNOW", True):
        arbeitnow = ArbeitnowJobScraper()
        an_remote = getattr(config, "ARBEITNOW_REMOTE_ONLY", True)
        an_pages = getattr(config, "ARBEITNOW_MAX_PAGES", 2) if not test_mode else 1
        an_limit = getattr(config, "ARBEITNOW_LIMIT", 50) if not test_mode else 10
        logger.info(f"🌐 Поиск на Arbeitnow (Remote={an_remote}, Страниц: {an_pages})...")
        an_jobs = arbeitnow.search_jobs(remote_only=an_remote, max_pages=an_pages, limit=an_limit)
        collect_and_process("Arbeitnow", an_jobs)

    # --- Greenhouse (Direct Company ATS) ---
    if getattr(config, "ENABLE_GREENHOUSE", True):
        gh_companies = getattr(config, "GREENHOUSE_COMPANIES", ["canonical", "cloudflare"])
        gh_remote = getattr(config, "GREENHOUSE_REMOTE_ONLY", True)
        gh_limit = getattr(config, "GREENHOUSE_LIMIT_PER_COMPANY", 30) if not test_mode else 10
        target_comps = gh_companies if not test_mode else [gh_companies[0]]
        logger.info(f"🌱 Поиск в Greenhouse ATS (Компаний: {len(target_comps)}, Remote={gh_remote})...")
        greenhouse = GreenhouseJobScraper(companies=target_comps)
        gh_jobs = greenhouse.search_jobs(remote_only=gh_remote, limit_per_company=gh_limit)
        collect_and_process("Greenhouse", gh_jobs)

    # --- Lever (Direct Company ATS) ---
    if getattr(config, "ENABLE_LEVER", True):
        lever_companies = getattr(config, "LEVER_COMPANIES", ["palantir", "spotify"])
        lever_remote = getattr(config, "LEVER_REMOTE_ONLY", True)
        lever_limit = getattr(config, "LEVER_LIMIT_PER_COMPANY", 30) if not test_mode else 10
        target_lever_comps = lever_companies if not test_mode else [lever_companies[0]]
        logger.info(f"⚡ Поиск в Lever ATS (Компаний: {len(target_lever_comps)}, Remote={lever_remote})...")
        lever = LeverJobScraper(companies=target_lever_comps)
        lever_jobs = lever.search_jobs(remote_only=lever_remote, limit_per_company=lever_limit)
        collect_and_process("Lever", lever_jobs)

    # --- Ashby (Direct Company ATS) ---
    if getattr(config, "ENABLE_ASHBY", True):
        ashby_companies = getattr(config, "ASHBY_COMPANIES", ["linear", "synthesia", "posthog"])
        ashby_remote = getattr(config, "ASHBY_REMOTE_ONLY", True)
        ashby_limit = getattr(config, "ASHBY_LIMIT_PER_COMPANY", 30) if not test_mode else 10
        target_ashby_comps = ashby_companies if not test_mode else [ashby_companies[0]]
        logger.info(f"🪐 Поиск в Ashby ATS (Компаний: {len(target_ashby_comps)}, Remote={ashby_remote})...")
        ashby = AshbyJobScraper(companies=target_ashby_comps)
        ashby_jobs = ashby.search_jobs(remote_only=ashby_remote, limit_per_company=ashby_limit)
        collect_and_process("Ashby", ashby_jobs)

    # --- Workable (Direct Company ATS) ---
    if getattr(config, "ENABLE_WORKABLE", True):
        workable_companies = getattr(config, "WORKABLE_COMPANIES", ["tekenable", "zyte", "seeq"])
        workable_remote = getattr(config, "WORKABLE_REMOTE_ONLY", True)
        workable_limit = getattr(config, "WORKABLE_LIMIT_PER_COMPANY", 30) if not test_mode else 10
        target_workable_comps = workable_companies if not test_mode else [workable_companies[0]]
        logger.info(f"🧩 Поиск в Workable ATS (Компаний: {len(target_workable_comps)}, Remote={workable_remote})...")
        workable = WorkableJobScraper(companies=target_workable_comps)
        workable_jobs = workable.search_jobs(remote_only=workable_remote, limit_per_company=workable_limit)
        collect_and_process("Workable", workable_jobs)

    # --- SmartRecruiters (Direct Company ATS, hourly polled) ---
    if getattr(config, "ENABLE_SMARTRECRUITERS", True):
        sr_interval = getattr(config, "SMARTRECRUITERS_POLL_INTERVAL_SECONDS", 3600)
        if db.claim_source_poll("smartrecruiters", min_interval_seconds=sr_interval):
            sr_companies = getattr(config, "SMARTRECRUITERS_COMPANIES", ["Mirantis", "Wise"])
            sr_remote = getattr(config, "SMARTRECRUITERS_REMOTE_ONLY", True)
            sr_limit = getattr(config, "SMARTRECRUITERS_LIMIT_PER_COMPANY", 20) if not test_mode else 5
            sr_queries = getattr(config, "SMARTRECRUITERS_QUERIES", ["QA", "SDET", "Test"])
            target_sr_comps = sr_companies if not test_mode else [sr_companies[0]]
            if test_mode:
                sr_queries = [sr_queries[0]]
            logger.info(f"🏢 Поиск в SmartRecruiters ATS (Компаний: {len(target_sr_comps)}, Remote={sr_remote})...")
            sr = SmartRecruitersJobScraper(companies=target_sr_comps)
            sr_jobs = sr.search_jobs(queries=sr_queries, remote_only=sr_remote, limit_per_company=sr_limit)
            collect_and_process("SmartRecruiters", sr_jobs)
        else:
            logger.info("[SmartRecruiters] Пропуск опроса: источник опрашивался менее часа назад.")

    # --- Remotive (remotive.com API) ---
    if getattr(config, "ENABLE_REMOTIVE", True):
        remotive_cat = getattr(config, "REMOTIVE_CATEGORY", "qa")
        remotive_remote = getattr(config, "REMOTIVE_REMOTE_ONLY", True)
        remotive_limit = getattr(config, "REMOTIVE_LIMIT", 50) if not test_mode else 10
        logger.info(f"🚀 Поиск на Remotive (Category={remotive_cat}, Remote={remotive_remote})...")
        remotive = RemotiveJobScraper(category=remotive_cat)
        remotive_jobs = remotive.search_jobs(category=remotive_cat, remote_only=remotive_remote, limit=remotive_limit)
        collect_and_process("Remotive", remotive_jobs)

    # --- WeWorkRemotely (weworkremotely.com RSS) ---
    if getattr(config, "ENABLE_WEWORKREMOTELY", True):
        wwr_limit = getattr(config, "WEWORKREMOTELY_LIMIT", 50) if not test_mode else 10
        logger.info("💼 Поиск на WeWorkRemotely RSS...")
        wwr = WeWorkRemotelyJobScraper()
        wwr_jobs = wwr.search_jobs(remote_only=True, limit=wwr_limit)
        collect_and_process("WeWorkRemotely", wwr_jobs)

    # --- Himalayas (himalayas.app API) ---
    if getattr(config, "ENABLE_HIMALAYAS", True):
        himalayas_max_pages = getattr(config, "HIMALAYAS_MAX_PAGES", 5) if not test_mode else 1
        himalayas_limit = getattr(config, "HIMALAYAS_LIMIT", 50) if not test_mode else 10
        logger.info(f"🏔️ Поиск на Himalayas API (Страниц: {himalayas_max_pages})...")
        himalayas = HimalayasJobScraper(max_pages=himalayas_max_pages)
        himalayas_jobs = himalayas.search_jobs(remote_only=True, limit=himalayas_limit)
        collect_and_process("Himalayas", himalayas_jobs)

    # --- Jobicy public API ---
    if getattr(config, "ENABLE_JOBICY", True):
        if db.claim_source_poll("jobicy", min_interval_seconds=3600):
            logger.info("🟠 Поиск на Jobicy API...")
            jobicy = JobicyJobScraper()
            jobicy_jobs = jobicy.search_jobs(
                tags=getattr(config, "JOBICY_TAGS", ["QA", "SDET", "test automation"]),
                limit=getattr(config, "JOBICY_LIMIT", 100) if not test_mode else 20,
            )
            collect_and_process("Jobicy", jobicy_jobs, require_confirmed_remote=True)
        else:
            logger.info("[Jobicy] Пропуск опроса: предыдущий запрос был менее часа назад.")

    # --- Remote OK public API ---
    if getattr(config, "ENABLE_REMOTEOK", True):
        logger.info("🌍 Поиск на Remote OK API...")
        remoteok = RemoteOKJobScraper()
        remoteok_jobs = remoteok.search_jobs(
            tags=getattr(config, "REMOTEOK_TAGS", ["qa", "sdet", "test-automation"]),
            limit=getattr(config, "REMOTEOK_LIMIT", 50) if not test_mode else 10,
        )
        collect_and_process("Remote OK", remoteok_jobs, require_confirmed_remote=True)

    # --- WorkRemotely.eu Ireland contractor/freelance results ---
    if getattr(config, "ENABLE_WORKREMOTELY_EU", True):
        poll_interval = getattr(config, "WORKREMOTELY_EU_POLL_INTERVAL_SECONDS", 3600)
        if db.claim_source_poll("workremotely_eu", min_interval_seconds=poll_interval):
            logger.info("🔎 Поиск QA/SDET контрактов WorkRemotely.eu (Ireland eligibility)...")
            source = WorkRemotelyEUScraper()
            limit = getattr(config, "WORKREMOTELY_EU_LIMIT", 50) if not test_mode else 10
            jobs = source.search_jobs(limit=limit)
            collect_and_process("WorkRemotely.eu", jobs, require_confirmed_remote=True)
        else:
            logger.info("[WorkRemotely.eu] Пропуск опроса: источник опрашивался менее часа назад.")

    # --- TechJobs.ie Irish QA board ---
    if getattr(config, "ENABLE_TECHJOBS_IE", True):
        poll_interval = getattr(config, "TECHJOBS_IE_POLL_INTERVAL_SECONDS", 3600)
        if db.claim_source_poll("techjobs_ie", min_interval_seconds=poll_interval):
            logger.info("🇮🇪 Поиск удалённых QA/SDET вакансий TechJobs.ie...")
            source = TechJobsIEScraper()
            limit = getattr(config, "TECHJOBS_IE_LIMIT", 50) if not test_mode else 10
            jobs = source.search_jobs(limit=limit)
            collect_and_process("TechJobs.ie", jobs, require_confirmed_remote=True)
        else:
            logger.info("[TechJobs.ie] Пропуск опроса: источник опрашивался менее часа назад.")

    # --- Working Nomads public JSON feed ---
    if getattr(config, "ENABLE_WORKING_NOMADS", True):
        poll_interval = getattr(config, "WORKING_NOMADS_POLL_INTERVAL_SECONDS", 3600)
        if db.claim_source_poll("working_nomads", min_interval_seconds=poll_interval):
            logger.info("🧳 Поиск на Working Nomads API...")
            source = WorkingNomadsJobScraper()
            limit = getattr(config, "WORKING_NOMADS_LIMIT", 50) if not test_mode else 10
            jobs = source.search_jobs(limit=limit)
            collect_and_process("Working Nomads", jobs, require_confirmed_remote=True)
        else:
            logger.info("[Working Nomads] Пропуск опроса: источник опрашивался менее часа назад.")

    # --- Irish IT recruitment agencies (Reperio, RealTime, Archer) ---
    irish_agency_specs = (
        ("reperio", "Reperio", "ENABLE_REPERIO", ReperioJobScraper, "REPERIO_KEYWORDS"),
        ("realtime", "RealTime", "ENABLE_REALTIME", RealTimeJobScraper, "REALTIME_KEYWORDS"),
        ("archer", "Archer", "ENABLE_ARCHER", ArcherJobScraper, "ARCHER_KEYWORDS"),
    )
    agency_poll_interval = getattr(config, "IRISH_AGENCIES_POLL_INTERVAL_SECONDS", 3600)
    agency_limit = getattr(config, "IRISH_AGENCIES_LIMIT", 30) if not test_mode else 10
    for poll_key, label, flag_name, scraper_cls, kw_attr in irish_agency_specs:
        if not getattr(config, flag_name, True):
            continue
        if not db.claim_source_poll(poll_key, min_interval_seconds=agency_poll_interval):
            logger.info("[%s] Пропуск опроса: источник опрашивался менее часа назад.", label)
            continue
        logger.info("🇮🇪 Поиск QA/SDET ролей в ирландском агентстве %s...", label)
        kws = getattr(config, kw_attr, ["QA", "Test", "SDET", "Automation"])
        if test_mode:
            kws = [kws[0]]
        jobs = scraper_cls().search_jobs(keywords=kws, limit=agency_limit)
        collect_and_process(label, jobs, allow_nearby_hybrid=True)

    # --- One LinkedIn query per scheduled run; rotate across keyword groups and regions ---
    linkedin_queries = build_linkedin_rotation_queries(locations, keywords)
    if linkedin_queries:
        query_index = (
            0
            if test_mode
            else db.claim_next_rotation_index("linkedin_search", len(linkedin_queries))
        )
        selected_location, selected_keyword = linkedin_queries[query_index]
        logger.info(
            "🔄 LinkedIn-ротация: запрос %s/%s (регион '%s', слово '%s')",
            query_index + 1,
            len(linkedin_queries),
            selected_location,
            selected_keyword,
        )
        linkedin_locations = [selected_location]
        linkedin_keywords = [selected_keyword]
    else:
        linkedin_locations = []
        linkedin_keywords = []

    # --- LinkedIn searches run last so a 429 cannot delay other sources ---
    for loc in linkedin_locations:
        scraper = LinkedInJobScraper(
            location=loc,
            remote_only=config.REMOTE_ONLY,
            time_filter=getattr(config, "LINKEDIN_TIME_FILTER", "r86400"),
            sort_by=getattr(config, "LINKEDIN_SORT_BY", "DD"),
        )
        for kw in linkedin_keywords:
            search_limit = getattr(config, "LINKEDIN_SEARCH_LIMIT", 10) if not test_mode else 1
            max_detail_fetches = getattr(config, "LINKEDIN_MAX_DETAIL_FETCHES", 8) if not test_mode else 1
            logger.info(f"🔍 Поиск в регионе '{loc}' по слову: '{kw}'...")
            jobs = scraper.search_jobs(keyword=kw, limit=search_limit, max_pages=1)
            seen_cnt, _ = log_and_track_batch(f"{loc} / {kw}", jobs, db)
            total_scanned += len(jobs)
            total_already_seen += seen_cnt

            new_cnt, filtered_cnt = process_linkedin_jobs(
                jobs=jobs,
                location=loc,
                scraper=scraper,
                db=db,
                notifier=notifier,
                dry_run=dry_run,
                max_detail_fetches=max_detail_fetches,
            )
            total_new += new_cnt
            total_filtered += filtered_cnt

            if scraper.last_hit_rate_limit and not jobs:
                logger.warning(
                    "⚠️ LinkedIn не отдал результаты после повтора 429; "
                    "текущий слот ротации пропущен до следующего цикла."
                )

    logger.info("=" * 80)
    logger.info("🏁 Проверка всех источников завершена успешно!")
    logger.info("📊 ИТОГИ ЗАПУСКА:")
    logger.info(f"   • Всего карточек просканировано: {total_scanned}")
    logger.info(f"   • Ранее уже были в базе (пропущены без повторного спама): {total_already_seen}")
    logger.info(f"   • Отклонено фильтрами (не QA / Onsite / гео-ограничения): {total_filtered}")
    logger.info(f"   • Новых вакансий отправлено в Telegram: {total_new}")
    logger.info(f"   • Всего записей в базе данных jobs_seen.db: {db.count_seen()}")
    logger.info("=" * 80)
    return total_new


def main():
    _lock_handle = acquire_lock()
    parser = argparse.ArgumentParser(description="LinkedIn Remote QA/SDET Job Tracker (Ireland)")
    parser.add_argument("--dry-run", action="store_true", help="Только показать найденное в консоли, не слать в Telegram")
    parser.add_argument("--test", action="store_true", help="Быстрый тест (только один поисковый запрос)")
    parser.add_argument("--interval", type=int, default=0, help="Запускать циклически каждые N минут (0 = один запуск)")

    args = parser.parse_args()

    if args.interval > 0:
        logger.info(f"Запущен режим мониторинга. Интервал проверки: {args.interval} минут.")
        while True:
            try:
                run_tracker(dry_run=args.dry_run, test_mode=args.test)
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}", exc_info=True)
            logger.info(f"Ожидание {args.interval} мин до следующей проверки...")
            time.sleep(args.interval * 60)
    else:
        run_tracker(dry_run=args.dry_run, test_mode=args.test)


if __name__ == "__main__":
    main()
