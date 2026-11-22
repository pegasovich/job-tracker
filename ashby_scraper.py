"""
Ashby ATS Scraper for Direct Tech Company Career Portals.
Directly queries official Ashby Job Board APIs (api.ashbyhq.com/posting-api/job-board/{company})
for remote QA / SDET openings with zero middleman or scraper bans.
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


class AshbyJobScraper:
    BASE_URL = "https://api.ashbyhq.com/posting-api/job-board/{company}"

    def __init__(self, companies: Optional[List[str]] = None):
        if companies is not None:
            self.companies = companies
        elif config and hasattr(config, "ASHBY_COMPANIES"):
            self.companies = config.ASHBY_COMPANIES
        else:
            self.companies = [
                "linear",
                "synthesia",
                "notion",
                "ramp",
                "posthog",
                "snyk",
                "zapier",
                "vanta",
                "webflow",
                "surveymonkey",
                "replit",
                "openai",
                "perplexity",
                "cursor",
                "cognition",
                "modal",
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
                    return json.loads(resp.read().decode("utf-8", errors="ignore"))
                logger.warning(f"Unexpected status {resp.status} for Ashby company: {company}")
        except Exception as e:
            logger.error(f"Error querying Ashby API for '{company}': {e}")
        return None

    @staticmethod
    def is_qa_title(title: str) -> bool:
        from linkedin_scraper import LinkedInJobScraper
        return LinkedInJobScraper.is_qa_title(title)

    def search_jobs(
        self,
        companies: Optional[List[str]] = None,
        remote_only: bool = True,
        limit_per_company: int = 30,
        qa_only: bool = True,
    ) -> List[Dict[str, Any]]:
        target_companies = companies or self.companies
        all_jobs = []

        for company in target_companies:
            data = self._fetch_company_jobs(company)
            if not data:
                continue

            raw_jobs = data.get("jobs", [])
            company_jobs_count = 0

            for job in raw_jobs:
                if company_jobs_count >= limit_per_company:
                    break

                title = (job.get("title") or "").strip()
                if qa_only and not self.is_qa_title(title):
                    continue

                parsed = self._parse_single_job(job, company_fallback=company, remote_only=remote_only)
                if parsed:
                    all_jobs.append(parsed)
                    company_jobs_count += 1

        return all_jobs

    def _parse_single_job(
        self,
        job: Dict[str, Any],
        company_fallback: str,
        remote_only: bool = True,
    ) -> Optional[Dict[str, Any]]:
        job_id = job.get("id")
        if not job_id:
            return None

        title = (job.get("title") or "").strip()
        company = company_fallback.capitalize()
        loc_name = (job.get("location") or "").strip()
        workplace_type_raw = (job.get("workplaceType") or "").strip().lower()
        is_remote_flag = job.get("isRemote") is True

        # Extract address metadata if available
        address_obj = job.get("address") or {}
        postal_addr = address_obj.get("postalAddress") or {}
        country = (postal_addr.get("addressCountry") or "").strip()

        # Check geographic block on location name or country
        from linkedin_scraper import LinkedInJobScraper
        if remote_only and loc_name and LinkedInJobScraper.is_location_blocked(loc_name):
            return None
        if remote_only and country and LinkedInJobScraper.is_location_blocked(country):
            return None

        # Remote / workplace classification
        text_for_remote = f"{title} {loc_name} {workplace_type_raw}".lower()
        is_remote = (
            is_remote_flag
            or workplace_type_raw == "remote"
            or "remote" in text_for_remote
            or "home based" in text_for_remote
            or "anywhere" in text_for_remote
            or "wfh" in text_for_remote
            or "distributed" in text_for_remote
        )

        if remote_only and not is_remote:
            return None

        if is_remote:
            workplace_type = "remote"
            location = f"Remote ({loc_name})" if loc_name and "remote" not in loc_name.lower() else (loc_name or "Remote")
        elif workplace_type_raw == "hybrid" or "hybrid" in text_for_remote:
            workplace_type = "hybrid"
            location = loc_name or "Hybrid"
        else:
            workplace_type = "onsite"
            location = loc_name or "On-Site"

        # Content cleaning
        description = job.get("descriptionPlain") or ""
        if not description:
            raw_html = job.get("descriptionHtml") or ""
            clean = html.unescape(re.sub(r"<[^>]+>", " ", raw_html))
            description = re.sub(r"\s+", " ", clean).strip()

        # Reject jobs with domestic US/foreign regional restrictions in description
        if remote_only and LinkedInJobScraper.is_description_blocked(description):
            return None

        # Check for salary mentions in text or description
        salary = ""
        # Ashby sometimes includes compensation tiers in secondary metadata
        sal_m = re.search(
            r'([$€£]\s*[\d,\.]+\s*(?:k|K)?(?:\s*[-–]\s*[$€£]?\s*[\d,\.]+\s*(?:k|K)?)?(?:/(?:hr|hour|day|year|mo|month|yr))?|\b\d+k\b)',
            title + " " + description[:400],
            re.IGNORECASE,
        )
        if sal_m:
            salary = sal_m.group(1).strip()

        # URL
        url = job.get("jobUrl") or job.get("applyUrl") or f"https://jobs.ashbyhq.com/{company_fallback}/{job_id}"

        # Published date
        published_at = job.get("publishedAt") or ""
        posted_date = published_at[:10] if published_at else ""

        return {
            "id": f"ashby_{company_fallback}_{job_id}",
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "posted_date": posted_date,
            "description": description,
            "salary": salary,
            "source": "Ashby",
            "workplace_type": workplace_type,
        }
