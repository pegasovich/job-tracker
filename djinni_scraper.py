"""
Djinni.co Scraper for QA / SDET Remote positions.
Extracts structured JobPostings via Schema.org JSON-LD with multi-page support.
"""

import urllib.request
import urllib.parse
import json
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

    def search_jobs(self, keyword: str = "QA Automation", max_pages: int = 5, limit: int = 60) -> List[Dict[str, str]]:
        jobs = []
        for page in range(1, max_pages + 1):
            params = {"primary_keyword": keyword}
            if page > 1:
                params["page"] = page

            url = f"{self.BASE_SEARCH_URL}?{urllib.parse.urlencode(params)}"
            html_content = self._make_request(url)
            if not html_content:
                break

            page_jobs_count = 0
            scripts = re.findall(r'<script\s+type="application/ld\+json">(.*?)</script>', html_content, re.DOTALL)
            for s in scripts:
                try:
                    data = json.loads(s.strip())
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        items = data.get("itemListElement") or [data]
                        if not isinstance(items, list):
                            items = [items]
                    else:
                        continue

                    for item in items:
                        if not isinstance(item, dict) or item.get("@type") != "JobPosting":
                            continue

                        job_id = f"djinni_{item.get('identifier')}"
                        title = item.get("title", "Untitled")

                        # Title relevance filter (ensure it's actually a QA/testing job)
                        title_lower = title.lower()
                        if not any(k in title_lower for k in ["qa", "test", "sdet", "quality"]):
                            continue

                        company = item.get("hiringOrganization", {}).get("name", "Unknown Company")
                        job_url = item.get("url", "")
                        date_posted = item.get("datePosted", "")
                        description = item.get("description", "")
                        is_remote = item.get("jobLocationType") == "TELECOMMUTE" or "remote" in description.lower()

                        # Region / Location (safely extract from dict or list)
                        loc_requirements = item.get("applicantLocationRequirements")
                        if isinstance(loc_requirements, list) and loc_requirements:
                            loc_requirements = loc_requirements[0]
                        if not isinstance(loc_requirements, dict):
                            loc_requirements = {}

                        address = loc_requirements.get("address")
                        if isinstance(address, list) and address:
                            address = address[0]
                        if not isinstance(address, dict):
                            address = {}

                        loc_region = address.get("addressRegion") or address.get("addressCountry") or "Remote"
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
                        page_jobs_count += 1

                        if len(jobs) >= limit:
                            return jobs
                except Exception as e:
                    logger.error(f"Error parsing Djinni JSON-LD: {e}", exc_info=True)

            if page_jobs_count == 0:
                break
            time.sleep(1.0)

        return jobs
