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

# Prevent duplicate concurrent executions using a file lock
import msvcrt
lock_file_path = Path(__file__).parent / "tracker.lock"
try:
    _lock_handle = open(lock_file_path, "w")
    msvcrt.locking(_lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
except OSError:
    if sys.stdout: print("⚠️ Другой экземпляр трекера уже запущен. Пропуск запуска.")
    sys.exit(0)

import config
from linkedin_scraper import LinkedInJobScraper
from djinni_scraper import DjinniJobScraper, is_djinni_country_eligible
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

    total_new = 0
    keywords = config.SEARCH_KEYWORDS if not test_mode else [config.SEARCH_KEYWORDS[0]]

    for loc in locations:
        scraper = LinkedInJobScraper(location=loc, remote_only=config.REMOTE_ONLY)
        for kw in keywords:
            logger.info(f"🔍 Поиск в регионе '{loc}' по слову: '{kw}'...")
            jobs = scraper.search_jobs(keyword=kw, limit=12)
            logger.info(f"[{loc} / {kw}] Найдено карточек: {len(jobs)}")

            for job in jobs:
                job_id = job["id"]
                job["region"] = loc
                if db.is_seen(job_id):
                    continue

                time.sleep(1.0)  # Вежливая задержка перед запросом деталей
                full_desc = scraper.get_job_description(job_id)
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
                        db.add_job(job)
                        continue

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
            logger.info(f"[Djinni / {kw}] Найдено карточек: {len(djinni_jobs)}")

            for job in djinni_jobs:
                job_id = job["id"]
                if db.is_seen(job_id):
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

    logger.info(
        f"🏁 Проверка завершена. Найдено новых вакансий: {total_new}. Всего в базе: {db.count_seen()}."
    )
    return total_new


def main():
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
