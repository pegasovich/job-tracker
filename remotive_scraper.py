"""
Remotive Job Board API Scraper for Remote QA / SDET positions.
Queries official Remotive API (https://remotive.com/api/remote-jobs?category=qa)
Filters for worldwide/Europe/Ireland remote roles with structured candidate location checks.
"""

import urllib.request
import urllib.parse
import json
import re
import html
import random
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

# Locations that explicitly include Ireland / Europe / Worldwide candidates
ALLOWED_LOCATION_PATTERNS = [
    r'\bworldwide\b',
    r'\banywhere\b',
    r'\bglobal\b',
    r'\beurope\b',
    r'\beu\b',
    r'\bemea\b',
    r'\bireland\b',
    r'\ball\b',
]

# Disallowed domestic regions when not combined with worldwide/Europe
BLOCKED_LOCATION_PATTERNS = [
    r'\busa?\b',
    r'\bunited\s+states\b',
    r'\bcanada\b',
    r'\blatam\b',
    r'\blatin\s+america\b',
    r'\bsouth\s+america\b',
    r'\bapac\b',
    r'\basia\b',
    r'\bindia\b',
    r'\bphilippines\b',
    r'\bpakistan\b',
    r'\bbrazil\b',
    r'\bargentina\b',
    r'\bcolombia\b',
    r'\bmexico\b',
    r'\baustralia\b',
    r'\bnew\s+zealand\b',
    r'\bafrica\b',
    r'\bnigeria\b',
    # Country-only remote restrictions do not include candidates in Ireland.
    # Broad Europe / EMEA / Worldwide markers are checked first and still pass.
    r'\b(united kingdom|uk|england|scotland|wales|northern ireland|germany|france|spain|portugal|italy|netherlands|poland|sweden|norway|denmark|finland|switzerland|austria|belgium|czechia|czech republic|romania|bulgaria|greece|croatia|estonia|latvia|lithuania|cyprus|malta|slovakia|slovenia|hungary|luxembourg|iceland|serbia|bosnia|montenegro|albania|north macedonia|moldova|ukraine|turkey|türkiye)\b',
]


def is_remotive_location_eligible(location: str) -> bool:
    """
    Check if a Remotive candidate location allows Ireland/Europe/Worldwide candidates.
    If location is empty, assume open.
    If it explicitly specifies an allowed region (worldwide, europe, emea, or Ireland), return True.
    If it only specifies a blocked region (e.g. USA, LATAM, APAC) without allowed regions, return False.
    """
    if not location or not location.strip():
        return True

    loc_lower = location.lower().strip()

    # "Northern Ireland" must not pass just because it contains the word Ireland.
    loc_for_ireland_match = re.sub(r'\bnorthern\s+ireland\b', '', loc_lower)
    is_allowed = any(re.search(pat, loc_for_ireland_match) for pat in ALLOWED_LOCATION_PATTERNS)
    if is_allowed:
        return True

    is_blocked = any(re.search(pat, loc_lower) for pat in BLOCKED_LOCATION_PATTERNS)
    if is_blocked:
        return False

    # If it's a specific European country name not matched above (e.g., "Germany, France")
    # or neutral text, default to True
    return True


class RemotiveJobScraper:
    BASE_URL = "https://remotive.com/api/remote-jobs"

    def __init__(self, category: str = "qa"):
        self.category = category

    def _fetch_jobs(self, category: Optional[str] = "qa", search: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        params = {}
        if category:
            params["category"] = category
        if search:
            params["search"] = search

        query_str = f"?{urllib.parse.urlencode(params)}" if params else ""
        url = f"{self.BASE_URL}{query_str}"

        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                    return data.get("jobs", [])
                logger.warning(f"Unexpected status {resp.status} for Remotive API: {url}")
        except Exception as e:
            logger.error(f"Error querying Remotive API: {e}")
        return None

    @staticmethod
    def is_qa_title(title: str) -> bool:
        from linkedin_scraper import LinkedInJobScraper
        return LinkedInJobScraper.is_qa_title(title)

    def search_jobs(
        self,
        category: Optional[str] = "qa",
        remote_only: bool = True,
        limit: int = 50,
        qa_only: bool = True,
    ) -> List[Dict[str, Any]]:
        raw_jobs = self._fetch_jobs(category=category)
        if not raw_jobs:
            return []

        all_jobs = []
        for job in raw_jobs:
            if len(all_jobs) >= limit:
                break

            title = (job.get("title") or "").strip()
            if qa_only and not self.is_qa_title(title):
                continue

            parsed = self._parse_single_job(job, remote_only=remote_only)
            if parsed:
                all_jobs.append(parsed)

        return all_jobs

    def _parse_single_job(self, job: Dict[str, Any], remote_only: bool = True) -> Optional[Dict[str, Any]]:
        job_id = job.get("id")
        if not job_id:
            return None

        title = (job.get("title") or "").strip()
        company = (job.get("company_name") or "Unknown Company").strip()
        candidate_loc = (job.get("candidate_required_location") or "").strip()

        # Location eligibility check (e.g. discard USA-only or LATAM-only)
        if not is_remotive_location_eligible(candidate_loc):
            return None

        # Clean HTML description
        raw_html = job.get("description") or ""
        clean_desc = html.unescape(re.sub(r"<[^>]+>", " ", raw_html))
        clean_desc = re.sub(r"\s+", " ", clean_desc).strip()

        # Remotive jobs are 100% remote
        workplace_type = "remote"
        location = f"Remote ({candidate_loc})" if candidate_loc else "Remote (Worldwide)"

        salary = (job.get("salary") or "").strip()
        if not salary:
            sal_m = re.search(r'([$€£][\d,\s–-]+\b|\b\d+k\b)', title + " " + clean_desc[:400])
            if sal_m:
                salary = sal_m.group(1).strip()

        url = job.get("url") or f"https://remotive.com/remote-jobs/{job_id}"
        pub_date = (job.get("publication_date") or "")[:10]

        return {
            "id": f"remotive_{job_id}",
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "posted_date": pub_date,
            "description": clean_desc,
            "salary": salary,
            "source": "Remotive",
            "workplace_type": workplace_type,
        }
