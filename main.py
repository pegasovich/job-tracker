"""
Main Runner for LinkedIn Remote QA/SDET Job Tracker (Ireland).
"""

import argparse
import sys
import io
import time
import random
import logging
from typing import List, Dict

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


def process_remote_feed_jobs(source_name: str, jobs: List[Dict], db: JobDatabase,
                             notifier: TelegramNotifier, dry_run: bool) -> tuple[int, int]:
    """Apply the shared QA/remote filters and deliver jobs from remote-only feeds."""
    new_count = 0
    filtered_count = 0
    for job in jobs:
        job_id = job["id"]
        if db.is_seen(job_id):
            continue

        description = job.get("description", "")
        reason = ""
        if not LinkedInJobScraper.is_qa_title(job.get("title", "")):
            reason = "not a QA/SDET role"
        elif job.get("workplace_type") != "remote":
            reason = "not confirmed fully remote"
        elif LinkedInJobScraper.is_location_blocked(job.get("location", "")):
            reason = "location is incompatible"
        elif LinkedInJobScraper.is_description_blocked(description):
            reason = "description restricts candidate location"
        elif config.has_non_allowed_language_requirement(f"{job.get('title', '')} {description}"):
            reason = "requires a non-English language"
        elif config.EXCLUDE_POLISH_DOMESTIC_ROLES and is_polish_domestic_title(job.get("title", "")):
            reason = "Polish domestic role"

        if reason:
            logger.info("🚫 [%s] Пропуск (%s): %s @ %s", source_name, reason, job.get("title"), job.get("company"))
            filtered_count += 1
            db.add_job(job)
            continue

        snippet = description[:350].rstrip()
        if len(description) > 350:
            snippet += "..."
        logger.info("✨ [%s] Новая вакансия (remote): %s @ %s", source_name, job["title"], job["company"])
        if dry_run:
            print("\n" + "=" * 60)
            print(f"[DRY RUN / {source_name}] Новая удалённая вакансия:")
            print(f"Позиция: {job['title']}\nКомпания: {job['company']}\nЛокация: {job['location']}")
            if job.get("employment_type"):
                print(f"Тип: {job['employment_type']}")
            if job.get("salary"):
                print(f"Зарплата: {job['salary']}")
            print(f"Ссылка: {job['url']}")
            if snippet:
                print(f"Фрагмент описания: {snippet[:200]}")
            print("=" * 60 + "\n")
            db.add_job(job)
        elif notifier.send_job_alert(job, snippet=snippet, workplace_type="remote"):
            logger.info("✅ Отправлено в Telegram: %s", job_id)
            db.add_job(job)
            time.sleep(1.5)
        else:
            # Leave it unseen so the next scheduled scan can retry the notification.
            logger.error("❌ Ошибка отправки в Telegram: %s; вакансия будет повторно проверена", job_id)
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

    for loc in locations:
        scraper = LinkedInJobScraper(
            location=loc,
            remote_only=config.REMOTE_ONLY,
            time_filter=getattr(config, "LINKEDIN_TIME_FILTER", "r86400"),
            sort_by=getattr(config, "LINKEDIN_SORT_BY", "DD"),
        )
        for kw in keywords:
            search_limit = getattr(config, "LINKEDIN_SEARCH_LIMIT", 6) if not test_mode else 1
            logger.info(f"🔍 Поиск в регионе '{loc}' по слову: '{kw}'...")
            jobs = scraper.search_jobs(keyword=kw, limit=search_limit)
            seen_cnt, _ = log_and_track_batch(f"{loc} / {kw}", jobs, db)
            total_scanned += len(jobs)
            total_already_seen += seen_cnt

            for job in jobs:
                job_id = job["id"]
                job["region"] = loc
                if db.is_seen(job_id):
                    continue

                # Level 0: Валидация названия роли (отсекаем разработчиков, DevOps, PM и т.д. без QA)
                if not scraper.is_qa_title(job.get("title", "")):
                    logger.info(
                        f"🚫 [НЕ QA РОЛЬ] Отклонена по названию: '{job['title']}' @ {job['company']}"
                    )
                    total_filtered += 1

                    db.add_job(job)

                    continue

                # Level 1: Гео-фильтр карточки (отсекаем несовместимые страны сразу, не делая HTTP-запрос за деталями)
                if scraper.is_location_blocked(job.get("location", "")):
                    logger.info(
                        f"🚫 [ГЕО-БЛОКИРОВКА] Отклонена по локации: {job['title']} @ {job['company']} (Локация: {job['location']})"
                    )
                    total_filtered += 1

                    db.add_job(job)

                    continue

                time.sleep(1.0)  # Вежливая задержка перед запросом деталей
                full_desc = scraper.get_job_description(job_id)
                if not full_desc and getattr(scraper, "last_hit_rate_limit", False):
                    logger.warning(
                        f"⏳ Пропускаем вакансию '{job['title']}' @ {job['company']} из-за лимита запросов LinkedIn (будет проверена в следующем запуске)."
                    )
                    continue

                snippet = full_desc[:350].rstrip() + "..." if len(full_desc) > 350 else full_desc
                workplace_type = scraper.detect_workplace_type(job["title"], job["location"], full_desc)

                # Строгая фильтрация формата работы
                if workplace_type == "onsite" and not config.ALLOW_ONSITE:
                    logger.info(
                        f"🚫 [СТРОГИЙ ФИЛЬТР] Отклонена On-site вакансия: {job['title']} @ {job['company']} (Локация: {job['location']})"
                    )
                    db.add_job(job)  # Запоминаем, чтобы не проверять повторно
                    continue

                if workplace_type == "hybrid" and not config.ALLOW_HYBRID:
                    # Проверяем, может это рядом с Cahersiveen?
                    if is_hybrid_nearby(job["location"]):
                        logger.info(
                            f"✅ [ГИБРИД РЯДОМ] Пропущена через фильтр: {job['title']} @ {job['company']} (Локация: {job['location']})"
                        )
                    else:
                        logger.info(
                            f"🚫 [СТРОГИЙ ФИЛЬТР] Отклонена Hybrid вакансия (далеко): {job['title']} @ {job['company']} (Локация: {job['location']})"
                        )
                        total_filtered += 1

                        db.add_job(job)

                        continue

                # Вакансии с неясным форматом (unclear):
                # - Generic Ireland (без города) — пропускаем, скорее всего remote
                # - Рядом с Керри — пропускаем
                # - Всё остальное — отклоняем
                if workplace_type == "unclear":
                    loc_stripped = job.get("location", "").strip().lower()
                    is_generic_ireland = loc_stripped in ("ireland", "")
                    if not is_generic_ireland and not is_hybrid_nearby(job.get("location", "")):
                        logger.info(
                            f"🚫 [СТРОГИЙ ФИЛЬТР] Отклонена вакансия с неясным форматом: {job['title']} @ {job['company']} (Локация: {job['location']})"
                        )
                        total_filtered += 1

                        db.add_job(job)

                        continue
                    else:
                        logger.info(
                            f"🟡 [UNCLEAR → ПРОПУСК] Вакансия с неясным форматом, но generic Ireland/nearby: {job['title']} @ {job['company']} (Локация: {job['location']})"
                        )

                total_new += 1
                logger.info(f"✨ Новая вакансия [{job_id}] ({workplace_type}): {job['title']} @ {job['company']}")

                if dry_run:
                    print("\n" + "=" * 60)
                    print(f"[DRY RUN] Новая вакансия ({workplace_type.upper()} | {loc}):")
                    print(f"Позиция: {job['title']}")
                    print(f"Компания: {job['company']}")
                    print(f"Локация: {job['location']}")
                    print(f"Ссылка: {job['url']}")
                    if snippet:
                        print(f"Фрагмент описания: {snippet[:200]}...")
                    print("=" * 60 + "\n")
                else:
                    sent = notifier.send_job_alert(job, snippet=snippet, workplace_type=workplace_type)
                    if sent:
                        logger.info(f"✅ Отправлено в Telegram: {job_id}")
                    else:
                        logger.error(f"❌ Ошибка отправки в Telegram: {job_id}")
                    time.sleep(1.5)  # Задержка между отправками сообщений

                # Сохраняем в базу данных, чтобы не дублировать
                db.add_job(job)

            # Пауза между запросами по разным ключевым словам
            if scraper.last_hit_rate_limit:
                scraper.last_hit_rate_limit = False
                time.sleep(random.uniform(12.0, 18.0))
            else:
                time.sleep(random.uniform(4.0, 6.5))
        time.sleep(random.uniform(7.0, 12.0))  # Пауза между регионами

    # --- Djinni.co ---
    if config.ENABLE_DJINNI:
        djinni = DjinniJobScraper()
        djinni_keywords = config.DJINNI_KEYWORDS if not test_mode else [config.DJINNI_KEYWORDS[0]]
        for kw in djinni_keywords:
            logger.info(f"🟢 Поиск на Djinni.co по слову: '{kw}'...")
            max_pages = getattr(config, "DJINNI_MAX_PAGES", 5)
            limit = getattr(config, "DJINNI_LIMIT", 60)
            djinni_jobs = djinni.search_jobs(keyword=kw, max_pages=max_pages, limit=limit)
            seen_cnt, _ = log_and_track_batch(f"Djinni / {kw}", djinni_jobs, db)
            total_scanned += len(djinni_jobs)
            total_already_seen += seen_cnt

            for job in djinni_jobs:
                job_id = job["id"]
                if db.is_seen(job_id):
                    continue

                # Level 0: Валидация названия роли
                if not LinkedInJobScraper.is_qa_title(job.get("title", "")):
                    logger.info(
                        f"🚫 [НЕ QA РОЛЬ / Djinni] Отклонена по названию: '{job['title']}' @ {job['company']}"
                    )
                    total_filtered += 1

                    db.add_job(job)

                    continue

                # Level 1: Гео-фильтр карточки (отсекаем несовместимые страны: США, Латам, Азию и др.)
                if LinkedInJobScraper.is_location_blocked(job.get("location", "")):
                    logger.info(
                        f"🚫 [ГЕО-БЛОКИРОВКА / Djinni] Отклонена по локации: {job['title']} @ {job['company']} (Локация: {job.get('location', '')})"
                    )
                    total_filtered += 1

                    db.add_job(job)

                    continue

                # Level 2: Стоп-фразы в описании
                if LinkedInJobScraper.is_description_blocked(job.get("description", "")):
                    logger.info(
                        f"🚫 [СТОП-ОПИСАНИЕ / Djinni] Отклонена по описанию: '{job['title']}' @ {job['company']}"
                    )
                    total_filtered += 1

                    db.add_job(job)

                    continue

                workplace_type = job.get("workplace_type", "remote")

                # Фильтрация гибридных вакансий на Djinni
                if workplace_type == "hybrid" and not config.ALLOW_HYBRID:
                    if is_hybrid_nearby(job.get("location", "")):
                        logger.info(
                            f"✅ [ГИБРИД РЯДОМ / Djinni] Пропущена через фильтр: {job['title']} @ {job['company']} (Локация: {job.get('location', '')})"
                        )
                    else:
                        logger.info(
                            f"🚫 [СТРОГИЙ ФИЛЬТР / Djinni] Отклонена Hybrid вакансия (далеко): {job['title']} @ {job['company']} (Локация: {job.get('location', '')})"
                        )
                        total_filtered += 1

                        db.add_job(job)

                        continue

                # Фильтрация по разрешенным странам на Djinni (профиль кандидата в Ирландии)
                if getattr(config, "DJINNI_COUNTRY_FILTER", True):
                    user_countries = getattr(config, "DJINNI_USER_COUNTRIES", ["IE", "IRL", "IRELAND"])
                    user_regions = getattr(config, "DJINNI_USER_REGIONS", ["EUROPE", "EU", "WORLDWIDE", "ANY", "ALL"])
                    if not is_djinni_country_eligible(job, user_countries=user_countries, user_regions=user_regions):
                        logger.info(
                            f"🚫 [СТРОГИЙ ФИЛЬТР / Djinni] Отклонена (Ирландия не подходит): "
                            f"{job['title']} @ {job['company']} (Локация: {job.get('location', '')})"
                        )
                        total_filtered += 1

                        db.add_job(job)

                        continue

                total_new += 1
                snippet = job.get("description", "")[:350]
                if len(job.get("description", "")) > 350:
                    snippet = snippet.rstrip() + "..."

                logger.info(f"✨ [Djinni] Новая вакансия [{job_id}] ({workplace_type}): {job['title']} @ {job['company']}")

                if dry_run:
                    print("\n" + "=" * 60)
                    print(f"[DRY RUN / Djinni] Новая вакансия ({workplace_type.upper()}):")
                    print(f"Позиция: {job['title']}")
                    print(f"Компания: {job['company']}")
                    print(f"Локация: {job['location']}")
                    if job.get("salary"):
                        print(f"Зарплата: {job['salary']}")
                    print(f"Ссылка: {job['url']}")
                    if snippet:
                        print(f"Фрагмент описания: {snippet[:200]}...")
                    print("=" * 60 + "\n")
                else:
                    sent = notifier.send_job_alert(job, snippet=snippet, workplace_type=workplace_type)
                    if sent:
                        logger.info(f"✅ Отправлено в Telegram: {job_id}")
                    else:
                        logger.error(f"❌ Ошибка отправки в Telegram: {job_id}")
                    time.sleep(1.5)

                db.add_job(job)

            time.sleep(2.0)

    # --- DOU (jobs.dou.ua) ---
    if getattr(config, "ENABLE_DOU", True):
        dou = DouJobScraper()
        dou_category = getattr(config, "DOU_CATEGORY", "QA")
        dou_remote = getattr(config, "DOU_REMOTE_ONLY", True)
        dou_limit = getattr(config, "DOU_LIMIT", 50) if not test_mode else 10
        logger.info(f"🟡 Поиск на DOU (jobs.dou.ua, Категория: {dou_category}, Remote={dou_remote})...")
        dou_jobs = dou.search_jobs(category=dou_category, remote_only=dou_remote, limit=dou_limit)
        seen_cnt, _ = log_and_track_batch("DOU", dou_jobs, db)
        total_scanned += len(dou_jobs)
        total_already_seen += seen_cnt

        for job in dou_jobs:
            job_id = job["id"]
            if db.is_seen(job_id):
                continue

            # Level 0: Валидация названия роли
            if not LinkedInJobScraper.is_qa_title(job.get("title", "")):
                logger.info(
                    f"🚫 [НЕ QA РОЛЬ / DOU] Отклонена по названию: '{job['title']}' @ {job['company']}"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            # Level 1: Гео-фильтр карточки (отсекаем несовместимые страны: США, Латам, Азию и др.)
            if LinkedInJobScraper.is_location_blocked(job.get("location", "")):
                logger.info(
                    f"🚫 [ГЕО-БЛОКИРОВКА / DOU] Отклонена по локации: {job['title']} @ {job['company']} (Локация: {job['location']})"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            # Level 2: Стоп-фразы в описании (внутренние US/Latam ограничения, зарплатные сетки США)
            if LinkedInJobScraper.is_description_blocked(job.get("description", "")):
                logger.info(
                    f"🚫 [СТОП-ОПИСАНИЕ / DOU] Отклонена по описанию: '{job['title']}' @ {job['company']}"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            workplace_type = job.get("workplace_type", "remote")
            total_new += 1
            snippet = job.get("description", "")[:350]
            if len(job.get("description", "")) > 350:
                snippet = snippet.rstrip() + "..."

            logger.info(f"✨ [DOU] Новая вакансия [{job_id}] ({workplace_type}): {job['title']} @ {job['company']}")

            if dry_run:
                print("\n" + "=" * 60)
                print(f"[DRY RUN / DOU] Новая вакансия ({workplace_type.upper()}):")
                print(f"Позиция: {job['title']}")
                print(f"Компания: {job['company']}")
                print(f"Локация: {job['location']}")
                if job.get("salary"):
                    print(f"Зарплата: {job['salary']}")
                print(f"Ссылка: {job['url']}")
                if snippet:
                    print(f"Фрагмент описания: {snippet[:200]}...")
                print("=" * 60 + "\n")
            else:
                sent = notifier.send_job_alert(job, snippet=snippet, workplace_type=workplace_type)
                if sent:
                    logger.info(f"✅ Отправлено в Telegram: {job_id}")
                else:
                    logger.error(f"❌ Ошибка отправки в Telegram: {job_id}")
                time.sleep(1.5)

            db.add_job(job)

    # --- No Fluff Jobs (nofluffjobs.com) ---
    if getattr(config, "ENABLE_NOFLUFF", True):
        nofluff = NoFluffJobScraper()
        nfj_category = getattr(config, "NOFLUFF_CATEGORY", "testing")
        nfj_remote = getattr(config, "NOFLUFF_REMOTE_ONLY", True)
        nfj_currency = getattr(config, "NOFLUFF_CURRENCY", "EUR")
        nfj_limit = getattr(config, "NOFLUFF_LIMIT", 50) if not test_mode else 10
        logger.info(f"🔴 Поиск на No Fluff Jobs (Категория: {nfj_category}, Remote={nfj_remote}, Валюта={nfj_currency})...")
        nfj_jobs = nofluff.search_jobs(category=nfj_category, remote_only=nfj_remote, currency=nfj_currency, limit=nfj_limit)
        seen_cnt, _ = log_and_track_batch("No Fluff Jobs", nfj_jobs, db)
        total_scanned += len(nfj_jobs)
        total_already_seen += seen_cnt

        for job in nfj_jobs:
            job_id = job["id"]
            if db.is_seen(job_id):
                continue

            # Level 0: Валидация названия роли
            if not LinkedInJobScraper.is_qa_title(job.get("title", "")):
                logger.info(
                    f"🚫 [НЕ QA РОЛЬ / NoFluff] Отклонена по названию: '{job['title']}' @ {job['company']}"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            # Level 0.5: Фильтр польских локальных вакансий
            if getattr(config, "EXCLUDE_POLISH_DOMESTIC_ROLES", True) and is_polish_domestic_title(job.get("title", "")):
                logger.info(
                    f"🇵🇱 [POLISH DOMESTIC / NoFluff] Отклонена по польскому названию: '{job['title']}' @ {job['company']}"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            workplace_type = job.get("workplace_type", "remote")
            total_new += 1
            snippet = job.get("description", "")[:350]
            if len(job.get("description", "")) > 350:
                snippet = snippet.rstrip() + "..."

            logger.info(f"✨ [NoFluff] Новая вакансия [{job_id}] ({workplace_type}): {job['title']} @ {job['company']}")

            if dry_run:
                print("\n" + "=" * 60)
                print(f"[DRY RUN / NoFluff] Новая вакансия ({workplace_type.upper()}):")
                print(f"Позиция: {job['title']}")
                print(f"Компания: {job['company']}")
                print(f"Локация: {job['location']}")
                if job.get("salary"):
                    print(f"Зарплата: {job['salary']}")
                print(f"Ссылка: {job['url']}")
                if snippet:
                    print(f"Фрагмент описания: {snippet[:200]}...")
                print("=" * 60 + "\n")
            else:
                sent = notifier.send_job_alert(job, snippet=snippet, workplace_type=workplace_type)
                if sent:
                    logger.info(f"✅ Отправлено в Telegram: {job_id}")
                else:
                    logger.error(f"❌ Ошибка отправки в Telegram: {job_id}")
                time.sleep(1.5)

            db.add_job(job)

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
        seen_cnt, _ = log_and_track_batch("JustJoin.it", jjit_jobs, db)
        total_scanned += len(jjit_jobs)
        total_already_seen += seen_cnt

        for job in jjit_jobs:
            job_id = job["id"]
            if db.is_seen(job_id):
                continue

            # Level 0: Валидация названия роли
            if not LinkedInJobScraper.is_qa_title(job.get("title", "")):
                logger.info(
                    f"🚫 [НЕ QA РОЛЬ / JustJoin] Отклонена по названию: '{job['title']}' @ {job['company']}"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            # Level 0.5: Фильтр польских локальных вакансий
            if getattr(config, "EXCLUDE_POLISH_DOMESTIC_ROLES", True) and is_polish_domestic_title(job.get("title", "")):
                logger.info(
                    f"🇵🇱 [POLISH DOMESTIC / JustJoin] Отклонена по польскому названию: '{job['title']}' @ {job['company']}"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            workplace_type = job.get("workplace_type", "remote")
            total_new += 1
            snippet = job.get("description", "")[:350]
            if len(job.get("description", "")) > 350:
                snippet = snippet.rstrip() + "..."

            logger.info(f"✨ [JustJoin] Новая вакансия [{job_id}] ({workplace_type}): {job['title']} @ {job['company']}")

            if dry_run:
                print("\n" + "=" * 60)
                print(f"[DRY RUN / JustJoin] Новая вакансия ({workplace_type.upper()}):")
                print(f"Позиция: {job['title']}")
                print(f"Компания: {job['company']}")
                print(f"Локация: {job['location']}")
                if job.get("salary"):
                    print(f"Зарплата: {job['salary']}")
                print(f"Ссылка: {job['url']}")
                if snippet:
                    print(f"Фрагмент описания: {snippet[:200]}...")
                print("=" * 60 + "\n")
            else:
                sent = notifier.send_job_alert(job, snippet=snippet, workplace_type=workplace_type)
                if sent:
                    logger.info(f"✅ Отправлено в Telegram: {job_id}")
                else:
                    logger.error(f"❌ Ошибка отправки в Telegram: {job_id}")
                time.sleep(1.5)

            db.add_job(job)

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
            seen_cnt, _ = log_and_track_batch("Adzuna", adzuna_jobs, db)
            total_scanned += len(adzuna_jobs)
            total_already_seen += seen_cnt

            for job in adzuna_jobs:
                job_id = job["id"]
                if db.is_seen(job_id):
                    continue

                # Level 0: Валидация названия роли
                if not LinkedInJobScraper.is_qa_title(job.get("title", "")):
                    logger.info(
                        f"🚫 [НЕ QA РОЛЬ / Adzuna] Отклонена по названию: '{job['title']}' @ {job['company']}"
                    )
                    total_filtered += 1

                    db.add_job(job)

                    continue

                workplace_type = job.get("workplace_type", "remote")
                total_new += 1
                snippet = job.get("description", "")[:350]
                if len(job.get("description", "")) > 350:
                    snippet = snippet.rstrip() + "..."

                logger.info(f"✨ [Adzuna] Новая вакансия [{job_id}] ({workplace_type}): {job['title']} @ {job['company']}")

                if dry_run:
                    print("\n" + "=" * 60)
                    print(f"[DRY RUN / Adzuna] Новая вакансия ({workplace_type.upper()}):")
                    print(f"Позиция: {job['title']}")
                    print(f"Компания: {job['company']}")
                    print(f"Локация: {job['location']}")
                    if job.get("salary"):
                        print(f"Зарплата: {job['salary']}")
                    print(f"Ссылка: {job['url']}")
                    if snippet:
                        print(f"Фрагмент описания: {snippet[:200]}...")
                    print("=" * 60 + "\n")
                else:
                    sent = notifier.send_job_alert(job, snippet=snippet, workplace_type=workplace_type)
                    if sent:
                        logger.info(f"✅ Отправлено в Telegram: {job_id}")
                    else:
                        logger.error(f"❌ Ошибка отправки в Telegram: {job_id}")
                    time.sleep(1.5)

                db.add_job(job)

    # --- Arbeitnow (arbeitnow.com) ---
    if getattr(config, "ENABLE_ARBEITNOW", True):
        arbeitnow = ArbeitnowJobScraper()
        an_remote = getattr(config, "ARBEITNOW_REMOTE_ONLY", True)
        an_pages = getattr(config, "ARBEITNOW_MAX_PAGES", 2) if not test_mode else 1
        an_limit = getattr(config, "ARBEITNOW_LIMIT", 50) if not test_mode else 10
        logger.info(f"🌐 Поиск на Arbeitnow (Remote={an_remote}, Страниц: {an_pages})...")
        an_jobs = arbeitnow.search_jobs(remote_only=an_remote, max_pages=an_pages, limit=an_limit)
        seen_cnt, _ = log_and_track_batch("Arbeitnow", an_jobs, db)
        total_scanned += len(an_jobs)
        total_already_seen += seen_cnt

        for job in an_jobs:
            job_id = job["id"]
            if db.is_seen(job_id):
                continue

            # Level 0: Валидация названия роли
            if not LinkedInJobScraper.is_qa_title(job.get("title", "")):
                logger.info(
                    f"🚫 [НЕ QA РОЛЬ / Arbeitnow] Отклонена по названию: '{job['title']}' @ {job['company']}"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            # Level 1: Гео-фильтр карточки (отсекаем несовместимые страны: США, Латам, Азию и др.)
            if LinkedInJobScraper.is_location_blocked(job.get("location", "")):
                logger.info(
                    f"🚫 [ГЕО-БЛОКИРОВКА / Arbeitnow] Отклонена по локации: {job['title']} @ {job['company']} (Локация: {job['location']})"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            # Level 2: Стоп-фразы в описании (внутренние US/Latam ограничения, зарплатные сетки США)
            if LinkedInJobScraper.is_description_blocked(job.get("description", "")):
                logger.info(
                    f"🚫 [СТОП-ОПИСАНИЕ / Arbeitnow] Отклонена по описанию: '{job['title']}' @ {job['company']}"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            workplace_type = job.get("workplace_type", "remote")
            total_new += 1
            snippet = job.get("description", "")[:350]
            if len(job.get("description", "")) > 350:
                snippet = snippet.rstrip() + "..."

            logger.info(f"✨ [Arbeitnow] Новая вакансия [{job_id}] ({workplace_type}): {job['title']} @ {job['company']}")

            if dry_run:
                print("\n" + "=" * 60)
                print(f"[DRY RUN / Arbeitnow] Новая вакансия ({workplace_type.upper()}):")
                print(f"Позиция: {job['title']}")
                print(f"Компания: {job['company']}")
                print(f"Локация: {job['location']}")
                if job.get("salary"):
                    print(f"Зарплата: {job['salary']}")
                print(f"Ссылка: {job['url']}")
                if snippet:
                    print(f"Фрагмент описания: {snippet[:200]}...")
                print("=" * 60 + "\n")
            else:
                sent = notifier.send_job_alert(job, snippet=snippet, workplace_type=workplace_type)
                if sent:
                    logger.info(f"✅ Отправлено в Telegram: {job_id}")
                else:
                    logger.error(f"❌ Ошибка отправки в Telegram: {job_id}")
                time.sleep(1.5)

            db.add_job(job)

    # --- Greenhouse (Direct Company ATS) ---
    if getattr(config, "ENABLE_GREENHOUSE", True):
        gh_companies = getattr(config, "GREENHOUSE_COMPANIES", ["canonical", "cloudflare"])
        gh_remote = getattr(config, "GREENHOUSE_REMOTE_ONLY", True)
        gh_limit = getattr(config, "GREENHOUSE_LIMIT_PER_COMPANY", 30) if not test_mode else 10
        target_comps = gh_companies if not test_mode else [gh_companies[0]]
        logger.info(f"🌱 Поиск в Greenhouse ATS (Компаний: {len(target_comps)}, Remote={gh_remote})...")
        greenhouse = GreenhouseJobScraper(companies=target_comps)
        gh_jobs = greenhouse.search_jobs(remote_only=gh_remote, limit_per_company=gh_limit)
        seen_cnt, _ = log_and_track_batch("Greenhouse", gh_jobs, db)
        total_scanned += len(gh_jobs)
        total_already_seen += seen_cnt

        for job in gh_jobs:
            job_id = job["id"]
            if db.is_seen(job_id):
                continue

            # Level 0: Валидация названия роли
            if not LinkedInJobScraper.is_qa_title(job.get("title", "")):
                logger.info(
                    f"🚫 [НЕ QA РОЛЬ / Greenhouse] Отклонена по названию: '{job['title']}' @ {job['company']}"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            # Level 1: Гео-фильтр карточки (отсекаем несовместимые страны: США, Латам, Азию и др.)
            if LinkedInJobScraper.is_location_blocked(job.get("location", "")):
                logger.info(
                    f"🚫 [ГЕО-БЛОКИРОВКА / Greenhouse] Отклонена по локации: {job['title']} @ {job['company']} (Локация: {job['location']})"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            # Level 2: Стоп-фразы в описании (внутренние US/Latam ограничения, зарплатные сетки США)
            if LinkedInJobScraper.is_description_blocked(job.get("description", "")):
                logger.info(
                    f"🚫 [СТОП-ОПИСАНИЕ / Greenhouse] Отклонена по описанию: '{job['title']}' @ {job['company']}"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            workplace_type = job.get("workplace_type", "remote")
            total_new += 1
            snippet = job.get("description", "")[:350]
            if len(job.get("description", "")) > 350:
                snippet = snippet.rstrip() + "..."

            logger.info(f"✨ [Greenhouse] Новая вакансия [{job_id}] ({workplace_type}): {job['title']} @ {job['company']}")

            if dry_run:
                print("\n" + "=" * 60)
                print(f"[DRY RUN / Greenhouse] Новая вакансия ({workplace_type.upper()}):")
                print(f"Позиция: {job['title']}")
                print(f"Компания: {job['company']}")
                print(f"Локация: {job['location']}")
                if job.get("salary"):
                    print(f"Зарплата: {job['salary']}")
                print(f"Ссылка: {job['url']}")
                if snippet:
                    print(f"Фрагмент описания: {snippet[:200]}...")
                print("=" * 60 + "\n")
            else:
                sent = notifier.send_job_alert(job, snippet=snippet, workplace_type=workplace_type)
                if sent:
                    logger.info(f"✅ Отправлено в Telegram: {job_id}")
                else:
                    logger.error(f"❌ Ошибка отправки в Telegram: {job_id}")
                time.sleep(1.5)

            db.add_job(job)

    # --- Lever (Direct Company ATS) ---
    if getattr(config, "ENABLE_LEVER", True):
        lever_companies = getattr(config, "LEVER_COMPANIES", ["palantir", "spotify"])
        lever_remote = getattr(config, "LEVER_REMOTE_ONLY", True)
        lever_limit = getattr(config, "LEVER_LIMIT_PER_COMPANY", 30) if not test_mode else 10
        target_lever_comps = lever_companies if not test_mode else [lever_companies[0]]
        logger.info(f"⚡ Поиск в Lever ATS (Компаний: {len(target_lever_comps)}, Remote={lever_remote})...")
        lever = LeverJobScraper(companies=target_lever_comps)
        lever_jobs = lever.search_jobs(remote_only=lever_remote, limit_per_company=lever_limit)
        seen_cnt, _ = log_and_track_batch("Lever", lever_jobs, db)
        total_scanned += len(lever_jobs)
        total_already_seen += seen_cnt

        for job in lever_jobs:
            job_id = job["id"]
            if db.is_seen(job_id):
                continue

            # Level 0: Валидация названия роли
            if not LinkedInJobScraper.is_qa_title(job.get("title", "")):
                logger.info(
                    f"🚫 [НЕ QA РОЛЬ / Lever] Отклонена по названию: '{job['title']}' @ {job['company']}"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            # Level 1: Гео-фильтр карточки (отсекаем несовместимые страны: США, Латам, Азию и др.)
            if LinkedInJobScraper.is_location_blocked(job.get("location", "")):
                logger.info(
                    f"🚫 [ГЕО-БЛОКИРОВКА / Lever] Отклонена по локации: {job['title']} @ {job['company']} (Локация: {job['location']})"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            # Level 2: Стоп-фразы в описании (внутренние US/Latam ограничения, зарплатные сетки США)
            if LinkedInJobScraper.is_description_blocked(job.get("description", "")):
                logger.info(
                    f"🚫 [СТОП-ОПИСАНИЕ / Lever] Отклонена по описанию: '{job['title']}' @ {job['company']}"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            workplace_type = job.get("workplace_type", "remote")
            total_new += 1
            snippet = job.get("description", "")[:350]
            if len(job.get("description", "")) > 350:
                snippet = snippet.rstrip() + "..."

            logger.info(f"✨ [Lever] Новая вакансия [{job_id}] ({workplace_type}): {job['title']} @ {job['company']}")

            if dry_run:
                print("\n" + "=" * 60)
                print(f"[DRY RUN / Lever] Новая вакансия ({workplace_type.upper()}):")
                print(f"Позиция: {job['title']}")
                print(f"Компания: {job['company']}")
                print(f"Локация: {job['location']}")
                if job.get("salary"):
                    print(f"Зарплата: {job['salary']}")
                print(f"Ссылка: {job['url']}")
                if snippet:
                    print(f"Фрагмент описания: {snippet[:200]}...")
                print("=" * 60 + "\n")
            else:
                sent = notifier.send_job_alert(job, snippet=snippet, workplace_type=workplace_type)
                if sent:
                    logger.info(f"✅ Отправлено в Telegram: {job_id}")
                else:
                    logger.error(f"❌ Ошибка отправки в Telegram: {job_id}")
                time.sleep(1.5)

            db.add_job(job)

    # --- Ashby (Direct Company ATS) ---
    if getattr(config, "ENABLE_ASHBY", True):
        ashby_companies = getattr(config, "ASHBY_COMPANIES", ["linear", "synthesia", "posthog"])
        ashby_remote = getattr(config, "ASHBY_REMOTE_ONLY", True)
        ashby_limit = getattr(config, "ASHBY_LIMIT_PER_COMPANY", 30) if not test_mode else 10
        target_ashby_comps = ashby_companies if not test_mode else [ashby_companies[0]]
        logger.info(f"🪐 Поиск в Ashby ATS (Компаний: {len(target_ashby_comps)}, Remote={ashby_remote})...")
        ashby = AshbyJobScraper(companies=target_ashby_comps)
        ashby_jobs = ashby.search_jobs(remote_only=ashby_remote, limit_per_company=ashby_limit)
        seen_cnt, _ = log_and_track_batch("Ashby", ashby_jobs, db)
        total_scanned += len(ashby_jobs)
        total_already_seen += seen_cnt

        for job in ashby_jobs:
            job_id = job["id"]
            if db.is_seen(job_id):
                continue

            # Level 0: Валидация названия роли
            if not LinkedInJobScraper.is_qa_title(job.get("title", "")):
                logger.info(
                    f"🚫 [НЕ QA РОЛЬ / Ashby] Отклонена по названию: '{job['title']}' @ {job['company']}"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            # Level 1: Гео-фильтр карточки (отсекаем несовместимые страны: США, Латам, Азию и др.)
            if LinkedInJobScraper.is_location_blocked(job.get("location", "")):
                logger.info(
                    f"🚫 [ГЕО-БЛОКИРОВКА / Ashby] Отклонена по локации: {job['title']} @ {job['company']} (Локация: {job['location']})"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            # Level 2: Стоп-фразы в описании (внутренние US/Latam ограничения, зарплатные сетки США)
            if LinkedInJobScraper.is_description_blocked(job.get("description", "")):
                logger.info(
                    f"🚫 [СТОП-ОПИСАНИЕ / Ashby] Отклонена по описанию: '{job['title']}' @ {job['company']}"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            workplace_type = job.get("workplace_type", "remote")
            total_new += 1
            snippet = job.get("description", "")[:350]
            if len(job.get("description", "")) > 350:
                snippet = snippet.rstrip() + "..."

            logger.info(f"✨ [Ashby] Новая вакансия [{job_id}] ({workplace_type}): {job['title']} @ {job['company']}")

            if dry_run:
                print("\n" + "=" * 60)
                print(f"[DRY RUN / Ashby] Новая вакансия ({workplace_type.upper()}):")
                print(f"Позиция: {job['title']}")
                print(f"Компания: {job['company']}")
                print(f"Локация: {job['location']}")
                if job.get("salary"):
                    print(f"Зарплата: {job['salary']}")
                print(f"Ссылка: {job['url']}")
                if snippet:
                    print(f"Фрагмент описания: {snippet[:200]}...")
                print("=" * 60 + "\n")
            else:
                sent = notifier.send_job_alert(job, snippet=snippet, workplace_type=workplace_type)
                if sent:
                    logger.info(f"✅ Отправлено в Telegram: {job_id}")
                else:
                    logger.error(f"❌ Ошибка отправки в Telegram: {job_id}")
                time.sleep(1.5)

            db.add_job(job)

    # --- Remotive (remotive.com API) ---
    if getattr(config, "ENABLE_REMOTIVE", True):
        remotive_cat = getattr(config, "REMOTIVE_CATEGORY", "qa")
        remotive_remote = getattr(config, "REMOTIVE_REMOTE_ONLY", True)
        remotive_limit = getattr(config, "REMOTIVE_LIMIT", 50) if not test_mode else 10
        logger.info(f"🚀 Поиск на Remotive (Category={remotive_cat}, Remote={remotive_remote})...")
        remotive = RemotiveJobScraper(category=remotive_cat)
        remotive_jobs = remotive.search_jobs(category=remotive_cat, remote_only=remotive_remote, limit=remotive_limit)
        seen_cnt, _ = log_and_track_batch("Remotive", remotive_jobs, db)
        total_scanned += len(remotive_jobs)
        total_already_seen += seen_cnt

        for job in remotive_jobs:
            job_id = job["id"]
            if db.is_seen(job_id):
                continue

            # Level 0: Валидация названия роли
            if not LinkedInJobScraper.is_qa_title(job.get("title", "")):
                logger.info(
                    f"🚫 [НЕ QA РОЛЬ / Remotive] Отклонена по названию: '{job['title']}' @ {job['company']}"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            # Level 1: Гео-фильтр карточки (отсекаем несовместимые страны: США, Латам, Азию и др.)
            if LinkedInJobScraper.is_location_blocked(job.get("location", "")):
                logger.info(
                    f"🚫 [ГЕО-БЛОКИРОВКА / Remotive] Отклонена по локации: {job['title']} @ {job['company']} (Локация: {job['location']})"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            # Level 2: Стоп-фразы в описании (внутренние US/Latam ограничения, зарплатные сетки США)
            if LinkedInJobScraper.is_description_blocked(job.get("description", "")):
                logger.info(
                    f"🚫 [СТОП-ОПИСАНИЕ / Remotive] Отклонена по описанию: '{job['title']}' @ {job['company']}"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            workplace_type = job.get("workplace_type", "remote")
            total_new += 1
            snippet = job.get("description", "")[:350]
            if len(job.get("description", "")) > 350:
                snippet = snippet.rstrip() + "..."

            logger.info(f"✨ [Remotive] Новая вакансия [{job_id}] ({workplace_type}): {job['title']} @ {job['company']}")

            if dry_run:
                print("\n" + "=" * 60)
                print(f"[DRY RUN / Remotive] Новая вакансия ({workplace_type.upper()}):")
                print(f"Позиция: {job['title']}")
                print(f"Компания: {job['company']}")
                print(f"Локация: {job['location']}")
                if job.get("salary"):
                    print(f"Зарплата: {job['salary']}")
                print(f"Ссылка: {job['url']}")
                if snippet:
                    print(f"Фрагмент описания: {snippet[:200]}...")
                print("=" * 60 + "\n")
            else:
                sent = notifier.send_job_alert(job, snippet=snippet, workplace_type=workplace_type)
                if sent:
                    logger.info(f"✅ Отправлено в Telegram: {job_id}")
                else:
                    logger.error(f"❌ Ошибка отправки в Telegram: {job_id}")
                time.sleep(1.5)

            db.add_job(job)

    # --- WeWorkRemotely (weworkremotely.com RSS) ---
    if getattr(config, "ENABLE_WEWORKREMOTELY", True):
        wwr_limit = getattr(config, "WEWORKREMOTELY_LIMIT", 50) if not test_mode else 10
        logger.info(f"💼 Поиск на WeWorkRemotely RSS...")
        wwr = WeWorkRemotelyJobScraper()
        wwr_jobs = wwr.search_jobs(remote_only=True, limit=wwr_limit)
        seen_cnt, _ = log_and_track_batch("WeWorkRemotely", wwr_jobs, db)
        total_scanned += len(wwr_jobs)
        total_already_seen += seen_cnt

        for job in wwr_jobs:
            job_id = job["id"]
            if db.is_seen(job_id):
                continue

            # Level 0: Валидация названия роли
            if not LinkedInJobScraper.is_qa_title(job.get("title", "")):
                logger.info(
                    f"🚫 [НЕ QA РОЛЬ / WeWorkRemotely] Отклонена по названию: '{job['title']}' @ {job['company']}"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            # Level 1: Гео-фильтр карточки (отсекаем несовместимые страны: США, Латам, Азию и др.)
            if LinkedInJobScraper.is_location_blocked(job.get("location", "")):
                logger.info(
                    f"🚫 [ГЕО-БЛОКИРОВКА / WeWorkRemotely] Отклонена по локации: {job['title']} @ {job['company']} (Локация: {job['location']})"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            # Level 2: Стоп-фразы в описании (внутренние US/Latam ограничения, зарплатные сетки США)
            if LinkedInJobScraper.is_description_blocked(job.get("description", "")):
                logger.info(
                    f"🚫 [СТОП-ОПИСАНИЕ / WeWorkRemotely] Отклонена по описанию: '{job['title']}' @ {job['company']}"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            workplace_type = job.get("workplace_type", "remote")
            total_new += 1
            snippet = job.get("description", "")[:350]
            if len(job.get("description", "")) > 350:
                snippet = snippet.rstrip() + "..."

            logger.info(f"✨ [WeWorkRemotely] Новая вакансия [{job_id}] ({workplace_type}): {job['title']} @ {job['company']}")

            if dry_run:
                print("\n" + "=" * 60)
                print(f"[DRY RUN / WeWorkRemotely] Новая вакансия ({workplace_type.upper()}):")
                print(f"Позиция: {job['title']}")
                print(f"Компания: {job['company']}")
                print(f"Локация: {job['location']}")
                if job.get("salary"):
                    print(f"Зарплата: {job['salary']}")
                print(f"Ссылка: {job['url']}")
                if snippet:
                    print(f"Фрагмент описания: {snippet[:200]}...")
                print("=" * 60 + "\n")
            else:
                sent = notifier.send_job_alert(job, snippet=snippet, workplace_type=workplace_type)
                if sent:
                    logger.info(f"✅ Отправлено в Telegram: {job_id}")
                else:
                    logger.error(f"❌ Ошибка отправки в Telegram: {job_id}")
                time.sleep(1.5)

            db.add_job(job)

    # --- Himalayas (himalayas.app API) ---
    if getattr(config, "ENABLE_HIMALAYAS", True):
        himalayas_max_pages = getattr(config, "HIMALAYAS_MAX_PAGES", 5) if not test_mode else 1
        himalayas_limit = getattr(config, "HIMALAYAS_LIMIT", 50) if not test_mode else 10
        logger.info(f"🏔️ Поиск на Himalayas API (Страниц: {himalayas_max_pages})...")
        himalayas = HimalayasJobScraper(max_pages=himalayas_max_pages)
        himalayas_jobs = himalayas.search_jobs(remote_only=True, limit=himalayas_limit)
        seen_cnt, _ = log_and_track_batch("Himalayas", himalayas_jobs, db)
        total_scanned += len(himalayas_jobs)
        total_already_seen += seen_cnt

        for job in himalayas_jobs:
            job_id = job["id"]
            if db.is_seen(job_id):
                continue

            # Level 0: Валидация названия роли
            if not LinkedInJobScraper.is_qa_title(job.get("title", "")):
                logger.info(
                    f"🚫 [НЕ QA РОЛЬ / Himalayas] Отклонена по названию: '{job['title']}' @ {job['company']}"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            # Level 1: Гео-фильтр карточки
            if LinkedInJobScraper.is_location_blocked(job.get("location", "")):
                logger.info(
                    f"🚫 [ГЕО-БЛОКИРОВКА / Himalayas] Отклонена по локации: {job['title']} @ {job['company']} (Локация: {job['location']})"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            # Level 2: Стоп-фразы в описании
            if LinkedInJobScraper.is_description_blocked(job.get("description", "")):
                logger.info(
                    f"🚫 [СТОП-ОПИСАНИЕ / Himalayas] Отклонена по описанию: '{job['title']}' @ {job['company']}"
                )
                total_filtered += 1

                db.add_job(job)

                continue

            workplace_type = job.get("workplace_type", "remote")
            total_new += 1
            snippet = job.get("description", "")[:350]
            if len(job.get("description", "")) > 350:
                snippet = snippet.rstrip() + "..."

            logger.info(f"✨ [Himalayas] Новая вакансия [{job_id}] ({workplace_type}): {job['title']} @ {job['company']}")

            if dry_run:
                print("\n" + "=" * 60)
                print(f"[DRY RUN / Himalayas] Новая вакансия ({workplace_type.upper()}):")
                print(f"Позиция: {job['title']}")
                print(f"Компания: {job['company']}")
                print(f"Локация: {job['location']}")
                if job.get("salary"):
                    print(f"Зарплата: {job['salary']}")
                print(f"Ссылка: {job['url']}")
                if snippet:
                    print(f"Фрагмент описания: {snippet[:200]}...")
                print("=" * 60 + "\n")
            else:
                sent = notifier.send_job_alert(job, snippet=snippet, workplace_type=workplace_type)
                if sent:
                    logger.info(f"✅ Отправлено в Telegram: {job_id}")
                else:
                    logger.error(f"❌ Ошибка отправки в Telegram: {job_id}")
                time.sleep(1.5)

            db.add_job(job)

    # --- Jobicy public API ---
    if getattr(config, "ENABLE_JOBICY", True):
        if db.claim_source_poll("jobicy", min_interval_seconds=3600):
            logger.info("🟠 Поиск на Jobicy API...")
            jobicy = JobicyJobScraper()
            jobicy_jobs = jobicy.search_jobs(
                tags=getattr(config, "JOBICY_TAGS", ["QA", "SDET", "test automation"]),
                limit=getattr(config, "JOBICY_LIMIT", 100) if not test_mode else 20,
            )
            seen_cnt, _ = log_and_track_batch("Jobicy", jobicy_jobs, db)
            total_scanned += len(jobicy_jobs)
            total_already_seen += seen_cnt
            new_count, filtered_count = process_remote_feed_jobs(
                "Jobicy", jobicy_jobs, db, notifier, dry_run
            )
            total_new += new_count
            total_filtered += filtered_count
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
        seen_cnt, _ = log_and_track_batch("Remote OK", remoteok_jobs, db)
        total_scanned += len(remoteok_jobs)
        total_already_seen += seen_cnt
        new_count, filtered_count = process_remote_feed_jobs(
            "Remote OK", remoteok_jobs, db, notifier, dry_run
        )
        total_new += new_count
        total_filtered += filtered_count

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
