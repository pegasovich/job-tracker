"""
LinkedIn Public Job Scraper for Ireland (Remote)
Uses LinkedIn Guest API (no login, no cookies, no risk of ban).
"""

import urllib.request
import urllib.parse
import re
import html
import time
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


class LinkedInJobScraper:
    BASE_SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    BASE_DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{}"

    def __init__(self, location: str = "Ireland", remote_only: bool = True):
        self.location = location
        self.remote_only = remote_only

    def _make_request(self, url: str) -> Optional[str]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    return resp.read().decode("utf-8", errors="ignore")
                logger.warning(f"Unexpected status {resp.status} for {url}")
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
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
        html_content = self._make_request(url)
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
        html_content = self._make_request(url)
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
        """
        Classifies workplace type as 'remote', 'hybrid', or 'onsite'.
        """
        t = title.lower()
        loc = location.lower()
        d = description.lower()

        # Hybrid check
        if any(h in d for h in ["hybrid", "days in office", "days a week in office", "days per week from", "days per week in", "days/week in office"]) or "hybrid" in t:
            return "hybrid"

        # Explicit remote check in text or title
        if any(r in d for r in ["fully remote", "100% remote", "work from home", "wfh", "anywhere in ireland", "home-based", "home based", "virtual role", "remote-first", "remote work"]):
            return "remote"

        # General remote mention
        if "remote" in d or "remote" in t:
            return "remote"

        # If location is specifically a physical town/county (like 'Galway', 'Dublin', 'Cork') and no remote/hybrid mention -> On-site!
        if loc != "ireland" and loc != "":
            return "onsite"

        if loc == "ireland":
            return "remote"

        return "unclear"
