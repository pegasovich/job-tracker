"""Minimal scraper for WorkRemotely.eu's Ireland contractor results."""

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


class _JobListParser(HTMLParser):
    """Read only job-card titles, company/scope spans, and links."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items: List[Dict[str, Any]] = []
        self.item: Optional[Dict[str, Any]] = None
        self.link_depth = 0
        self.span_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "li" and self.item is None:
            self.item = {"href": "", "title": [], "spans": [], "text": []}
        if self.item is None:
            return
        if tag == "a" and not self.item["href"]:
            href = attrs.get("href", "")
            path = urllib.parse.urlparse(href).path
            if path.startswith("/jobs/") and not path.startswith("/go/"):
                self.item["href"] = href
                self.link_depth = 1
        elif tag == "a" and self.link_depth:
            self.link_depth += 1
        if tag == "span":
            if self.span_depth == 0:
                self.item["spans"].append([])
            self.span_depth += 1

    def handle_endtag(self, tag):
        if self.item is None:
            return
        if tag == "a" and self.link_depth:
            self.link_depth -= 1
        if tag == "span" and self.span_depth:
            self.span_depth -= 1
        if tag == "li":
            if self.item["href"]:
                self.items.append(self.item)
            self.item = None
            self.link_depth = 0
            self.span_depth = 0

    def handle_data(self, data):
        if self.item is None or not data.strip():
            return
        value = " ".join(data.split())
        self.item["text"].append(value)
        if self.link_depth:
            self.item["title"].append(value)
        if self.span_depth:
            self.item["spans"][-1].append(value)

    def close(self):
        super().close()
        if self.item and self.item["href"]:
            self.items.append(self.item)
        self.item = None


class WorkRemotelyEUScraper:
    """Fetch the public Ireland/freelance page no more than hourly in the runner."""

    RESULTS_URL = "https://workremotely.eu/remote-jobs/ireland/freelance"
    BASE_URL = "https://workremotely.eu"
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
            logger.error("WorkRemotely.eu listing request failed: %s", exc)
            return ""

    def search_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.parse_jobs(self._fetch(), limit=limit)

    @classmethod
    def parse_jobs(cls, html: str, limit: int = 50) -> List[Dict[str, Any]]:
        if limit <= 0:
            return []
        parser = _JobListParser()
        try:
            parser.feed(html or "")
            parser.close()
        except (ValueError, AssertionError) as exc:
            logger.warning("Could not parse WorkRemotely.eu listing: %s", exc)
            return []

        found: Dict[str, Dict[str, Any]] = {}
        for item in parser.items:
            title = " ".join(item["title"]).strip()
            if not title or not LinkedInJobScraper.is_qa_title(title):
                continue
            card_text = " ".join(item["text"])
            if re.search(r"\bhybrid\b|\b(?:on[- ]site|onsite)\b", card_text, re.IGNORECASE):
                continue

            spans = [" ".join(span).strip() for span in item["spans"]]
            spans = [span for span in spans if span]
            company = spans[0] if spans else "Unknown Company"
            scope = next(
                (
                    value
                    for index, value in enumerate(spans)
                    if (index > 0 or re.fullmatch(
                        r"(?:remote\s+)?(?:ireland|europe|european union|eu|emea|worldwide|anywhere|global)",
                        value,
                        re.IGNORECASE,
                    ))
                    and is_eligible_for_ireland(value)
                ),
                "",
            )
            # The Ireland/freelance page is a discovery route, not proof that an
            # individual listing permits Irish residents. Require a visible scope.
            if not scope:
                continue

            href = item["href"]
            parsed_href = urllib.parse.urlparse(href)
            if parsed_href.netloc and parsed_href.hostname not in {"workremotely.eu", "www.workremotely.eu"}:
                continue
            url = urllib.parse.urljoin(cls.BASE_URL, href)
            slug = urllib.parse.urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
            if not slug or slug in found:
                continue

            found[slug] = {
                "id": f"workremotely_eu_{slug}",
                "title": title,
                "company": company,
                "location": f"Remote (Ireland eligible; {scope})",
                "url": url,
                "posted_date": "",
                # Store a short source note, not a copied job description.
                "description": (
                    "Listed in WorkRemotely.eu's Ireland contractor/freelance results; "
                    "open the listing for requirements."
                ),
                "employment_type": "Freelance/contractor listing; B2B not stated",
                "source": "WorkRemotely.eu",
                "workplace_type": "remote",
            }
            if len(found) >= limit:
                break
        return list(found.values())
