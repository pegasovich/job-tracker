"""Workable ATS scraper for direct tech company career portals.

Queries public Workable widget endpoints:
https://apply.workable.com/api/v1/widget/accounts/{company}?details=true
"""

import html
import json
import logging
import random
import re
from typing import Any, Dict, List, Optional
import urllib.request

try:
    import config
except ImportError:
    config = None

from linkedin_scraper import LinkedInJobScraper

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]


class WorkableJobScraper:
    """Fetch QA/SDET roles from public Workable widget JSON endpoints."""

    BASE_URL = "https://apply.workable.com/api/v1/widget/accounts/{company}?details=true"

    def __init__(self, companies: Optional[List[str]] = None):
        if companies is not None:
            self.companies = companies
        elif config and hasattr(config, "WORKABLE_COMPANIES"):
            self.companies = config.WORKABLE_COMPANIES
        else:
            self.companies = [
                "tekenable",
                "seeq",
                "zyte",
                "careacross",
                "itrex-group",
                "libertex-europe",
                "talent-voyager",
                "winthrop-technologies",
            ]

    def _fetch_company_jobs(self, company: str) -> Optional[Dict[str, Any]]:
        url = self.BASE_URL.format(company=company)
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                    return data if isinstance(data, dict) else None
                logger.warning("Unexpected status %s for Workable company: %s", resp.status, company)
        except Exception as exc:
            logger.error("Error querying Workable API for '%s': %s", company, exc)
        return None

    @staticmethod
    def is_qa_title(title: str) -> bool:
        return LinkedInJobScraper.is_qa_title(title)

    def search_jobs(
        self,
        companies: Optional[List[str]] = None,
        remote_only: bool = True,
        limit_per_company: int = 30,
        qa_only: bool = True,
    ) -> List[Dict[str, Any]]:
        target_companies = companies or self.companies
        all_jobs: List[Dict[str, Any]] = []
        classifier = LinkedInJobScraper(location="Ireland")

        for company in target_companies:
            payload = self._fetch_company_jobs(company)
            if not payload:
                continue

            company_label = (payload.get("name") or company.replace("-", " ").title()).strip()
            raw_jobs = payload.get("jobs") or []
            company_jobs_count = 0

            for job in raw_jobs:
                if company_jobs_count >= limit_per_company:
                    break
                if not isinstance(job, dict):
                    continue
                title = (job.get("title") or "").strip()
                if qa_only and not self.is_qa_title(title):
                    continue

                parsed = self._parse_single_job(
                    job,
                    company_slug=company,
                    company_name=company_label,
                    remote_only=remote_only,
                    classifier=classifier,
                )
                if parsed:
                    all_jobs.append(parsed)
                    company_jobs_count += 1

        return all_jobs

    def _parse_single_job(
        self,
        job: Dict[str, Any],
        company_slug: str,
        company_name: str = "",
        remote_only: bool = True,
        classifier: Optional[LinkedInJobScraper] = None,
    ) -> Optional[Dict[str, Any]]:
        job_id = str(job.get("shortcode") or job.get("code") or "").strip()
        if not job_id:
            return None

        title = (job.get("title") or "").strip()
        company = company_name or company_slug.replace("-", " ").title()

        city = (job.get("city") or "").strip()
        country = (job.get("country") or "").strip()
        loc_parts = [p for p in (city, country) if p]
        raw_loc = ", ".join(loc_parts)
        if not raw_loc and isinstance(job.get("locations"), list) and job["locations"]:
            first_loc = job["locations"][0]
            if isinstance(first_loc, dict):
                raw_loc = ", ".join(
                    str(first_loc.get(k) or "").strip()
                    for k in ("city", "country")
                    if first_loc.get(k)
                )

        telecommuting = job.get("telecommuting") is True
        is_remote = telecommuting or "remote" in f"{title} {raw_loc}".lower()

        if remote_only and not is_remote:
            return None
        if remote_only and raw_loc and LinkedInJobScraper.is_location_blocked(raw_loc):
            return None

        raw_html = job.get("description") or ""
        clean_desc = html.unescape(re.sub(r"<[^>]+>", " ", raw_html))
        description = re.sub(r"\s+", " ", clean_desc).strip()

        if remote_only and LinkedInJobScraper.is_description_blocked(description):
            return None

        classifier = classifier or LinkedInJobScraper(location="Ireland")
        title_hint = f"{title} (Remote)" if is_remote and "remote" not in title.lower() else title
        detected = classifier.detect_workplace_type(title_hint, raw_loc or "Remote", description)

        if remote_only and detected != "remote":
            return None

        workplace_type = detected if detected in ("remote", "hybrid", "onsite") else ("remote" if is_remote else "onsite")
        location = f"Remote ({raw_loc})" if is_remote and raw_loc and "remote" not in raw_loc.lower() else (raw_loc or ("Remote" if is_remote else "On-Site"))

        salary = ""
        sal_m = re.search(
            r'([$€£]\s*[\d,\.]+\s*(?:k|K)?(?:\s*[-–]\s*[$€£]?\s*[\d,\.]+\s*(?:k|K)?)?(?:/(?:hr|hour|day|year|mo|month|yr))?|\b\d+k\b)',
            f"{title} {description[:400]}",
            re.IGNORECASE,
        )
        if sal_m:
            salary = sal_m.group(1).strip()

        url = (job.get("url") or job.get("shortlink") or job.get("application_url") or f"https://apply.workable.com/j/{job_id}").strip()
        posted_date = str(job.get("published_on") or job.get("created_at") or "")[:10]
        emp_type = (job.get("employment_type") or "").strip()

        result: Dict[str, Any] = {
            "id": f"workable_{company_slug}_{job_id}",
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "posted_date": posted_date,
            "description": description,
            "salary": salary,
            "source": "Workable",
            "workplace_type": workplace_type,
        }
        if emp_type:
            result["employment_type"] = emp_type
        return result
