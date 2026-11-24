"""Working Nomads public remote-jobs JSON feed integration."""

import hashlib
import logging
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List

import config
from jobicy_scraper import clean_html, is_eligible_for_ireland
from linkedin_scraper import LinkedInJobScraper

logger = logging.getLogger(__name__)

_WORK_ARRANGEMENT_RE = re.compile(
    r"\b(hybrid(?:\s+(?:role|work|working|schedule|model))?|"
    r"\d+\s+days?\s+(?:per\s+week\s+)?in\s+(?:the\s+)?office|"
    r"office attendance required|on[- ]site|onsite)\b",
    re.IGNORECASE,
)

# Working Nomads uses timezone labels such as "Time zone: CET (+/- 3 hours)"
# for EMEA-compatible remote roles (Ireland is UTC+0/+1).
_EMEA_TIMEZONE_RE = re.compile(
    r"\b(?:cet|cest|wet|west|eet|gmt|utc)\b",
    re.IGNORECASE,
)


def is_working_nomads_location_eligible(location: str, description: str = "") -> bool:
    """Return True when a Working Nomads listing accepts candidates in Ireland."""
    if is_eligible_for_ireland(location, description):
        return True

    loc = (location or "").strip()
    if not loc or LinkedInJobScraper.is_location_blocked(loc):
        return False

    if _EMEA_TIMEZONE_RE.search(loc):
        if re.search(
            r"\b(?:excluding|except|outside)\s+(?:the\s+)?(?:republic\s+of\s+)?ireland\b",
            f"{loc} {description}",
            re.IGNORECASE,
        ):
            return False
        return not LinkedInJobScraper.is_description_blocked(description)

    return False


class WorkingNomadsJobScraper:
    """Fetch public remote job listings from Working Nomads."""

    API_URL = "https://www.workingnomads.com/api/exposed_jobs/"
    USER_AGENT = (
        "QA-SDET-Job-Tracker/1.0 "
        "(+https://github.com/pegasovich/job-tracker; personal job search)"
    )

    def _fetch(self) -> List[Dict[str, Any]]:
        request = urllib.request.Request(
            self.API_URL,
            headers={"Accept": "application/json", "User-Agent": self.USER_AGENT},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                import json

                payload = json.loads(response.read().decode("utf-8", errors="replace"))
            return payload if isinstance(payload, list) else []
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            logger.error("Working Nomads API request failed: %s", exc)
            return []

    @classmethod
    def parse_jobs(cls, raw_jobs: List[Dict[str, Any]], limit: int = 50) -> List[Dict[str, Any]]:
        if limit <= 0 or not isinstance(raw_jobs, list):
            return []

        found: Dict[str, Dict[str, Any]] = {}
        for raw in raw_jobs:
            if not isinstance(raw, dict):
                continue
            title = str(raw.get("title") or "").strip()
            url = str(raw.get("url") or "").strip()
            if not title or not url or not LinkedInJobScraper.is_qa_title(title):
                continue

            description = clean_html(str(raw.get("description") or ""))
            location = str(raw.get("location") or "").strip()
            tags = str(raw.get("tags") or "").strip()

            if not is_working_nomads_location_eligible(location, description):
                continue
            if config.has_non_allowed_language_requirement(f"{title} {description} {tags}"):
                continue
            if _WORK_ARRANGEMENT_RE.search(location) or _WORK_ARRANGEMENT_RE.search(description):
                continue

            id_match = re.search(r"/job/(?:go/)?([^/?#]+)", url)
            raw_id = id_match.group(1) if id_match else hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
            if raw_id in found:
                continue

            combined = f"{title} {description} {tags}"
            if re.search(r"\bB2B\b|business[- ]to[- ]business|independent contractor", combined, re.I):
                employment_type = "Contract / B2B stated"
            elif re.search(r"\b(?:contract|freelance|contractor)\b", combined, re.I):
                employment_type = "Contract / Freelance; B2B not stated"
            else:
                employment_type = "Remote listing; B2B not stated"

            found[raw_id] = {
                "id": f"workingnomads_{raw_id}",
                "title": title,
                "company": str(raw.get("company_name") or "Unknown Company").strip(),
                "location": f"Remote ({location})" if "remote" not in location.lower() else location,
                "url": url,
                "posted_date": str(raw.get("pub_date") or "")[:10],
                "description": description,
                "employment_type": employment_type,
                "source": "Working Nomads",
                "workplace_type": "remote",
            }
            if len(found) >= limit:
                break

        return list(found.values())

    def search_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.parse_jobs(self._fetch(), limit=limit)
