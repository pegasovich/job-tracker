"""
Greenhouse ATS Scraper for Direct Tech Company Career Portals.
Directly queries official Greenhouse Job Board APIs (boards-api.greenhouse.io)
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


class GreenhouseJobScraper:
    BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true"

    def __init__(self, companies: Optional[List[str]] = None):
        if companies is not None:
            self.companies = companies
        elif config and hasattr(config, "GREENHOUSE_COMPANIES"):
            self.companies = config.GREENHOUSE_COMPANIES
        else:
            self.companies = [
                "canonical",
                "gitlab",
                "elastic",
                "grafanalabs",
                "cloudflare",
                "mozilla",
                "figma",
                "stripe",
                "reddit",
                "cockroachlabs",
                "airtable",
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
                logger.warning(f"Unexpected status {resp.status} for Greenhouse company: {company}")
        except Exception as e:
            logger.error(f"Error querying Greenhouse API for '{company}': {e}")
        return None

    def search_jobs(
        self,
        companies: Optional[List[str]] = None,
        remote_only: bool = True,
        limit_per_company: int = 30,
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

                parsed = self._parse_single_job(job, company_fallback=company, remote_only=remote_only)
                if parsed:
                    all_jobs.append(parsed)
                    company_jobs_count += 1

        return all_jobs

    def _parse_single_job(
        self, job: Dict[str, Any], company_fallback: str, remote_only: bool = True
    ) -> Optional[Dict[str, Any]]:
        job_id = job.get("id")
        if not job_id:
            return None

        title = (job.get("title") or "").strip()
        company = (job.get("company_name") or company_fallback.capitalize()).strip()
        loc_data = job.get("location") or {}
        loc_name = (loc_data.get("name") if isinstance(loc_data, dict) else str(loc_data) or "").strip()

        # Remote / workplace classification
        text_for_remote = f"{title} {loc_name}".lower()
        is_remote = (
            "home based" in text_for_remote
            or "remote" in text_for_remote
            or "anywhere" in text_for_remote
            or "wfh" in text_for_remote
            or "distributed" in text_for_remote
        )

        if remote_only and not is_remote:
            return None

        if is_remote:
            workplace_type = "remote"
            location = f"Remote ({loc_name})" if loc_name and "remote" not in loc_name.lower() else (loc_name or "Remote")
        elif "hybrid" in text_for_remote:
            workplace_type = "hybrid"
            location = loc_name or "Hybrid"
        else:
            workplace_type = "onsite"
            location = loc_name or "On-Site"

        # Content cleaning
        raw_content = job.get("content") or ""
        clean_desc = html.unescape(re.sub(r"<[^>]+>", " ", raw_content))
        clean_desc = re.sub(r"\s+", " ", clean_desc).strip()

        # Check for salary mentions in content or title
        salary = ""
        sal_m = re.search(r'([$€£][\d,\s–-]+\b|\b\d+k\b)', title + " " + clean_desc[:400])
        if sal_m:
            salary = sal_m.group(1).strip()

        url = job.get("absolute_url") or f"https://boards.greenhouse.io/{company_fallback}/jobs/{job_id}"
        updated_at = (job.get("updated_at") or "")[:10]

        return {
            "id": f"gh_{company_fallback}_{job_id}",
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "posted_date": updated_at,
            "description": clean_desc,
            "salary": salary,
            "source": "Greenhouse",
            "workplace_type": workplace_type,
        }
