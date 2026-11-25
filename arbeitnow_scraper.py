"""
Arbeitnow API Scraper for European and Remote QA / SDET positions.
Free public REST API providing structured job postings across Europe.
"""

import urllib.request
import urllib.parse
import json
import re
import html
import datetime
import random
import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]

# Common non-English words that indicate the job posting is not in English
# Covers German, French, Spanish, Italian, Dutch, Portuguese, Polish, Czech
NON_ENGLISH_MARKER_WORDS = re.compile(
    r'\b(?:'
    # German
    r'für|und|oder|mit|bei|als|wir|suchen|ihre?|dein[e]?|unser[e]?|aufgaben|anforderungen'
    r'|stellenangebot|qualitätsmanager|entwickler|berufserfahrung|mindestens|arbeiten'
    r'|erfahrung|kenntnisse|verantwortlich|bewerbung|sofort|festanstellung|homeoffice'
    # French
    r'|nous|vous|avec|pour|dans|notre|votre|poste|expérience|recherchons|missions'
    r'|compétences|responsable|développeur|ingénieur'
    # Spanish
    r'|para|como|nuestro|nuestra|experiencia|conocimientos|responsabilidades|buscamos'
    r'|empresa|puesto|requisitos|habilidades'
    # Polish
    r'|praca|doświadczenie|wymagania|obowiązki|stanowisko|szukamy|oferujemy|umiejętności'
    r')\b',
    re.IGNORECASE,
)

# Minimum number of non-English markers to classify text as non-English
NON_ENGLISH_MARKER_THRESHOLD = 3


def is_non_english_text(title: str, description: str = "") -> bool:
    """Detect if job title + description snippet is NOT in English using common marker words.

    Returns True if the text contains enough non-English marker words to be
    confidently classified as a non-English posting.
    """
    combined = f"{title} {description[:500]}"
    matches = NON_ENGLISH_MARKER_WORDS.findall(combined)
    return len(matches) >= NON_ENGLISH_MARKER_THRESHOLD


class ArbeitnowJobScraper:
    BASE_URL = "https://www.arbeitnow.com/api/job-board-api"

    def __init__(self):
        pass

    def _fetch_page(self, page: int = 1) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE_URL}?page={page}"
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
                logger.warning(f"Unexpected status {resp.status} for Arbeitnow page {page}")
        except Exception as e:
            logger.error(f"Error querying Arbeitnow API (page {page}): {e}")
        return None

    def search_jobs(
        self,
        remote_only: bool = True,
        max_pages: int = 2,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        jobs = []
        seen_slugs = set()

        for page in range(1, max_pages + 1):
            data = self._fetch_page(page=page)
            if not data:
                break

            items = data.get("data", [])
            if not items:
                break

            for item in items:
                slug = item.get("slug")
                if not slug or slug in seen_slugs:
                    continue
                seen_slugs.add(slug)

                parsed_job = self._parse_single_item(item, remote_only=remote_only)
                if parsed_job:
                    jobs.append(parsed_job)

                if len(jobs) >= limit:
                    break

            if len(jobs) >= limit:
                break

        return jobs

    def _parse_single_item(self, item: Dict[str, Any], remote_only: bool = True) -> Optional[Dict[str, Any]]:
        slug = item.get("slug", "")
        title = (item.get("title") or "").strip()
        company = (item.get("company_name") or "Unknown Company").strip()
        raw_loc = (item.get("location") or "").strip()
        is_remote = item.get("remote") is True or "remote" in raw_loc.lower() or "homeoffice" in raw_loc.lower()

        if remote_only and not is_remote:
            return None

        # Geographical location filter (reject US, Latam, APAC, etc. for remote candidate in Ireland)
        from linkedin_scraper import LinkedInJobScraper
        if remote_only and LinkedInJobScraper.is_location_blocked(raw_loc):
            return None

        # Reject remote roles restricted to a list of specific foreign countries
        # without Ireland or a broad scope (Europe, EU, Worldwide …).
        # E.g. "Austria, Germany, Spain, Italy, Hungary, Portugal, Croatia" lists
        # eligible countries explicitly and Ireland is not among them.
        # A single city/country (e.g. "Berlin") is NOT blocked — it is likely just
        # the company HQ, not a country-restriction list.
        if remote_only and is_remote and raw_loc:
            loc_parts = [p.strip() for p in re.split(r'[,;/–—-]+', raw_loc) if p.strip()]
            # Strip filler tokens that are not country names
            geo_parts = [
                p for p in loc_parts
                if p.lower() not in ("remote", "homeoffice", "home office", "hybrid")
            ]
            if len(geo_parts) >= 2 and not LinkedInJobScraper.has_eligible_remote_scope(raw_loc):
                logger.debug(
                    f"Skipping Arbeitnow job without Ireland-eligible scope: "
                    f"'{title}' @ {company} [{raw_loc}]"
                )
                return None

        # Description cleaning (needed early for language detection)
        raw_desc = item.get("description", "")
        clean_desc = html.unescape(re.sub(r"<[^>]+>", " ", raw_desc))
        clean_desc = re.sub(r"\s+", " ", clean_desc).strip()

        # Reject jobs with domestic US/foreign regional restrictions in description
        if remote_only and LinkedInJobScraper.is_description_blocked(clean_desc):
            return None

        # Non-English language detection: skip postings written in German, French, etc.
        if is_non_english_text(title, clean_desc):
            logger.debug(f"Skipping Arbeitnow non-English posting: '{title}' @ {company}")
            return None

        workplace_type = "remote" if is_remote else "onsite"
        location_label = f"Remote ({raw_loc})" if is_remote and raw_loc else ("Remote" if is_remote else raw_loc)

        # Date formatting
        ts = item.get("created_at")
        posted_date = ""
        if ts and isinstance(ts, (int, float)):
            try:
                posted_date = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d")
            except Exception:
                pass

        # Tags and snippet
        tags = item.get("tags") or []
        snippet_parts = []
        if tags:
            snippet_parts.append(f"Теги: {', '.join(tags[:6])}")
        if clean_desc:
            snippet_parts.append(clean_desc[:250])
        description = " | ".join(snippet_parts) if snippet_parts else "Arbeitnow job posting"

        # Check for salary mentions in description or title
        salary = ""
        sal_m = re.search(r'([€$£][\d,\s–-]+\b|\b\d+k\b)', title + " " + clean_desc[:300])
        if sal_m:
            salary = sal_m.group(1).strip()

        return {
            "id": f"arbeitnow_{slug}",
            "title": title,
            "company": company,
            "location": location_label,
            "url": item.get("url") or f"https://www.arbeitnow.com/jobs/companies/{slug}",
            "posted_date": posted_date,
            "description": description,
            "salary": salary,
            "source": "Arbeitnow",
            "workplace_type": workplace_type,
        }
