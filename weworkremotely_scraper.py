"""
WeWorkRemotely (WWR) RSS Scraper for Remote QA / SDET positions.
Parses official WWR RSS feeds for curated 100% remote tech jobs.
"""

import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import re
import html
import random
import logging
from typing import List, Dict, Optional, Any

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
]

DEFAULT_FEEDS = [
    "https://weworkremotely.com/remote-jobs.rss",
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
]


class WeWorkRemotelyJobScraper:
    def __init__(self, feeds: Optional[List[str]] = None):
        self.feeds = feeds or DEFAULT_FEEDS

    def _fetch_feed(self, url: str) -> Optional[str]:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    return resp.read().decode("utf-8", errors="ignore")
                logger.warning(f"Unexpected status {resp.status} for WWR feed: {url}")
        except Exception as e:
            logger.error(f"Error fetching WWR feed {url}: {e}")
        return None

    @staticmethod
    def is_qa_title(title: str) -> bool:
        from linkedin_scraper import LinkedInJobScraper
        return LinkedInJobScraper.is_qa_title(title)

    def search_jobs(
        self,
        remote_only: bool = True,
        limit: int = 50,
        qa_only: bool = True,
    ) -> List[Dict[str, Any]]:
        seen_urls = set()
        all_jobs = []

        for feed_url in self.feeds:
            if len(all_jobs) >= limit:
                break

            xml_content = self._fetch_feed(feed_url)
            if not xml_content:
                continue

            parsed_items = self.parse_feed(xml_content, limit=limit - len(all_jobs), qa_only=qa_only)
            for job in parsed_items:
                if job["url"] not in seen_urls:
                    seen_urls.add(job["url"])
                    all_jobs.append(job)
                    if len(all_jobs) >= limit:
                        break

        return all_jobs

    def parse_feed(self, xml_content: str, limit: int = 50, qa_only: bool = True) -> List[Dict[str, Any]]:
        jobs = []
        try:
            root = ET.fromstring(xml_content)
        except Exception as e:
            logger.error(f"Failed to parse WWR RSS XML: {e}")
            return []

        channel = root.find("channel")
        if channel is None:
            return []

        for item in channel.findall("item"):
            if len(jobs) >= limit:
                break

            raw_title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            guid = item.findtext("guid", "").strip() or link
            pub_date = item.findtext("pubDate", "").strip()
            raw_desc = item.findtext("description", "").strip()

            if not raw_title or not link:
                continue

            # WWR titles are usually "Company Name: Job Title"
            if ":" in raw_title:
                parts = raw_title.split(":", 1)
                company = parts[0].strip()
                title = parts[1].strip()
            else:
                company = "Unknown Company"
                title = raw_title

            if qa_only and not self.is_qa_title(title):
                continue

            # Clean HTML description
            clean_desc = html.unescape(re.sub(r"<[^>]+>", " ", raw_desc))
            clean_desc = re.sub(r"\s+", " ", clean_desc).strip()

            # Regional stop patterns check (Americas/LATAM/Asia-only restrictions)
            if config and hasattr(config, "LINKEDIN_DESCRIPTION_STOP_PATTERNS"):
                text_to_check = f"{title} {clean_desc}".lower()
                is_blocked = any(re.search(pat, text_to_check, re.IGNORECASE) for pat in config.LINKEDIN_DESCRIPTION_STOP_PATTERNS)
                if is_blocked:
                    continue

            # Check for salary mentions
            salary = ""
            sal_m = re.search(
                r'([$€£]\s*[\d,\.]+\s*(?:k|K)?(?:\s*[-–]\s*[$€£]?\s*[\d,\.]+\s*(?:k|K)?)?(?:/(?:hr|hour|day|year|mo|month|yr))?|\b\d+k\b)',
                raw_title + " " + clean_desc[:400],
                re.IGNORECASE,
            )
            if sal_m:
                salary = sal_m.group(1).strip()

            # Slug or ID from GUID/link
            slug = guid.rstrip("/").split("/")[-1]
            job_id = f"wwr_{slug}" if slug else f"wwr_{abs(hash(link))}"

            jobs.append({
                "id": job_id,
                "title": title,
                "company": company,
                "location": "Remote (Worldwide)",
                "url": link,
                "posted_date": pub_date[:16] if pub_date else "",
                "description": clean_desc,
                "salary": salary,
                "source": "WeWorkRemotely",
                "workplace_type": "remote",
            })

        return jobs
