"""
JustJoin.it Scraper for QA / SDET Remote positions.
Extracts structured JobPostings via official candidate API with salary and tech stack.
"""

import urllib.request
import urllib.parse
import json
import random
import time
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


def has_polish_language_requirement(languages: Any) -> bool:
    """Detects if job requires Polish language based on JustJoin languages list."""
    if not languages or not isinstance(languages, list):
        return False
    for lang in languages:
        if isinstance(lang, dict):
            code = (lang.get("code") or "").strip().lower()
            name = (lang.get("name") or "").strip().lower()
            if code == "pl" or "polish" in name or "polski" in name:
                return True
        elif isinstance(lang, str):
            if lang.strip().lower() in ["pl", "polish", "polski"]:
                return True
    return False


def has_non_allowed_language_requirement(languages: Any, allowed_codes: list = None) -> bool:
    """Detects if job requires a language NOT in the allowed whitelist.

    Returns True if the job has language requirements and at least one required
    language is not in the allowed list (e.g. German, French, Spanish).
    Returns False if no language requirements or all required languages are allowed.
    """
    if allowed_codes is None:
        from config import ALLOWED_LANGUAGE_CODES
        allowed_codes = ALLOWED_LANGUAGE_CODES

    if not languages or not isinstance(languages, list):
        return False  # No requirements → OK

    allowed_set = {c.strip().lower() for c in allowed_codes}

    for lang in languages:
        if isinstance(lang, dict):
            code = (lang.get("code") or "").strip().lower()
            name = (lang.get("name") or "").strip().lower()
            if not code and not name:
                continue
            # Check if this language is NOT in the allowed list
            if code and code not in allowed_set:
                return True
            if not code and name and not any(a in name for a in allowed_set):
                return True
        elif isinstance(lang, str):
            val = lang.strip().lower()
            if val and val not in allowed_set:
                return True
    return False


class JustJoinJobScraper:
    BASE_SEARCH_URL = "https://justjoin.it/api/candidate-api/offers"
    OFFER_BASE_URL = "https://justjoin.it/offers/{}"

    def __init__(self):
        pass

    def _fetch_page(self, category: str = "testing", from_offset: int = 0) -> Optional[Dict[str, Any]]:
        query_params = {
            "categories": category,
            "from": from_offset,
        }
        url = f"{self.BASE_SEARCH_URL}?{urllib.parse.urlencode(query_params)}"

        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8", errors="ignore"))
                logger.warning(f"Unexpected status {resp.status} for JustJoin.it {url}")
        except Exception as e:
            logger.error(f"Error querying JustJoin.it API: {e}")
        return None

    def search_jobs(
        self,
        category: str = "testing",
        remote_only: bool = True,
        currency: str = "EUR",
        max_pages: int = 3,
        limit: int = 30,
        exclude_polish: bool = True,
    ) -> List[Dict[str, Any]]:
        jobs = []
        seen_guids = set()

        for page in range(max_pages):
            offset = page * 10
            data = self._fetch_page(category=category, from_offset=offset)
            if not data:
                break

            page_offers = data.get("data", [])
            if not page_offers:
                break

            for o in page_offers:
                guid = o.get("guid")
                if not guid or guid in seen_guids:
                    continue
                seen_guids.add(guid)

                workplace_type = (o.get("workplaceType") or "remote").lower()
                if remote_only and workplace_type != "remote":
                    continue

                if exclude_polish:
                    if has_polish_language_requirement(o.get("languages")):
                        logger.debug(f"Skipping JustJoin offer requiring Polish: '{o.get('title')}' @ {o.get('companyName')}")
                        continue
                    if is_polish_domestic_title(o.get("title") or ""):
                        logger.debug(f"Skipping JustJoin offer with Polish title: '{o.get('title')}' @ {o.get('companyName')}")
                        continue

                # Language whitelist filter: skip if job requires a language we don't speak
                if has_non_allowed_language_requirement(o.get("languages")):
                    logger.debug(f"Skipping JustJoin offer requiring non-allowed language: '{o.get('title')}' @ {o.get('companyName')}")
                    continue

                parsed_job = self._parse_single_offer(o, currency=currency, exclude_polish=exclude_polish)
                if parsed_job:
                    jobs.append(parsed_job)

                if len(jobs) >= limit:
                    break

            if len(jobs) >= limit:
                break

            time.sleep(random.uniform(0.3, 0.7))

        return jobs

    def _parse_single_offer(self, o: Dict[str, Any], currency: str = "EUR", exclude_polish: bool = False) -> Optional[Dict[str, Any]]:
        title = (o.get("title") or "").strip()
        company = (o.get("companyName") or "Unknown Company").strip()

        if exclude_polish:
            if has_polish_language_requirement(o.get("languages")) or is_polish_domestic_title(title):
                return None

        # Language whitelist filter
        if has_non_allowed_language_requirement(o.get("languages")):
            return None

        guid = o.get("guid")
        slug = o.get("slug") or guid
        workplace_type = (o.get("workplaceType") or "remote").lower()
        city = (o.get("city") or "").strip()

        # Location label
        if workplace_type == "remote":
            location = "Remote (Europe / Worldwide)"
        elif city:
            location = f"{workplace_type.capitalize()} ({city})"
        else:
            location = workplace_type.capitalize()

        # Salary formatting
        emp_types = o.get("employmentTypes") or []
        salary = ""
        if isinstance(emp_types, list) and emp_types:
            # 1. Try B2B with target currency (EUR)
            target = next(
                (e for e in emp_types if e.get("type") == "b2b" and e.get("currency") == currency),
                None,
            )
            # 2. Try any B2B
            if not target:
                target = next((e for e in emp_types if e.get("type") == "b2b"), None)
            # 3. Try any matching target currency
            if not target:
                target = next((e for e in emp_types if e.get("currency") == currency), None)
            # 4. Fallback to first available
            if not target:
                target = emp_types[0]

            fr = target.get("from")
            to = target.get("to")
            cur = target.get("currency") or currency
            stype = (target.get("type") or "").upper()

            if fr and to:
                salary = f"{int(fr)}–{int(to)} {cur}"
            elif fr:
                salary = f"from {int(fr)} {cur}"
            elif to:
                salary = f"up to {int(to)} {cur}"

            if salary and stype:
                salary += f" ({stype})"

        # Skills and experience snippet
        skills = [
            s.get("name").strip()
            for s in o.get("requiredSkills", [])
            if isinstance(s, dict) and s.get("name")
        ]
        exp = (o.get("experienceLevel") or "").strip()

        parts = []
        if exp:
            parts.append(f"Уровень: {exp.capitalize()}")
        if skills:
            parts.append(f"Навыки: {', '.join(skills[:6])}")

        description = " | ".join(parts) if parts else "JustJoin.it job offer"

        pub_date = (o.get("publishedAt") or "")[:10]

        return {
            "id": f"jjit_{guid}",
            "title": title,
            "company": company,
            "location": location,
            "url": self.OFFER_BASE_URL.format(slug),
            "posted_date": pub_date,
            "description": description,
            "salary": salary,
            "source": "JustJoinIT",
            "workplace_type": workplace_type,
        }
