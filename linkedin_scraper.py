"""
LinkedIn Public Job Scraper for Ireland (Remote)
Uses LinkedIn Guest API (no login, no cookies, no risk of ban).
"""

import urllib.request
import urllib.parse
import urllib.error
import re
import html
import time
import random
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
]


def get_random_headers(referer: Optional[str] = None) -> dict:
    ua = random.choice(USER_AGENTS)
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }
    if "Windows" in ua:
        headers["Sec-Ch-Ua-Platform"] = '"Windows"'
    elif "Macintosh" in ua:
        headers["Sec-Ch-Ua-Platform"] = '"macOS"'
    if referer:
        headers["Referer"] = referer
    return headers


class LinkedInJobScraper:
    BASE_SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    BASE_DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{}"

    def __init__(self, location: str = "Ireland", remote_only: bool = True):
        self.location = location
        self.remote_only = remote_only
        self.last_hit_rate_limit = False

    def _make_request(self, url: str, max_retries: int = 3, referer: Optional[str] = None) -> Optional[str]:
        if not referer:
            referer = "https://www.linkedin.com/jobs/search"

        for attempt in range(max_retries + 1):
            headers = get_random_headers(referer=referer)
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if resp.status == 200:
                        return resp.read().decode("utf-8", errors="ignore")
                    logger.warning(f"Неожиданный статус ответа {resp.status} для {url}")
                    return None
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    self.last_hit_rate_limit = True
                    if attempt < max_retries:
                        retry_after = e.headers.get("Retry-After") if e.headers else None
                        # Прогрессивное ожидание: ~35с на 1-й попытке, ~65с на 2-й, ~95с на 3-й
                        wait_seconds = 35 * (attempt + 1) + random.uniform(2.0, 6.0)
                        if retry_after and retry_after.isdigit():
                            wait_seconds = max(wait_seconds, int(retry_after) + 3)
                        logger.warning(
                            f"⏳ LinkedIn Rate Limit (429 Too Many Requests) для {url}. "
                            f"Пауза {int(wait_seconds)} сек перед повтором (попытка {attempt + 1}/{max_retries})..."
                        )
                        time.sleep(wait_seconds)
                        continue
                    else:
                        logger.warning(
                            f"⚠️ LinkedIn временно ограничил частоту запросов (429). "
                            f"Запрос пропущен, он будет повторен при следующем запуске: {url}"
                        )
                else:
                    logger.error(f"HTTP ошибка {e.code} при запросе {url}: {e.reason}")
                return None
            except Exception as e:
                logger.error(f"Ошибка запроса {url}: {e}")
                return None
        return None

    def search_jobs(self, keyword: str, limit: int = 25) -> List[Dict[str, str]]:
        """
        Search jobs by keyword.
        f_WT=2 sets filter to Remote.
        f_TPR=r86400 (past 24h) or r604800 (past week) can also be used if needed.
        """
        params = {
            "keywords": keyword,
            "location": self.location,
            "start": 0,
        }
        if self.remote_only:
            params["f_WT"] = "2"  # 2 = Remote in LinkedIn filter

        url = f"{self.BASE_SEARCH_URL}?{urllib.parse.urlencode(params)}"
        search_referer = f"https://www.linkedin.com/jobs/search?{urllib.parse.urlencode({'keywords': keyword, 'location': self.location})}"
        html_content = self._make_request(url, referer=search_referer)
        if not html_content:
            return []

        jobs = []
        # Each job is enclosed in an <li> with a base-card
        card_blocks = re.findall(
            r'(<div class="base-card[^"]*".*?data-entity-urn="urn:li:jobPosting:(\d+)".*?</li>)',
            html_content,
            re.DOTALL,
        )

        for block_html, job_id in card_blocks:
            # Title
            title_m = re.search(r'<h3 class="base-search-card__title">\s*([^<]+?)\s*</h3>', block_html)
            title = html.unescape(title_m.group(1).strip()) if title_m else "Unknown Title"

            # Company
            company_m = re.search(r'<h4 class="base-search-card__subtitle">.*?<a[^>]*>\s*([^<]+?)\s*</a>', block_html, re.DOTALL)
            if not company_m:
                company_m = re.search(r'<h4 class="base-search-card__subtitle">\s*([^<]+?)\s*</h4>', block_html)
            company = html.unescape(company_m.group(1).strip()) if company_m else "Unknown Company"

            # Location
            loc_m = re.search(r'<span class="job-search-card__location">\s*([^<]+?)\s*</span>', block_html)
            job_loc = html.unescape(loc_m.group(1).strip()) if loc_m else self.location

            # Post date / relative time
            date_m = re.search(r'<time class="job-search-card__listdate[^"]*"\s+datetime="([^"]+)"', block_html)
            posted_date = date_m.group(1) if date_m else ""

            # Link
            link_m = re.search(r'<a class="base-card__full-link[^"]*"\s+href="([^"?]+)', block_html)
            link = link_m.group(1) if link_m else f"https://www.linkedin.com/jobs/view/{job_id}"

            jobs.append({
                "id": job_id,
                "title": title,
                "company": company,
                "location": job_loc,
                "posted_date": posted_date,
                "url": link,
                "keyword": keyword,
            })

            if len(jobs) >= limit:
                break

        return jobs

    def get_job_description(self, job_id: str) -> str:
        """Fetch full job description text."""
        url = self.BASE_DETAIL_URL.format(job_id)
        job_referer = f"https://www.linkedin.com/jobs/view/{job_id}"
        html_content = self._make_request(url, referer=job_referer)
        if not html_content:
            return ""

        desc_m = re.search(r'<div class="show-more-less-html__markup[^"]*">(.*?)</div>', html_content, re.DOTALL)
        if not desc_m:
            return ""

        raw_desc = desc_m.group(1)
        text = re.sub(r'<[^>]+>', ' ', raw_desc)
        text = html.unescape(text)
        return " ".join(text.split())

    def get_job_description_snippet(self, job_id: str, max_chars: int = 350) -> str:
        """Fetch job detail and return brief description snippet."""
        full_desc = self.get_job_description(job_id)
        if len(full_desc) > max_chars:
            return full_desc[:max_chars].rstrip() + "..."
        return full_desc

    def detect_workplace_type(self, title: str, location: str, description: str) -> str:
        t = title.lower()
        loc = location.lower()
        d = description.lower()

        # 1. Domestic Remote Restrictions (must be checked early!)
        # E.g. "nur innerhalb Ungarns", "only within Germany", "must reside in Poland"
        domestic_restrictions = [
            r'nur\s+innerhalb\s+(?!irland|europa|eu\b)',
            r'only\s+(?:available\s+)?(?:within|in)\s+(?!ireland|europe|eu\b|uk\b|the\s+eu\b|the\s+uk\b)[a-z]+',
            r'must\s+be\s+(?:located|based|resident|living)\s+in\s+(?!ireland|europe|eu\b|uk\b|the\s+eu\b|the\s+uk\b)[a-z]+',
            r'residents?\s+of\s+(?!ireland|europe|eu\b|uk\b|the\s+eu\b|the\s+uk\b)[a-z]+\s+only',
            r'tax\s+residen(?:cy|t)\s+in\s+(?!ireland|europe|eu\b|uk\b)[a-z]+',
            r'remote\s+(?:work\s+)?is\s+only\s+(?:possible|permitted|allowed)\s+(?:within|in)',
        ]
        for pattern in domestic_restrictions:
            if re.search(pattern, d):
                return "onsite"  # Restricted to another country -> effectively onsite/unusable for Ireland

        # 2. Explicit On-site markers (multi-language)
        onsite_markers = [
            "on-site", "on site", "onsite",
            "office-based", "office based",
            "in-office", "in office",
            "work from the office", "working from the office", "work from office",
            "based in our office", "based at our office", "based in the office",
            "relocation required", "must relocate", "relocation package",
            # German
            "vor ort", "im büro", "präsenzpflicht", "an unserem standort",
            # Hungarian
            "irodai munkavégzés", "személyes jelenlét", "helyszíni munkavégzés",
        ]
        has_onsite_marker = any(m in d for m in onsite_markers) or any(m in t for m in ["on-site", "onsite", "on site"])

        # 3. Hybrid check
        hybrid_markers = [
            "hybrid", "days in office", "days a week in office",
            "days per week from", "days per week in", "days per week office",
            "days/week in office", "days on-site", "days onsite",
            "partial remote", "mix of remote and office",
            # German
            "hybrides arbeiten", "hybrid-modell", "tage im büro",
            # Hungarian
            "hibrid",
        ]
        if any(h in d for h in hybrid_markers) or "hybrid" in t:
            return "hybrid"

        # 4. Explicit International Remote Work (highest confidence for candidates in Ireland)
        international_remote = [
            "anywhere in europe", "anywhere in the eu", "anywhere in eu",
            "work from anywhere", "remote across europe", "remote in europe",
            "pan-european", "b2b contractor", "b2b contract", "contractor role",
            "worldwide remote", "fully remote worldwide", "fully remote europe",
            "remote throughout europe", "remote - europe", "remote (europe)",
            "anywhere in ireland", "remote in ireland", "fully remote ireland",
        ]
        if any(r in d for r in international_remote):
            if has_onsite_marker:
                return "onsite"
            return "remote"

        # 5. High-confidence explicit remote phrases
        explicit_remote = [
            "fully remote", "100% remote", "completely remote",
            "work from home", "work from anywhere", "wfh",
            "home-based", "home based",
            "virtual role", "virtual position",
            "remote-first", "remote first",
            "remote work", "remote position", "remote role",
            "remote opportunity", "remote job",
            "working remotely", "work remotely",
            "this is a remote", "this role is remote",
            "location: remote", "location remote",
        ]
        has_explicit_remote = any(r in d for r in explicit_remote) or "remote" in t

        # 6. Clean false positives for standalone "remote"
        false_positive_patterns = [
            "remote access", "remote monitoring", "remote support",
            "remote desktop", "remote connection", "remote server",
            "remote infrastructure", "remote troubleshoot",
            "remote diagnos", "remote debug", "remote control",
            "remote execution", "remote management",
            "remote locations", "remote areas", "remote sites",
            "remote teams", "remote team", "remote colleagues",
            "remote interview", "remote onboarding", "interviews remotely",
            "not a remote", "no remote", "not remote",
            "remote device", "remote testing",
        ]
        d_clean = d
        for fp in false_positive_patterns:
            d_clean = d_clean.replace(fp, "")

        has_general_remote = "remote" in d_clean

        # 7. Decision logic considering location
        is_foreign_specific_city = bool(loc and not any(k in loc for k in ["ireland", "remote", "worldwide", "united kingdom", "uk"]))

        if has_onsite_marker:
            return "onsite"

        if has_explicit_remote:
            # If location is a specific foreign city (e.g. Budapest, Hungary) and NOT Ireland,
            # but says "fully remote", it might be domestic remote within that country
            # unless it explicitly says Europe / Worldwide.
            if is_foreign_specific_city:
                if any(k in d for k in ["europe", "worldwide", "b2b", "contract"]):
                    return "remote"
                # Otherwise foreign city + remote usually means domestic remote within that country
                return "onsite"
            return "remote"

        if has_general_remote:
            if is_foreign_specific_city:
                # Standalone "remote" for a foreign city is almost always onsite/domestic
                return "onsite"
            return "remote"

        if is_foreign_specific_city:
            return "onsite"

        if loc == "ireland":
            return "remote"

        return "unclear"
