"""
Himalayas API Scraper for Global and European Remote QA / SDET Positions.
Directly queries official Himalayas Jobs API (https://himalayas.app/jobs/api)
with structured location and timezone restriction validation.
"""

import urllib.request
import urllib.parse
import json
import re
import html
import random
import datetime
import logging
from typing import List, Dict, Optional, Any

try:
    import config
except ImportError:
    config = None

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]

IRELAND_ELIGIBLE_LOCATION_SCOPES = {
    "ireland", "republic of ireland",
    "europe", "pan-european", "european union", "eu", "emea",
    "worldwide", "anywhere", "global",
}


def is_himalayas_location_eligible(
    loc_restrictions: Optional[List[str]],
    tz_restrictions: Optional[List[float]] = None,
    allowed_timezones: Optional[List[float]] = None,
) -> bool:
    """
    Check whether Himalayas explicitly allows a candidate in Ireland or a broad
    region that includes Ireland.
    - Empty loc_restrictions indicates open worldwide.
    - A country-specific restriction must name Ireland; another country such as
      the UK or Netherlands does not make the role Ireland-eligible.
    - Broad scopes such as Europe, EMEA, or Worldwide are accepted.
    - If tz_restrictions is specified, it must overlap with Irish / EMEA timezones (-2 to +4).
    """
    # 1. Location restrictions check
    if loc_restrictions:
        locs_lower = {str(l).lower().strip() for l in loc_restrictions}
        has_allowed = bool(locs_lower.intersection(IRELAND_ELIGIBLE_LOCATION_SCOPES))
        if not has_allowed:
            return False

    # 2. Timezone restrictions check (Ireland is UTC 0 in winter, UTC +1 in summer)
    if tz_restrictions:
        target_tz_range = allowed_timezones if allowed_timezones is not None else [-2, -1, 0, 1, 2, 3, 4]
        has_tz_overlap = any(tz in target_tz_range for tz in tz_restrictions)
        if not has_tz_overlap:
            return False

    return True


class HimalayasJobScraper:
    BASE_URL = "https://himalayas.app/jobs/api"

    def __init__(self, max_pages: int = 5, limit_per_page: int = 20):
        self.max_pages = max_pages
        self.limit_per_page = limit_per_page

    def _fetch_page(self, offset: int = 0) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE_URL}?offset={offset}&limit={self.limit_per_page}"
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
                logger.warning(f"Unexpected status {resp.status} for Himalayas API")
        except Exception as e:
            logger.error(f"Error querying Himalayas API at offset {offset}: {e}")
        return None

    @staticmethod
    def is_qa_title(title: str) -> bool:
        from linkedin_scraper import LinkedInJobScraper
        return LinkedInJobScraper.is_qa_title(title)

    def search_jobs(
        self,
        max_pages: Optional[int] = None,
        remote_only: bool = True,
        qa_only: bool = True,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        pages_to_crawl = max_pages or getattr(config, "HIMALAYAS_MAX_PAGES", self.max_pages) if config else self.max_pages
        allowed_tz = getattr(config, "HIMALAYAS_ALLOWED_TIMEZONES", [-2, -1, 0, 1, 2, 3, 4]) if config else [-2, -1, 0, 1, 2, 3, 4]
        all_jobs = []

        for page in range(pages_to_crawl):
            if len(all_jobs) >= limit:
                break

            offset = page * self.limit_per_page
            data = self._fetch_page(offset=offset)
            if not data:
                break

            raw_jobs = data.get("jobs", [])
            if not raw_jobs:
                break

            for job in raw_jobs:
                if len(all_jobs) >= limit:
                    break

                title = (job.get("title") or "").strip()
                if qa_only and not self.is_qa_title(title):
                    continue

                parsed = self._parse_single_job(job, allowed_timezones=allowed_tz)
                if parsed:
                    all_jobs.append(parsed)

        return all_jobs

    def _parse_single_job(
        self,
        job: Dict[str, Any],
        allowed_timezones: Optional[List[float]] = None,
    ) -> Optional[Dict[str, Any]]:
        guid = job.get("guid") or str(job.get("id") or "")
        if not guid:
            return None

        title = (job.get("title") or "").strip()
        company = (job.get("companyName") or "Unknown Company").strip()
        loc_restrictions = job.get("locationRestrictions") or []
        tz_restrictions = job.get("timezoneRestrictions") or []

        # 1. Geographic and timezone eligibility for Ireland
        if not is_himalayas_location_eligible(loc_restrictions, tz_restrictions, allowed_timezones):
            return None

        # 2. Check description stop patterns
        raw_desc = job.get("description") or job.get("excerpt") or ""
        clean_desc = html.unescape(re.sub(r"<[^>]+>", " ", raw_desc))
        clean_desc = re.sub(r"\s+", " ", clean_desc).strip()

        from linkedin_scraper import LinkedInJobScraper
        if LinkedInJobScraper.is_description_blocked(clean_desc):
            return None

        # Format location label
        if not loc_restrictions:
            location_label = "Remote (Worldwide)"
        elif "Ireland" in loc_restrictions:
            location_label = "Remote (Ireland)"
        else:
            loc_summary = ", ".join(loc_restrictions[:3])
            location_label = f"Remote ({loc_summary})"

        # Format salary if structured or from text
        salary = ""
        min_sal = job.get("minSalary")
        max_sal = job.get("maxSalary")
        curr = job.get("currency") or "$"
        period = job.get("salaryPeriod") or "year"

        if min_sal and max_sal:
            salary = f"{curr}{min_sal:,.0f} - {curr}{max_sal:,.0f} / {period}"
        elif min_sal:
            salary = f"{curr}{min_sal:,.0f} / {period}"
        else:
            sal_m = re.search(r'([$€£][\d,\s–-]+\b|\b\d+k\b)', title + " " + clean_desc[:400])
            if sal_m:
                salary = sal_m.group(1).strip()

        # Application URL
        url = job.get("applicationLink")
        if not url:
            comp_slug = job.get("companySlug") or "company"
            url = f"https://himalayas.app/companies/{comp_slug}/jobs/{guid}"

        # Date formatting
        pub_date = job.get("pubDate")
        posted_date = ""
        if pub_date:
            try:
                # Handles ISO or RFC formats e.g. 2026-11-20T...
                posted_date = pub_date[:10]
            except Exception:
                posted_date = ""

        return {
            "id": f"himalayas_{guid}",
            "title": title,
            "company": company,
            "location": location_label,
            "url": url,
            "posted_date": posted_date,
            "description": clean_desc,
            "salary": salary,
            "source": "Himalayas",
            "workplace_type": "remote",
        }
