"""
Adzuna API Scraper for Ireland and UK QA / SDET Remote positions.
Official REST API client with structured salaries, geolocation and employer info.
"""

import urllib.request
import urllib.parse
import json
import re
import html
import logging
from typing import List, Dict, Optional, Any

try:
    import config
except ImportError:
    config = None

logger = logging.getLogger(__name__)

CURRENCY_SYMBOLS = {
    "ie": "€",
    "gb": "£",
    "us": "$",
}


class AdzunaJobScraper:
    BASE_SEARCH_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_key: Optional[str] = None,
        countries: Optional[List[str]] = None,
    ):
        if app_id is not None:
            self.app_id = app_id
        else:
            self.app_id = getattr(config, "ADZUNA_APP_ID", "") if config else ""

        if app_key is not None:
            self.app_key = app_key
        else:
            self.app_key = getattr(config, "ADZUNA_APP_KEY", "") if config else ""

        if countries is not None:
            self.countries = countries
        else:
            self.countries = getattr(config, "ADZUNA_COUNTRIES", ["ie", "gb"]) if config else ["ie", "gb"]

    @property
    def is_configured(self) -> bool:
        return bool(self.app_id and self.app_key)

    def _fetch_page(
        self, country: str, page: int, what: str, results_per_page: int = 20
    ) -> Optional[Dict[str, Any]]:
        if not self.is_configured:
            return None

        url = self.BASE_SEARCH_URL.format(country=country, page=page)
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": results_per_page,
            "what": what,
            "content-type": "application/json",
        }
        full_url = f"{url}?{urllib.parse.urlencode(params)}"

        headers = {
            "Accept": "application/json",
            "User-Agent": "JobTracker-Automation/1.0",
        }

        req = urllib.request.Request(full_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8", errors="ignore"))
                logger.warning(f"Unexpected status {resp.status} for Adzuna {country} search")
        except Exception as e:
            logger.error(f"Error querying Adzuna API ({country}): {e}")
        return None

    def search_jobs(
        self,
        keywords: Optional[List[str]] = None,
        remote_only: bool = True,
        max_pages: int = 1,
        results_per_page: int = 20,
    ) -> List[Dict[str, Any]]:
        if not self.is_configured:
            logger.warning(
                "Adzuna API credentials are not configured (ADZUNA_APP_ID or ADZUNA_APP_KEY empty). Skipping."
            )
            return []

        if keywords is None:
            keywords = getattr(config, "ADZUNA_KEYWORDS", ["QA Engineer", "SDET"]) if config else ["QA Engineer"]

        jobs = []
        seen_ids = set()

        for country in self.countries:
            cur_sym = CURRENCY_SYMBOLS.get(country.lower(), "€")
            for kw in keywords:
                for page in range(1, max_pages + 1):
                    data = self._fetch_page(
                        country=country, page=page, what=kw, results_per_page=results_per_page
                    )
                    if not data:
                        break

                    results = data.get("results", [])
                    if not results:
                        break

                    for item in results:
                        job_id = f"adzuna_{item.get('id')}"
                        if job_id in seen_ids:
                            continue
                        seen_ids.add(job_id)

                        raw_title = item.get("title", "")
                        clean_title = html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()

                        raw_desc = item.get("description", "")
                        clean_desc = html.unescape(re.sub(r"<[^>]+>", " ", raw_desc))
                        clean_desc = re.sub(r"\s+", " ", clean_desc).strip()

                        loc_obj = item.get("location", {})
                        loc_display = loc_obj.get("display_name", country.upper())

                        # Remote detection
                        text_for_remote = f"{clean_title} {clean_desc} {loc_display}".lower()
                        is_remote = "remote" in text_for_remote or "work from home" in text_for_remote or "wfh" in text_for_remote

                        if remote_only and not is_remote:
                            continue

                        workplace_type = "remote" if is_remote else "onsite"

                        # Company name
                        company = item.get("company", {}).get("display_name", "Unknown Company")

                        # Salary extraction
                        salary = ""
                        sal_min = item.get("salary_min")
                        sal_max = item.get("salary_max")
                        c_type = (item.get("contract_type") or "").upper()

                        if sal_min and sal_max and sal_min > 0 and sal_max > 0:
                            salary = f"{int(sal_min):,}–{int(sal_max):,} {cur_sym}".replace(",", " ")
                        elif sal_min and sal_min > 0:
                            salary = f"from {int(sal_min):,} {cur_sym}".replace(",", " ")
                        elif sal_max and sal_max > 0:
                            salary = f"up to {int(sal_max):,} {cur_sym}".replace(",", " ")

                        if salary and c_type:
                            salary += f" ({c_type})"

                        jobs.append({
                            "id": job_id,
                            "title": clean_title,
                            "company": company,
                            "location": f"Remote ({loc_display})" if is_remote else loc_display,
                            "url": item.get("redirect_url", ""),
                            "posted_date": (item.get("created") or "")[:10],
                            "description": clean_desc,
                            "salary": salary,
                            "source": "Adzuna",
                            "workplace_type": workplace_type,
                            "region": country.upper(),
                        })

        return jobs
