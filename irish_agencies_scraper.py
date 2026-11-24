"""Irish IT recruitment agency scrapers (Reperio, RealTime, Archer).

Focuses on daily-rate contracts and remote/nearby-hybrid QA/SDET roles in Ireland.
Onsite roles and hybrid roles outside Co. Kerry are rejected downstream/here via
LinkedInJobScraper.detect_workplace_type.
"""

from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from database import compute_job_fingerprint
from jobicy_scraper import clean_html
from linkedin_scraper import LinkedInJobScraper

logger = logging.getLogger(__name__)

_DEFAULT_USER_AGENT = (
    "QA-SDET-Job-Tracker/1.0 "
    "(+https://github.com/pegasovich/job-tracker; personal job search)"
)
_IRISH_CITY_RE = re.compile(
    r"\b(?:dublin|cork|galway|limerick|waterford|kilkenny|athlone|sligo|tralee|killarney|kerry)\b",
    re.IGNORECASE,
)


def _http_get(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": _DEFAULT_USER_AGENT, "Accept": "text/html,application/xml,*/*"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.error("HTTP GET failed for %s: %s", url, exc)
        return ""


def _http_post_form(url: str, data: Dict[str, Any], timeout: int = 20) -> str:
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=encoded,
        headers={
            "User-Agent": _DEFAULT_USER_AGENT,
            "Accept": "application/json, text/javascript, */*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.error("HTTP POST failed for %s: %s", url, exc)
        return ""


def _normalize_irish_location(location: str) -> str:
    """Ensure standalone Irish city names include 'Ireland' for workplace classification."""
    loc = " ".join((location or "").split()).strip(" ,-/")
    if not loc:
        return "Ireland"
    if "ireland" not in loc.lower() and _IRISH_CITY_RE.search(loc):
        return f"{loc}, Ireland"
    return loc


def _format_employment_type(raw_type: str, text: str) -> str:
    combined = f"{raw_type} {text}"
    has_daily_rate = bool(re.search(r"\b(?:daily|day)\s*rate\b|/\s*day\b|\bper\s+day\b", combined, re.I))
    has_b2b = bool(re.search(r"\bB2B\b|business[- ]to[- ]business|limited\s+company|umbrella", combined, re.I))
    has_contract = bool(re.search(r"\b(?:contract|contractor|ftc|fixed[- ]term)\b", combined, re.I))

    parts = [raw_type.strip()] if raw_type and raw_type.strip() else []
    if has_daily_rate and not any("daily" in p.lower() or "day" in p.lower() for p in parts):
        parts.append("Daily Rate")
    elif has_contract and not any("contract" in p.lower() or "ftc" in p.lower() for p in parts):
        parts.append("Contract")
    if has_b2b:
        parts.append("B2B/Ltd")
    return "; ".join(parts) if parts else "Not specified"


def _extract_salary(text: str) -> str:
    match = re.search(
        r"€\s*\d[\d,]*(?:\s*[-–to]+\s*€?\s*\d[\d,]*)?(?:\s*(?:per\s+day|/\s*day|daily|day|k|per\s+annum|p\.?a\.?))?",
        text or "",
        re.IGNORECASE,
    )
    return " ".join(match.group(0).split()) if match else ""


def _classify_agency_workplace(
    classifier: LinkedInJobScraper, title: str, location: str, description: str
) -> str:
    """Classify agency listing workplace; reject onsite and unclear listings."""
    workplace_type = classifier.detect_workplace_type(title, location, description)
    if workplace_type == "unclear":
        # Explicit 'Remote' location without onsite/hybrid markers in description is remote.
        if re.search(r"\bremote\b", location, re.IGNORECASE) and not re.search(
            r"\b(?:hybrid|on[- ]site|onsite)\b", description, re.IGNORECASE
        ):
            return "remote"
    return workplace_type


def _extract_json_ld_job(html_text: str) -> Optional[Dict[str, Any]]:
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text or "",
        re.DOTALL | re.IGNORECASE,
    ):
        try:
            payload = json.loads(match.group(1))
        except ValueError:
            continue
        items = payload.get("@graph", []) if isinstance(payload, dict) and "@graph" in payload else [payload]
        if isinstance(payload, list):
            items = payload
        for item in items:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return item
    return None


class ReperioJobScraper:
    """Scraper for Reperio Human Capital's Irish IT contract/permanent job board."""

    SEARCH_URL = "https://www.reperiohumancapital.com/jobs-search"
    BASE_URL = "https://www.reperiohumancapital.com"

    def _fetch_search(self, keyword: str) -> str:
        return _http_get(f"{self.SEARCH_URL}?{urllib.parse.urlencode({'search': keyword})}")

    def _fetch_detail(self, url: str) -> str:
        return _http_get(url)

    @staticmethod
    def parse_search_cards(html_text: str) -> List[Dict[str, str]]:
        """Extract job URLs, titles, and card snippets from search HTML."""
        cards: List[Dict[str, str]] = []
        seen_paths = set()
        for match in re.finditer(
            r'<article[^>]*class="[^"]*node--type-job[^"]*"[^>]*>(.*?)</article>',
            html_text or "",
            re.DOTALL | re.IGNORECASE,
        ):
            block = match.group(1)
            link_m = re.search(r'href="(/job/(\d+)/[^"#?]+)"', block)
            if not link_m:
                continue
            path, job_id = link_m.group(1), link_m.group(2)
            if path in seen_paths:
                continue
            seen_paths.add(path)

            title_m = re.search(r"<h3[^>]*>.*?<a[^>]*>(.*?)</a>", block, re.DOTALL | re.IGNORECASE)
            title = clean_html(title_m.group(1)) if title_m else ""
            if not title:
                continue

            details_m = re.search(r'<div class="details"[^>]*>(.*?)</div>', block, re.DOTALL | re.IGNORECASE)
            details_text = clean_html(details_m.group(1)) if details_m else ""
            cards.append({"id": job_id, "title": title, "path": path, "details": details_text})
        return cards

    @classmethod
    def parse_detail_json_ld(cls, html_text: str, fallback_title: str = "", url: str = "") -> Optional[Dict[str, Any]]:
        data = _extract_json_ld_job(html_text)
        if not data:
            return None

        title = clean_html(str(data.get("title") or fallback_title))
        description = clean_html(str(data.get("description") or ""))
        if not title:
            return None

        addr = ((data.get("jobLocation") or {}).get("address") or {})
        street = addr.get("streetAddress") or []
        if isinstance(street, str):
            street = [street]
        locality = addr.get("addressLocality") or ""
        country = addr.get("addressCountry") or ""
        loc_parts = [str(p).strip() for p in (*street, locality, country) if p and str(p).strip()]
        raw_loc = ", ".join(dict.fromkeys(loc_parts)) or "Ireland"
        location = _normalize_irish_location(raw_loc)

        salary = ""
        sal_val = (data.get("baseSalary") or {}).get("value") or {}
        curr = str((data.get("baseSalary") or {}).get("currency") or "€")
        min_v, max_v = sal_val.get("minValue"), sal_val.get("maxValue")
        unit = str(sal_val.get("unitText") or "").strip()
        if min_v and max_v:
            salary = f"{curr}{min_v}–{curr}{max_v}" + (f" / {unit}" if unit else "")
        elif min_v or max_v:
            salary = f"{curr}{min_v or max_v}" + (f" / {unit}" if unit else "")

        emp_type = str(data.get("employmentType") or "").strip()
        return {
            "id": f"reperio_{data.get('identifier') or ''}",
            "title": title,
            "company": "Reperio Human Capital",
            "location": location,
            "url": url,
            "posted_date": str(data.get("datePosted") or "")[:10],
            "description": description,
            "salary": salary,
            "employment_type": _format_employment_type(emp_type, f"{title} {salary} {description}"),
            "source": "Reperio",
        }

    def search_jobs(self, keywords: Optional[List[str]] = None, limit: int = 30) -> List[Dict[str, Any]]:
        if limit <= 0:
            return []
        keywords = keywords or ["QA", "Test", "SDET", "Automation"]
        classifier = LinkedInJobScraper(location="Ireland")
        found: Dict[str, Dict[str, Any]] = {}

        for idx, kw in enumerate(keywords):
            if idx:
                time.sleep(0.5)
            cards = self.parse_search_cards(self._fetch_search(kw))
            for card in cards:
                if card["id"] in found or not LinkedInJobScraper.is_qa_title(card["title"]):
                    continue
                url = urllib.parse.urljoin(self.BASE_URL, card["path"])
                time.sleep(0.4)
                parsed = self.parse_detail_json_ld(self._fetch_detail(url), fallback_title=card["title"], url=url)
                if not parsed:
                    continue
                if not parsed["id"] or parsed["id"] == "reperio_":
                    parsed["id"] = f"reperio_{card['id']}"
                workplace = _classify_agency_workplace(classifier, parsed["title"], parsed["location"], parsed["description"])
                if workplace not in ("remote", "hybrid"):
                    continue
                parsed["workplace_type"] = workplace
                found[card["id"]] = parsed
                if len(found) >= limit:
                    return list(found.values())

        return list(found.values())


class _WPJobManagerParser(HTMLParser):
    """Parse WP Job Manager <li class='...job_listing...'> result fragments."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items: List[Dict[str, Any]] = []
        self.current: Optional[Dict[str, Any]] = None
        self.capture_tag: Optional[str] = None
        self.in_location = False
        self.in_job_type = False

    def handle_starttag(self, tag, attrs):
        attr_map = dict(attrs)
        cls = attr_map.get("class", "")
        if tag == "li" and "job_listing" in cls:
            id_m = re.search(r"\bpost-(\d+)\b", cls)
            self.current = {
                "id": id_m.group(1) if id_m else "",
                "url": "",
                "title": [],
                "location": [],
                "job_type": [],
                "posted_date": "",
            }
            return
        if self.current is None:
            return
        if tag == "a" and not self.current["url"]:
            self.current["url"] = attr_map.get("href", "")
        elif tag == "h3":
            self.capture_tag = "title"
        elif tag == "div" and "location" in cls:
            self.in_location = True
        elif tag == "li" and "job-type" in cls:
            self.in_job_type = True
        elif tag == "time" and not self.current["posted_date"]:
            self.current["posted_date"] = attr_map.get("datetime", "")

    def handle_endtag(self, tag):
        if self.current is None:
            return
        if tag == "h3" and self.capture_tag == "title":
            self.capture_tag = None
        elif tag == "div" and self.in_location:
            self.in_location = False
        elif tag == "li" and self.in_job_type:
            self.in_job_type = False
        elif tag == "li" and not self.in_job_type:
            if self.current["url"] and self.current["title"]:
                self.items.append(self.current)
            self.current = None

    def handle_data(self, data):
        if self.current is None or not data.strip():
            return
        text = " ".join(data.split())
        if self.capture_tag == "title":
            self.current["title"].append(text)
        elif self.in_location:
            self.current["location"].append(text)
        elif self.in_job_type:
            self.current["job_type"].append(text)


class RealTimeJobScraper:
    """Scraper for RealTime Recruitment (realtime.jobs) via WP Job Manager AJAX."""

    AJAX_URL = "https://realtime.jobs/jm-ajax/get_listings/"

    def _fetch_listings(self, keyword: str, per_page: int = 25) -> str:
        payload = _http_post_form(
            self.AJAX_URL,
            {"search_keywords": keyword, "per_page": per_page, "page": 1},
        )
        if not payload:
            return ""
        try:
            data = json.loads(payload)
            return str(data.get("html") or "") if isinstance(data, dict) else ""
        except ValueError:
            return ""

    def _fetch_detail(self, url: str) -> str:
        return _http_get(url)

    @classmethod
    def parse_listings_html(cls, html_fragment: str) -> List[Dict[str, str]]:
        parser = _WPJobManagerParser()
        try:
            parser.feed(html_fragment or "")
            parser.close()
        except (ValueError, AssertionError):
            return []

        cards: List[Dict[str, str]] = []
        for item in parser.items:
            url = item["url"].strip()
            slug = urllib.parse.urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
            job_id = item["id"] or slug
            title = " ".join(item["title"]).strip()
            location = _normalize_irish_location(" ".join(item["location"]))
            if not job_id or not title or not url:
                continue
            cards.append({
                "id": job_id,
                "title": title,
                "location": location,
                "job_type": " ".join(item["job_type"]).strip(),
                "posted_date": item["posted_date"][:10],
                "url": url,
            })
        return cards

    @staticmethod
    def extract_detail_description(html_text: str) -> str:
        json_ld = _extract_json_ld_job(html_text)
        if json_ld and json_ld.get("description"):
            return clean_html(str(json_ld["description"]))
        desc_m = re.search(
            r'<div[^>]+class="[^"]*job_description[^"]*"[^>]*>(.*?)</div>',
            html_text or "",
            re.DOTALL | re.IGNORECASE,
        )
        return clean_html(desc_m.group(1)) if desc_m else ""

    def search_jobs(self, keywords: Optional[List[str]] = None, limit: int = 30) -> List[Dict[str, Any]]:
        if limit <= 0:
            return []
        keywords = keywords or ["QA", "Test", "SDET", "Automation"]
        classifier = LinkedInJobScraper(location="Ireland")
        found: Dict[str, Dict[str, Any]] = {}

        for idx, kw in enumerate(keywords):
            if idx:
                time.sleep(0.5)
            cards = self.parse_listings_html(self._fetch_listings(kw))
            for card in cards:
                if card["id"] in found or not LinkedInJobScraper.is_qa_title(card["title"]):
                    continue
                time.sleep(0.4)
                description = self.extract_detail_description(self._fetch_detail(card["url"]))
                workplace = _classify_agency_workplace(classifier, card["title"], card["location"], description)
                if workplace not in ("remote", "hybrid"):
                    continue
                salary = _extract_salary(f"{card['title']} {description}")
                found[card["id"]] = {
                    "id": f"realtime_{card['id']}",
                    "title": card["title"],
                    "company": "RealTime Recruitment",
                    "location": card["location"],
                    "url": card["url"],
                    "posted_date": card["posted_date"],
                    "description": description,
                    "salary": salary,
                    "employment_type": _format_employment_type(card["job_type"], f"{card['title']} {description}"),
                    "source": "RealTime",
                    "workplace_type": workplace,
                }
                if len(found) >= limit:
                    return list(found.values())

        return list(found.values())


class ArcherJobScraper:
    """Scraper for Archer Recruitment (archer.ie) via WP Job Manager RSS feed."""

    FEED_URL = "https://www.archer.ie/?feed=job_feed"

    def _fetch_feed(self, keyword: str) -> str:
        return _http_get(f"{self.FEED_URL}&{urllib.parse.urlencode({'search_keywords': keyword})}")

    @classmethod
    def parse_feed(cls, xml_text: str, limit: int = 30) -> List[Dict[str, Any]]:
        if limit <= 0 or not xml_text or not xml_text.strip():
            return []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.warning("Could not parse Archer RSS XML: %s", exc)
            return []

        classifier = LinkedInJobScraper(location="Ireland")
        found: Dict[str, Dict[str, Any]] = {}
        seen_fingerprints: set[str] = set()

        for item in root.findall(".//item"):
            title = clean_html(item.findtext("title") or "")
            url = (item.findtext("link") or "").strip()
            if not title or not url or not LinkedInJobScraper.is_qa_title(title):
                continue

            slug = urllib.parse.urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
            if not slug or slug in found:
                continue

            raw_location = ""
            raw_job_type = ""
            for child in item:
                tag_name = child.tag.rsplit("}", 1)[-1].lower()
                if tag_name == "location" and child.text:
                    raw_location = child.text.strip()
                elif tag_name == "job_type" and child.text:
                    raw_job_type = child.text.strip()

            location = _normalize_irish_location(raw_location)
            description = clean_html(item.findtext("description") or "")
            workplace = _classify_agency_workplace(classifier, title, location, description)
            if workplace not in ("remote", "hybrid"):
                continue

            posted_date = ""
            pub_raw = (item.findtext("pubDate") or "").strip()
            if pub_raw:
                try:
                    posted_date = parsedate_to_datetime(pub_raw).date().isoformat()
                except (TypeError, ValueError):
                    posted_date = ""

            salary = _extract_salary(f"{title} {description}")
            job_entry = {
                "id": f"archer_{slug}",
                "title": title,
                "company": "Archer Recruitment",
                "location": location,
                "url": url,
                "posted_date": posted_date,
                "description": description,
                "salary": salary,
                "employment_type": _format_employment_type(raw_job_type, f"{title} {description}"),
                "source": "Archer",
                "workplace_type": workplace,
            }
            fingerprint = compute_job_fingerprint(job_entry)
            if fingerprint in seen_fingerprints:
                continue
            seen_fingerprints.add(fingerprint)
            found[slug] = job_entry
            if len(found) >= limit:
                break

        return list(found.values())

    def search_jobs(self, keywords: Optional[List[str]] = None, limit: int = 30) -> List[Dict[str, Any]]:
        if limit <= 0:
            return []
        keywords = keywords or ["QA", "Test", "SDET", "Automation"]
        found: Dict[str, Dict[str, Any]] = {}
        seen_fingerprints: set[str] = set()
        for idx, kw in enumerate(keywords):
            if idx:
                time.sleep(0.5)
            for job in self.parse_feed(self._fetch_feed(kw), limit=limit):
                fingerprint = compute_job_fingerprint(job)
                if job["id"] not in found and fingerprint not in seen_fingerprints:
                    seen_fingerprints.add(fingerprint)
                    found[job["id"]] = job
                    if len(found) >= limit:
                        return list(found.values())
        return list(found.values())
