"""
No Fluff Jobs (nofluffjobs.com) Scraper for QA / SDET Remote positions.
Queries official search API with structured salaries, technology stack and B2B tags.
"""

import urllib.request
import urllib.parse
import json
import datetime
import random
import logging
from typing import List, Dict, Optional, Any
from config import is_polish_domestic_title

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]


def has_polish_language_tile(tiles: Any) -> bool:
    """Detects if job requires Polish language based on NoFluffJobs tiles."""
    if isinstance(tiles, dict):
        values = tiles.get("values", [])
    elif isinstance(tiles, list):
        values = tiles
    else:
        values = []

    for item in values:
        if isinstance(item, dict):
            val = (item.get("value") or "").strip().lower()
            itype = (item.get("type") or "").strip().lower()
            if val in ["pl", "polish", "polski"] or (itype == "joblanguage" and val == "pl"):
                return True
        elif isinstance(item, str):
            if item.strip().lower() in ["pl", "polish", "polski"]:
                return True
    return False


def has_non_allowed_language_tile(tiles: Any, allowed_codes: list = None) -> bool:
    """Detects if job requires a language NOT in the allowed whitelist based on NoFluffJobs tiles.

    Returns True if the job has language tiles and at least one required
    language is not in the allowed list (e.g. German, French, Spanish).
    Returns False if no language tiles or all required languages are allowed.
    """
    if allowed_codes is None:
        from config import ALLOWED_LANGUAGE_CODES
        allowed_codes = ALLOWED_LANGUAGE_CODES

    allowed_set = {c.strip().lower() for c in allowed_codes}

    if isinstance(tiles, dict):
        values = tiles.get("values", [])
    elif isinstance(tiles, list):
        values = tiles
    else:
        return False

    for item in values:
        if isinstance(item, dict):
            val = (item.get("value") or "").strip().lower()
            itype = (item.get("type") or "").strip().lower()
            if itype == "joblanguage" and val and val not in allowed_set:
                return True
        elif isinstance(item, str):
            # Raw string language codes
            stripped = item.strip().lower()
            if stripped and stripped not in allowed_set and len(stripped) <= 3:
                return True
    return False


class NoFluffJobScraper:
    BASE_SEARCH_URL = "https://nofluffjobs.com/api/search/posting"
    JOB_BASE_URL = "https://nofluffjobs.com/job/{}"

    def __init__(self):
        pass

    def _make_request(self, category: str, remote_only: bool, currency: str, limit: int) -> Optional[Dict[str, Any]]:
        query_params = {
            "limit": limit,
            "offset": 0,
            "salaryCurrency": currency,
            "salaryPeriod": "month",
            "region": "world",
        }
        url = f"{self.BASE_SEARCH_URL}?{urllib.parse.urlencode(query_params)}"

        criteria: Dict[str, Any] = {"category": [category]}
        if remote_only:
            criteria["city"] = ["remote"]

        payload = json.dumps({"page": 1, "criteriaSearch": criteria}).encode("utf-8")

        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }

        req = urllib.request.Request(url, data=payload, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8", errors="ignore"))
                logger.warning(f"Unexpected status {resp.status} for No Fluff Jobs search")
        except Exception as e:
            logger.error(f"Error querying No Fluff Jobs API: {e}")
        return None

    def search_jobs(
        self,
        category: str = "testing",
        remote_only: bool = True,
        currency: str = "EUR",
        limit: int = 50,
        exclude_polish: bool = True,
    ) -> List[Dict[str, Any]]:
        data = self._make_request(category=category, remote_only=remote_only, currency=currency, limit=limit)
        if not data:
            return []
        return self.parse_postings(data, currency=currency, limit=limit, exclude_polish=exclude_polish)

    def parse_postings(
        self,
        data: Dict[str, Any],
        currency: str = "EUR",
        limit: int = 50,
        exclude_polish: bool = False
    ) -> List[Dict[str, Any]]:
        postings = data.get("postings", [])
        jobs = []
        seen_ids = set()

        for p in postings:
            if len(jobs) >= limit:
                break

            raw_id = p.get("id")
            if not raw_id:
                continue

            title = (p.get("title") or "").strip()
            company = (p.get("name") or "Unknown Company").strip()
            tiles = p.get("tiles", {})

            # Filter out domestic Polish positions and requirements
            if exclude_polish:
                if has_polish_language_tile(tiles):
                    logger.debug(f"Skipping NoFluff offer requiring Polish: '{title}' @ {company}")
                    continue
                if is_polish_domestic_title(title):
                    logger.debug(f"Skipping NoFluff offer with Polish title: '{title}' @ {company}")
                    continue

            # Language whitelist filter: skip if job requires a language we don't speak
            if has_non_allowed_language_tile(tiles):
                logger.debug(f"Skipping NoFluff offer requiring non-allowed language: '{title}' @ {company}")
                continue

            job_id = f"nfj_{raw_id}"
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            url_slug = p.get("url") or raw_id
            job_url = self.JOB_BASE_URL.format(url_slug)

            # Salary parsing
            sal_data = p.get("salary")
            salary = ""
            if isinstance(sal_data, dict):
                fr = sal_data.get("from")
                to = sal_data.get("to")
                cur = sal_data.get("currency") or currency
                stype = (sal_data.get("type") or "").upper()
                if fr and to:
                    salary = f"{int(fr)}–{int(to)} {cur}"
                elif fr:
                    salary = f"from {int(fr)} {cur}"
                elif to:
                    salary = f"up to {int(to)} {cur}"
                if salary and stype:
                    salary += f" ({stype})"

            # Requirements & tech stack extraction
            skills = []
            tiles = p.get("tiles", {})
            if isinstance(tiles, dict):
                for item in tiles.get("values", []):
                    if isinstance(item, dict) and item.get("value"):
                        val = item["value"].strip()
                        if val.lower() not in ["en", "pl", "uk"]:
                            skills.append(val)

            tech = p.get("technology")
            seniority_list = p.get("seniority") or []
            seniority = ", ".join(seniority_list) if isinstance(seniority_list, list) else str(seniority_list)

            desc_parts = []
            if seniority:
                desc_parts.append(f"Уровень: {seniority}")
            if tech:
                desc_parts.append(f"Основной стек: {tech}")
            if skills:
                desc_parts.append(f"Навыки: {', '.join(skills[:8])}")

            description = " | ".join(desc_parts) if desc_parts else "No Fluff Jobs posting"

            # Posted date
            posted_ms = p.get("posted")
            posted_date = ""
            if posted_ms and isinstance(posted_ms, (int, float)):
                try:
                    posted_date = datetime.datetime.fromtimestamp(
                        posted_ms / 1000, datetime.timezone.utc
                    ).strftime("%Y-%m-%d")
                except Exception:
                    pass

            jobs.append({
                "id": job_id,
                "title": title,
                "company": company,
                "location": "Remote (Europe / Worldwide)",
                "url": job_url,
                "posted_date": posted_date,
                "description": description,
                "salary": salary,
                "source": "NoFluffJobs",
                "workplace_type": "remote",
            })

        return jobs
