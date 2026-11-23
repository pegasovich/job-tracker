"""Jobicy public remote-jobs API integration."""

import html
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from linkedin_scraper import LinkedInJobScraper

logger = logging.getLogger(__name__)


def is_eligible_for_ireland(location: str, description: str = "") -> bool:
    """Require an explicit location scope that includes Ireland."""
    loc = (location or "").strip().lower()
    if not loc:
        return False
    if LinkedInJobScraper.is_location_blocked(loc):
        return False
    eligibility_text = f"{loc} {description or ''}"
    if re.search(
        r"\b(?:excluding|except|outside)\s+(?:the\s+)?(?:republic\s+of\s+)?ireland\b|"
        r"\bireland\s+(?:is\s+)?(?:excluded|not\s+eligible|not\s+allowed)\b",
        eligibility_text,
        re.IGNORECASE,
    ):
        return False
    allowed = re.search(
        r"\b(ireland|europe|european union|\beu\b|emea|worldwide|anywhere|global)\b",
        loc,
        re.IGNORECASE,
    )
    # A generic remote label does not establish where the employer can hire.
    if not allowed:
        return False
    return not LinkedInJobScraper.is_description_blocked(description)


def clean_html(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


class JobicyJobScraper:
    BASE_URL = "https://jobicy.com/api/jobs"

    def _fetch(self, tag: str, count: int) -> List[Dict[str, Any]]:
        params = urllib.parse.urlencode({"count": min(max(count, 1), 100), "tag": tag})
        request = urllib.request.Request(
            f"{self.BASE_URL}?{params}",
            headers={"Accept": "application/json", "User-Agent": "QA-SDET-Job-Tracker/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
            if payload.get("success") is False:
                logger.warning("Jobicy API returned an unsuccessful response for tag %r", tag)
                return []
            jobs = payload.get("jobs", [])
            return jobs if isinstance(jobs, list) else []
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            logger.error("Jobicy API request failed for tag %r: %s", tag, exc)
            return []

    def search_jobs(self, tags: List[str], limit: int = 50) -> List[Dict[str, Any]]:
        found: Dict[str, Dict[str, Any]] = {}
        for index, tag in enumerate(tags):
            if index:
                time.sleep(1.0)  # Jobicy public API limit: at most one request per second.
            for raw in self._fetch(tag, min(limit, 100)):
                job_id = str(raw.get("id") or "").strip()
                title = str(raw.get("jobTitle") or "").strip()
                description = clean_html(str(raw.get("jobDescription") or raw.get("jobExcerpt") or ""))
                location = str(raw.get("jobGeo") or "").strip()
                if not job_id or not title or not LinkedInJobScraper.is_qa_title(title):
                    continue
                if not is_eligible_for_ireland(location, description):
                    continue

                job_types = raw.get("jobType") or []
                if isinstance(job_types, str):
                    job_types = [job_types]
                raw_type = ", ".join(str(item) for item in job_types)
                if re.search(r"\bB2B\b|business[- ]to[- ]business|independent contractor", description, re.I):
                    employment_type = f"{raw_type}; B2B stated" if raw_type else "B2B stated"
                elif re.search(r"contract|freelance", raw_type, re.I):
                    employment_type = f"{raw_type}; B2B not stated"
                else:
                    employment_type = f"{raw_type}; B2B not stated" if raw_type else "Not specified; B2B not stated"
                salary = ""
                low, high = raw.get("salaryMin"), raw.get("salaryMax")
                currency = str(raw.get("salaryCurrency") or "").upper()
                period = str(raw.get("salaryPeriod") or "")
                if low or high:
                    amount = f"{low or ''}{'–' if low and high else ''}{high or ''} {currency} {period}".strip()
                    salary = amount

                found[job_id] = {
                    "id": f"jobicy_{job_id}",
                    "title": title,
                    "company": str(raw.get("companyName") or "Unknown Company").strip(),
                    "location": f"Remote ({location})",
                    "url": str(raw.get("url") or "").strip(),
                    "posted_date": str(raw.get("pubDate") or "")[:10],
                    "description": description,
                    "salary": salary,
                    "employment_type": employment_type,
                    "source": "Jobicy",
                    "workplace_type": "remote",
                }
                if len(found) >= limit:
                    return list(found.values())
        return list(found.values())
