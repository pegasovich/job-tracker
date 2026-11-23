"""Minimal parser for remote QA listings on the Irish TechJobs.ie board."""

import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional

from jobicy_scraper import is_eligible_for_ireland
from linkedin_scraper import LinkedInJobScraper

logger = logging.getLogger(__name__)


class _ListingParser(HTMLParser):
    """Collect visible text from each QA listing until the next listing link."""

    JOB_PATH = re.compile(r"^/jobs/qa-testing/[^/?#]+/?$")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items: List[Dict[str, Any]] = []
        self.item: Optional[Dict[str, Any]] = None
        self.in_title = False

    def _finish(self):
        if self.item and self.item["title"]:
            self.items.append(self.item)
        self.item = None
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            path = urllib.parse.urlparse(attrs.get("href", "")).path
            if self.JOB_PATH.match(path):
                self._finish()
                self.item = {"href": attrs["href"], "title": [], "text": []}
                self.in_title = True
        if tag == "time" and self.item and not self.item.get("posted_date"):
            self.item["posted_date"] = attrs.get("datetime", "")

    def handle_endtag(self, tag):
        if tag == "a" and self.in_title:
            self.in_title = False

    def handle_data(self, data):
        if self.item is None or not data.strip():
            return
        value = " ".join(data.split())
        self.item["text"].append(value)
        if self.in_title:
            self.item["title"].append(value)

    def close(self):
        super().close()
        self._finish()


class TechJobsIEScraper:
    RESULTS_URL = "https://www.techjobs.ie/jobs/qa-engineer-jobs-ireland"
    BASE_URL = "https://www.techjobs.ie"
    USER_AGENT = (
        "QA-SDET-Job-Tracker/1.0 "
        "(+https://github.com/pegasovich/job-tracker; personal job search)"
    )

    def _fetch(self) -> str:
        request = urllib.request.Request(
            self.RESULTS_URL,
            headers={"User-Agent": self.USER_AGENT, "Accept": "text/html"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.error("TechJobs.ie listing request failed: %s", exc)
            return ""

    def search_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.parse_jobs(self._fetch(), limit=limit)

    @classmethod
    def parse_jobs(cls, html: str, limit: int = 50) -> List[Dict[str, Any]]:
        if limit <= 0:
            return []
        parser = _ListingParser()
        try:
            parser.feed(html or "")
            parser.close()
        except (ValueError, AssertionError) as exc:
            logger.warning("Could not parse TechJobs.ie listing: %s", exc)
            return []

        found: Dict[str, Dict[str, Any]] = {}
        for item in parser.items:
            title = " ".join(item["title"]).strip()
            card_text = " ".join(item["text"])
            if not title or not LinkedInJobScraper.is_qa_title(title):
                continue
            if not re.search(r"\bremote\b", card_text, re.IGNORECASE):
                continue
            if re.search(
                r"\bhybrid\b|\b(?:on[- ]site|onsite)\b|"
                r"\d+\s+days?\s+(?:per\s+week\s+)?in\s+(?:the\s+)?office|"
                r"office attendance required",
                card_text,
                re.IGNORECASE,
            ):
                continue
            # Tie eligibility to a nearby remote label. A site footer or the next
            # card must not make an otherwise country-restricted listing eligible.
            remote_contexts = []
            for remote_match in re.finditer(r"\bremote\b", card_text, re.IGNORECASE):
                start = max(0, remote_match.start() - 180)
                end = min(len(card_text), remote_match.end() + 180)
                remote_contexts.append(card_text[start:end])
            location_match = re.compile(
                r"(?:[A-Z][A-Za-z'’.-]*(?:\s+[A-Z][A-Za-z'’.-]*){0,2},\s*)?"
                r"(?:Ireland|Europe|European Union|EU|EMEA|Worldwide|Anywhere|Global)"
                r"[^.]{0,45}\bremote\b[^.]{0,30}|"
                r"\bremote\b[^.]{0,30}"
                r"(?:Ireland|Europe|European Union|EU|EMEA|Worldwide|Anywhere|Global)",
                re.IGNORECASE,
            )
            eligible_location_context = next(
                (
                    context
                    for context in remote_contexts
                    if is_eligible_for_ireland(context) and location_match.search(context)
                ),
                "",
            )
            if not eligible_location_context:
                continue

            href = item["href"]
            parsed_href = urllib.parse.urlparse(href)
            if parsed_href.netloc and parsed_href.hostname not in {"techjobs.ie", "www.techjobs.ie"}:
                continue
            url = urllib.parse.urljoin(cls.BASE_URL, href)
            slug = urllib.parse.urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
            if not slug or slug in found:
                continue

            # Only short visible metadata is retained; requirements stay on the source page.
            tail = card_text[len(title):]
            company_match = re.search(r"([^·|]{2,80})\s*[·|]\s*(?:Recruitment agency|Direct employer)", tail, re.I)
            company = company_match.group(1).strip(" ·|-") if company_match else "Unknown Company"
            employment_type = "Contract; B2B not stated" if re.search(r"\bcontract\b", card_text, re.I) else "Not specified; B2B not stated"

            found[slug] = {
                "id": f"techjobs_ie_{slug}",
                "title": title,
                "company": company or "Unknown Company",
                "location": "Remote (Ireland eligible; TechJobs.ie)",
                "url": url,
                "posted_date": str(item.get("posted_date") or "")[:10],
                "description": "Remote QA listing on TechJobs.ie; open the listing for requirements.",
                "employment_type": employment_type,
                "source": "TechJobs.ie",
                "workplace_type": "remote",
            }
            if len(found) >= limit:
                break
        return list(found.values())
