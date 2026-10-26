"""
Djinni.co Scraper for QA / SDET Remote positions.
Extracts structured JobPostings via Schema.org JSON-LD.
"""

import urllib.request
import urllib.parse
import json
import re
import html
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


class DjinniJobScraper:
    BASE_SEARCH_URL = "https://djinni.co/jobs/"

    def __init__(self):
        pass

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
            logger.error(f"Error fetching Djinni {url}: {e}")
        return None

    def search_jobs(self, keyword: str = "QA Automation", limit: int = 15) -> List[Dict[str, str]]:
        params = {"primary_keyword": keyword}
        url = f"{self.BASE_SEARCH_URL}?{urllib.parse.urlencode(params)}"
        html_content = self._make_request(url)
        if not html_content:
            return []

        jobs = []
        scripts = re.findall(r'<script\s+type="application/ld\+json">(.*?)</script>', html_content, re.DOTALL)
        for s in scripts:
            try:
                data = json.loads(s.strip())
                items = data if isinstance(data, list) else data.get("itemListElement", [data])
                for item in items:
                    if not isinstance(item, dict) or item.get("@type") != "JobPosting":
                        continue

                    job_id = f"djinni_{item.get('identifier')}"
                    title = item.get("title", "Untitled")
                    company = item.get("hiringOrganization", {}).get("name", "Unknown Company")
                    job_url = item.get("url", "")
                    date_posted = item.get("datePosted", "")
                    description = item.get("description", "")
                    is_remote = item.get("jobLocationType") == "TELECOMMUTE" or "remote" in description.lower()

                    # Region / Location
                    req_loc = item.get("applicantLocationRequirements", {}).get("address", {})
                    loc_region = req_loc.get("addressRegion") or req_loc.get("addressCountry") or "Remote"
                    location_label = f"Remote ({loc_region})" if is_remote else loc_region

                    # Look for salary in description or HTML
                    salary = ""
                    sal_m = re.search(r'(\$[\d,\s–-]+\b|\b\d+k\b)', title + " " + description[:200])
                    if sal_m:
                        salary = sal_m.group(1).strip()

                    jobs.append({
                        "id": job_id,
                        "title": title,
                        "company": company,
                        "location": location_label,
                        "url": job_url,
                        "posted_date": date_posted,
                        "description": description,
                        "salary": salary,
                        "source": "Djinni.co",
                        "keyword": keyword,
                        "workplace_type": "remote" if is_remote else "hybrid",
                    })

                    if len(jobs) >= limit:
                        break
            except Exception as e:
                logger.error(f"Error parsing Djinni JSON-LD: {e}")

        return jobs
