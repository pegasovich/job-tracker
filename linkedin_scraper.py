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

    def __init__(
        self,
        location: str = "Ireland",
        remote_only: bool = True,
        time_filter: Optional[str] = None,
        sort_by: Optional[str] = None,
    ):
        self.location = location
        self.remote_only = remote_only
        self.time_filter = time_filter
        self.sort_by = sort_by
        self.last_hit_rate_limit = False

    def _make_request(
        self,
        url: str,
        max_retries: Optional[int] = None,
        referer: Optional[str] = None,
    ) -> Optional[str]:
        if not referer:
            referer = "https://www.linkedin.com/jobs/search"

        if max_retries is None:
            max_retries = getattr(config, "LINKEDIN_MAX_RETRIES", 1) if config else 1
        base_wait = getattr(config, "LINKEDIN_RETRY_BASE_WAIT", 10.0) if config else 10.0

        self.last_hit_rate_limit = False
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
                        # Адаптивное быстрое ожидание: ~10-15 сек (вместо затяжных 40-110 сек)
                        wait_seconds = base_wait * (attempt + 1) + random.uniform(1.0, 3.0)
                        if retry_after and retry_after.isdigit():
                            wait_seconds = min(max(wait_seconds, float(retry_after)), 25.0)
                        logger.warning(
                            f"⏳ LinkedIn Rate Limit (429) для {url}. "
                            f"Пауза {int(wait_seconds)} сек перед повтором (попытка {attempt + 1}/{max_retries})..."
                        )
                        time.sleep(wait_seconds)
                        continue
                    else:
                        logger.warning(
                            f"⚠️ LinkedIn ограничил частоту запросов (429). "
                            f"Запрос пропущен (будет повторен в следующем цикле): {url}"
                        )
                else:
                    logger.error(f"HTTP ошибка {e.code} при запросе {url}: {e.reason}")
                return None
            except Exception as e:
                logger.error(f"Ошибка запроса {url}: {e}")
                return None
        return None

    def search_jobs(self, keyword: str, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """
        Search jobs by keyword.
        f_WT=2 sets filter to Remote.
        f_TPR=r86400 (past 24h) or r604800 (past week) sets time range.
        sortBy=DD sets sort to most recent date descending.
        """
        if limit is None:
            limit = getattr(config, "LINKEDIN_SEARCH_LIMIT", 6) if config else 6
        jobs = []
        seen_ids = set()
        start = 0

        while len(jobs) < limit:
            params = {
                "keywords": keyword,
                "location": self.location,
                "start": start,
            }
            if self.remote_only:
                params["f_WT"] = "2"  # 2 = Remote in LinkedIn filter
            if self.time_filter:
                params["f_TPR"] = self.time_filter
            if self.sort_by:
                params["sortBy"] = self.sort_by

            url = f"{self.BASE_SEARCH_URL}?{urllib.parse.urlencode(params)}"
            search_referer = f"https://www.linkedin.com/jobs/search?{urllib.parse.urlencode({'keywords': keyword, 'location': self.location})}"
            html_content = self._make_request(url, referer=search_referer)
            if not html_content:
                break

            # Each job is enclosed in an <li> with a base-card
            card_blocks = re.findall(
                r'(<div class="base-card[^"]*".*?data-entity-urn="urn:li:jobPosting:(\d+)".*?</li>)',
                html_content,
                re.DOTALL,
            )
            if not card_blocks:
                break

            new_on_page = 0
            for block_html, job_id in card_blocks:
                if job_id in seen_ids:
                    continue
                seen_ids.add(job_id)

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
                new_on_page += 1

                if len(jobs) >= limit:
                    break

            if new_on_page == 0 or len(card_blocks) < 5:
                # No more new jobs or reached end of results
                break

            start += len(card_blocks)
            if len(jobs) < limit:
                time.sleep(1.0)  # Gentle delay between page fetches

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

    @staticmethod
    def is_qa_title(title: str) -> bool:
        """
        Check if the job title represents a QA / SDET / Testing role.
        Rejects pure developer, DevOps, PM, data engineering, etc. positions.
        """
        if not config or not getattr(config, "ENABLE_TITLE_FILTER", True):
            return True
        t = (title or "").strip()
        if not t:
            return False

        # 1. Non-QA Overrides (e.g. "Software Engineer, Backend", "DevOps Engineer")
        overrides = getattr(config, "NON_QA_OVERRIDE_PATTERNS", [])
        for neg in overrides:
            if re.search(neg, t, re.IGNORECASE):
                # Allow only if title specifically includes explicit QA/SDET markers like "in Test", "SDET", "QA"
                if not re.search(r'\b(?:in\s+test|sdet|qa)\b', t, re.IGNORECASE):
                    return False

        # 2. Positive QA patterns
        patterns = getattr(config, "QA_TITLE_PATTERNS", [])
        has_qa = any(re.search(p, t, re.IGNORECASE) for p in patterns)

        # 3. Allow "Automation Engineer" unless it's hardware/PLC/marketing/GTM
        if not has_qa and re.search(r'\bautomation\s+engineers?\b', t, re.IGNORECASE):
            if not re.search(r'\b(?:plc|hardware|industrial|marketing|sales|network|gtm|revenue|business|crm|hubspot|salesforce)\b', t, re.IGNORECASE):
                has_qa = True

        return has_qa

    @staticmethod
    def is_location_blocked(location: str) -> bool:
        """
        Check if a job card's location string points to a region incompatible with a candidate in Ireland.
        E.g. Argentina, Brazil, India, USA, etc.
        """
        if not config or not getattr(config, "ENABLE_LINKEDIN_GEO_FILTER", True):
            return False
        loc = (location or "").strip()
        if not loc:
            return False
        # UK-only remote roles are domestic to the UK. Ireland and broad scopes
        # remain eligible when explicitly included in the location label.
        loc_without_northern_ireland = re.sub(r'\bnorthern\s+ireland\b', '', loc, flags=re.IGNORECASE)
        uk_only = re.search(r'\b(?:united kingdom|uk|england|scotland|wales|northern ireland)\b', loc, re.IGNORECASE)
        ireland_or_broad_scope = re.search(
            r'\b(?:ireland|europe|european union|eu|emea|worldwide|anywhere|global)\b',
            loc_without_northern_ireland,
            re.IGNORECASE,
        )
        if uk_only and not ireland_or_broad_scope:
            return True
        blocked_list = getattr(config, "LINKEDIN_BLOCKED_LOCATIONS", [])
        for pattern in blocked_list:
            regex = pattern if pattern.startswith(r"\b") else r"\b" + re.escape(pattern) + r"\b"
            if re.search(regex, loc, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def is_description_blocked(description: str) -> bool:
        """
        Check if the job description contains phrases indicating the role is restricted
        to foreign domestic residents (e.g. US only, Latam only, domestic salary tables, etc.)
        incompatible with a candidate based in Ireland.
        """
        if not description:
            return False
        d = description.lower()
        patterns = getattr(config, "LINKEDIN_DESCRIPTION_STOP_PATTERNS", []) if config else []
        for pat in patterns:
            if re.search(pat, d, re.IGNORECASE):
                return True
        return False

    def detect_workplace_type(self, title: str, location: str, description: str) -> str:
        t = title.lower()
        loc = location.lower()
        d = description.lower()

        # 0. Check against explicit blocked location first
        if self.is_location_blocked(location):
            return "onsite"  # Blocked region -> unusable for candidate in Ireland

        # 1. Domestic & Regional Remote Restrictions (must be checked early!)
        # E.g. "for Latam", "US only", "only within Germany", "must reside in Poland", "residents of UK only"
        domestic_restrictions = [
            r'nur\s+innerhalb\s+(?!irland|europa|eu\b)',
            r'only\s+(?:available\s+)?(?:within|in)\s+(?!ireland|europe|eu\b|the\s+eu\b)(?:the\s+)?[a-z]{2,}(?:\s+[a-z]+)?\b',
            r'must\s+(?:already\s+|currently\s+)?(?:be\s+)?(?:living|live|residing|reside|located|based|resident)\s+in\s+(?!ireland|europe\b|eu\b|the\s+eu\b)(?:the\s+)?[a-z]{2,}(?:\s+[a-z]+)?\b',
            r'residents?\s+of\s+(?!ireland|europe|eu\b|the\s+eu\b)(?:the\s+)?[a-z]{2,}(?:\s+[a-z]+)?\s+only\b',
            r'tax\s+residen(?:cy|t)\s+in\s+(?!ireland|europe|eu\b)(?:the\s+)?[a-z]{2,}(?:\s+[a-z]+)?\b',
            r'remote\s+(?:work\s+)?is\s+only\s+(?:possible|permitted|allowed)\s+(?:within|in)',
            r'remote\s+(?:within|from)\s+(?!ireland|europe|eu\b)(?:the\s+)?[a-z]{2,}(?:\s+[a-z]+)?\b',
        ]
        config_patterns = getattr(config, "LINKEDIN_DESCRIPTION_STOP_PATTERNS", []) if config else []
        for pattern in domestic_restrictions + config_patterns:
            if re.search(pattern, d, re.IGNORECASE):
                return "onsite"  # Restricted to another country/region -> unusable for candidate in Ireland

        # 2. Explicit On-site markers (multi-language & client-site markers)
        onsite_markers = [
            "on-site", "on site", "onsite",
            "100% on-site", "100% onsite", "fully on-site", "fully onsite",
            "office-based", "office based",
            "in-office", "in office",
            "client site", "client's site", "on client site", "on client's site",
            "working directly on client", "work directly on client", "directly on client",
            "on-site work", "onsite work", "work on-site", "work onsite",
            "working on-site", "working onsite",
            "work from the office", "working from the office", "work from office",
            "based in our office", "based at our office", "based in the office",
            "attendance required", "present on site", "present onsite",
            "physical presence", "presence required",
            "attend the office", "attending the office",
            "presence in the office", "presence in office",
            "visiting the office", "travel to client site", "travel to client",
            "travel to the office",
            "relocation required", "must relocate", "relocation package",
            "must be able to commute", "ability to commute",
            # German
            "vor ort", "im büro", "präsenzpflicht", "an unserem standort",
            # Hungarian
            "irodai munkavégzés", "személyes jelenlét", "helyszíni munkavégzés",
        ]
        has_onsite_marker = any(m in d for m in onsite_markers) or any(m in t for m in ["on-site", "onsite", "on site"])

        # 3. Hybrid check
        hybrid_markers = [
            "hybrid", "days in office", "days a week in office",
            "days in the office", "days a week in the office",
            "days per week in the office", "days per week at the office",
            "days/week in the office", "days per week from", "days per week in",
            "days per week office", "days/week in office", "days on-site", "days onsite",
            "days from home", "days a week from home", "days per week from home",
            "partial remote", "partially remote", "part-remote", "part remote",
            "mix of remote and office",
            "flexible working model", "flexible working policy",
            "flexible hybrid", "hybrid working", "hybrid work",
            "hybrid arrangement", "hybrid setup", "hybrid role", "hybrid model",
            "hybrid mode", "hybrid working mode", "work in a hybrid mode",
            "flexible/remote", "flexible / remote", "flexible or remote",
            "hybrid/remote", "hybrid / remote", "hybrid or remote",
            "split between home and office", "split between office and home",
            "split between remote and office", "split between office and remote",
            "blend of home and office", "blend of office and home",
            "blend of remote and office", "blended working",
            "smart working",
            "occasional office", "regular office visits", "time split between",
            "office days", "core office days",
            # German
            "hybrides arbeiten", "hybrid-modell", "tage im büro",
            # Hungarian
            "hibrid",
        ]
        hybrid_regex = [
            r'\b\d+\s*(?:-\s*\d+)?\s*days?\s+(?:a|per)?\s*week\s+(?:in|from|at)\s+(?:the\s+)?office\b',
            r'\b\d+\s*(?:-\s*\d+)?\s*days?\s+(?:in|at)\s+(?:the\s+)?office\b',
            r'\b\d+\s*(?:-\s*\d+)?\s*days?\s+(?:on-site|onsite)\b',
            r'\b\d+\s*(?:-\s*\d+)?\s*days?\s+(?:wfh|from\s+home)\b',
            r'\b\d+\s*(?:-\s*\d+)?\s*days?\s+(?:[a-z]+\s+){0,3}(?:wfh|from\s+home)\b',
            r'\b\d+\s*(?:-\s*\d+)?\s*days?\s+remote\b',
            r'\b(?:access(?:ing)?|attend(?:ing)?|visit(?:ing)?|in|at|to)\s+(?:the\s+)?office\b[^\.\n;]{0,60}\b\d+\s*(?:x|times?|days?)\s*(?:a|per)?\s*week\b',
            r'\b\d+\s*(?:x|times?|days?)\s*(?:a|per)?\s*week\b[^\.\n;]{0,60}\b(?:in|at|to\s+the\s+)?office\b',
            r'commutable\s+(?:to|from)\b',
            r'within\s+(?:a\s+)?commuting\s+distance\b',
            r'commute\s+to\s+(?:our\s+)?office\b',
        ]
        has_hybrid_regex = any(re.search(p, d) for p in hybrid_regex)
        if any(h in d for h in hybrid_markers) or "hybrid" in t or has_hybrid_regex:
            return "hybrid"

        # 4. Explicit International Remote Work (highest confidence for candidates in Ireland)
        international_remote = [
            "anywhere in europe", "anywhere in the eu", "anywhere in eu",
            "work from anywhere", "remote across europe", "remote in europe",
            "pan-european remote", "pan-european role", "pan-european position",
            "b2b contractor", "b2b contract", "contractor role",
            "full-time contractor", "independent contractor",
            "worldwide remote", "fully remote worldwide", "fully remote europe",
            "remote throughout europe", "remote - europe", "remote (europe)",
            "anywhere in ireland", "remote in ireland", "fully remote ireland",
            "remote within ireland", "remote across ireland",
            "work from anywhere in europe", "work from anywhere in the eu",
            "ireland or uk", "uk or ireland",
            "applicants worldwide", "candidates worldwide", "open worldwide",
            "open to worldwide", "worldwide considered",
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

        # 7. Decision logic considering location and candidate in Ireland
        loc_clean = re.sub(r'\(?\s*remote\s*\)?', '', loc, flags=re.IGNORECASE).strip(' ,-')
        loc_clean_no_ni = loc_clean.replace("northern ireland", "").strip(' ,-')
        is_generic_remote = loc_clean in ["", "remote", "worldwide", "anywhere", "europe", "european union", "eu"]
        is_ireland_generic = (loc_clean == "ireland")
        is_irish_city = bool("ireland" in loc_clean_no_ni and loc_clean_no_ni != "ireland")

        is_uk = any(k in loc_clean for k in ["united kingdom", "uk", "england", "scotland", "wales", "northern ireland"])
        is_uk_generic = (loc_clean in ["united kingdom", "uk"])
        is_uk_city = bool(is_uk and not is_uk_generic)

        is_foreign_specific_city = bool(
            loc_clean and not any(k in loc_clean_no_ni for k in ["ireland", "remote", "worldwide", "anywhere"]) and not is_uk
        )

        if has_onsite_marker:
            return "onsite"

        if has_explicit_remote:
            if is_irish_city or is_ireland_generic or is_generic_remote:
                return "remote"
            # UK or foreign city without explicit international remote is domestic remote for that country
            return "onsite"

        if has_general_remote:
            if is_ireland_generic or is_generic_remote:
                return "remote"
            return "onsite"

        # If location is a specific city anywhere without confirmed remote in description -> onsite
        if is_irish_city or is_uk_city or is_foreign_specific_city:
            return "onsite"

        if is_ireland_generic:
            return "unclear"

        return "unclear"

