"""Remote OK public JSON feed integration."""

import html
import json
import logging
import re
import urllib.parse
import urllib.error
import urllib.request
from typing import Any, Dict, List

from jobicy_scraper import is_eligible_for_ireland
from linkedin_scraper import LinkedInJobScraper

logger = logging.getLogger(__name__)


class RemoteOKJobScraper:
    API_URL = "https://remoteok.com/api"

    def search_jobs(self, tags: List[str], limit: int = 50) -> List[Dict[str, Any]]:
        query = urllib.parse.urlencode({"tags": ",".join(tags)})
        request = urllib.request.Request(
            f"{self.API_URL}?{query}",
            headers={
                "Accept": "application/json",
                "User-Agent": "QA-SDET-Job-Tracker/1.0 (https://remoteok.com/)",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            logger.error("Remote OK API request failed: %s", exc)
            return []

        if not isinstance(payload, list):
            logger.warning("Remote OK API returned an unexpected response")
            return []

        found: Dict[str, Dict[str, Any]] = {}
        for raw in payload:
            if not isinstance(raw, dict):
                continue  # The feed's first item may be an API notice, not a job.
            title = str(raw.get("position") or "").strip()
            description_html = str(raw.get("description") or "")
            description = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", description_html))).strip()
            location = str(raw.get("location") or "").strip()
            if not title or not LinkedInJobScraper.is_qa_title(title):
                continue
            if not is_eligible_for_ireland(location, description):
                continue

            # Reject explicit office attendance or hybrid requirements even on a remote board.
            work_arrangement = re.compile(
                r"\b(hybrid(?:\s+(?:role|work|working|schedule|model))?|"
                r"\d+\s+days?\s+(?:per\s+week\s+)?in\s+(?:the\s+)?office|"
                r"office attendance required|on[- ]site|onsite)\b",
                re.IGNORECASE,
            )
            if work_arrangement.search(location) or work_arrangement.search(description):
                continue

            job_id = str(raw.get("id") or raw.get("slug") or "").strip()
            url = str(raw.get("url") or raw.get("apply_url") or "").strip()
            if not job_id or not url:
                continue
            tags_value = raw.get("tags") or []
            if isinstance(tags_value, str):
                tags_value = [tags_value]
            employment_type = str(raw.get("type") or "").strip()
            if not employment_type:
                type_tags = [str(tag) for tag in tags_value if re.search(r"contract|freelance|full.?time|part.?time", str(tag), re.I)]
                employment_type = ", ".join(type_tags)
            if re.search(r"\bB2B\b|business[- ]to[- ]business|independent contractor", description, re.I):
                employment_type = f"{employment_type}; B2B stated" if employment_type else "B2B stated"
            elif employment_type:
                employment_type += "; B2B not stated"
            else:
                employment_type = "Not specified; B2B not stated"

            found[job_id] = {
                "id": f"remoteok_{job_id}",
                "title": title,
                "company": str(raw.get("company") or "Unknown Company").strip(),
                "location": f"Remote ({location})",
                "url": url,
                "posted_date": str(raw.get("date") or "")[:10],
                "description": description,
                "salary": str(raw.get("salary") or "").strip(),
                "employment_type": employment_type,
                "source": "Remote OK",
                "workplace_type": "remote",
            }
            if len(found) >= limit:
                break
        return list(found.values())
