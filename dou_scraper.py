"""
DOU (jobs.dou.ua) Scraper for QA / SDET Remote positions.
Extracts structured JobPostings via official RSS feed.
"""

import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import re
import html
import random
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]


class DouJobScraper:
    FEED_URL = "https://jobs.dou.ua/vacancies/feeds/"

    def __init__(self):
        pass

    def _fetch_feed(self, category: str = "QA", remote_only: bool = True) -> Optional[str]:
        query_parts = [f"category={urllib.parse.quote(category)}"]
        if remote_only:
            query_parts.append("remote")
        url = f"{self.FEED_URL}?{'&'.join(query_parts)}"

        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
            "Accept-Language": "en-US,en;q=0.9,uk;q=0.8",
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    return resp.read().decode("utf-8", errors="ignore")
                logger.warning(f"Unexpected status {resp.status} for {url}")
        except Exception as e:
            logger.error(f"Error fetching DOU feed {url}: {e}")
        return None

    def search_jobs(self, category: str = "QA", remote_only: bool = True, limit: int = 50) -> List[Dict[str, str]]:
        xml_content = self._fetch_feed(category=category, remote_only=remote_only)
        if not xml_content:
            return []
        return self.parse_feed(xml_content, limit=limit)

    def parse_feed(self, xml_content: str, limit: int = 50) -> List[Dict[str, str]]:
        jobs = []
        try:
            root = ET.fromstring(xml_content)
        except Exception as e:
            logger.error(f"Failed to parse XML from DOU: {e}")
            return []

        channel = root.find("channel")
        if channel is None:
            return []

        for item in channel.findall("item"):
            if len(jobs) >= limit:
                break

            link = (item.find("link").text or "").strip() if item.find("link") is not None else ""
            if not link:
                continue

            clean_url = re.sub(r"\?utm_.*$", "", link)
            m_id = re.search(r"/vacancies/(\d+)/", clean_url)
            job_id = f"dou_{m_id.group(1)}" if m_id else f"dou_{clean_url}"

            raw_title = (item.find("title").text or "").strip() if item.find("title") is not None else ""
            raw_title = html.unescape(raw_title)

            # Title format on DOU RSS: "<JobTitle> в <Company>[, <Location>, <Salary>, віддалено]"
            if " в " in raw_title:
                title_part, rest = raw_title.split(" в ", 1)
                title = title_part.strip()
                if "," in rest:
                    parts = [p.strip() for p in rest.split(",")]
                    company = parts[0]
                    location_parts = parts[1:]
                else:
                    company = rest.strip()
                    location_parts = ["віддалено"]
            else:
                title = raw_title
                company = "Unknown Company"
                location_parts = ["віддалено"]

            salary = ""
            sal_m = re.search(r'(\$[\d,\s–-]+\b|\b\d+k\b|€[\d,\s–-]+\b)', " ".join(location_parts) + " " + title)
            if sal_m:
                salary = sal_m.group(1).strip()
                location_parts = [p for p in location_parts if salary not in p]

            location = ", ".join(location_parts) if location_parts else "віддалено"

            raw_desc = (item.find("description").text or "").strip() if item.find("description") is not None else ""
            clean_desc = re.sub(r"<[^>]+>", " ", raw_desc)
            clean_desc = html.unescape(clean_desc)
            clean_desc = re.sub(r"\s+", " ", clean_desc).strip()

            pub_date = (item.find("pubDate").text or "").strip() if item.find("pubDate") is not None else ""

            jobs.append({
                "id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "url": clean_url,
                "posted_date": pub_date,
                "description": clean_desc,
                "salary": salary,
                "source": "DOU",
                "workplace_type": "remote",
            })

        return jobs
