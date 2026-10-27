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


class DjinniJobScraper:
    BASE_SEARCH_URL = "https://djinni.co/jobs/"

    def __init__(self):
        pass

    def _make_request(self, url: str) -> Optional[str]:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
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

                        # Region / Countries parsing (safely extract from dict or list)
                        loc_requirements = item.get("applicantLocationRequirements")
                        allowed_countries = []
                        allowed_regions = []

                        if loc_requirements:
                            req_items = loc_requirements if isinstance(loc_requirements, list) else [loc_requirements]
                            for req in req_items:
                                if not isinstance(req, dict):
                                    continue
                                addr = req.get("address")
                                if isinstance(addr, list) and addr:
                                    addr = addr[0]
                                if isinstance(addr, dict):
                                    c = addr.get("addressCountry")
                                    r = addr.get("addressRegion")
                                    if c:
                                        allowed_countries.append(str(c).upper())
                                    if r:
                                        allowed_regions.append(str(r))

                        # Format descriptive location label
                        if not loc_requirements or (not allowed_countries and not allowed_regions):
                            loc_summary = "Worldwide"
                        elif allowed_regions and not allowed_countries:
                            loc_summary = ", ".join(allowed_regions)
                        elif allowed_countries and not allowed_regions:
                            loc_summary = ", ".join(allowed_countries)
                        else:
                            loc_summary = f"{', '.join(allowed_regions)} ({', '.join(allowed_countries)})"

                        location_label = f"Remote ({loc_summary})" if is_remote else loc_summary

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
                            "applicant_countries": allowed_countries,
                            "applicant_regions": allowed_regions,
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


def is_djinni_country_eligible(
    job: Dict[str, Any],
    user_countries: Optional[List[str]] = None,
    user_regions: Optional[List[str]] = None,
) -> bool:
    """
    Checks if candidate in user_countries/user_regions is accepted by Djinni job.
    If the job does not restrict location (worldwide), returns True.
    """
    if user_countries is None:
        user_countries = ["IE", "IRL", "IRELAND"]
    if user_regions is None:
        user_regions = ["EUROPE", "EU", "WORLDWIDE", "ANY", "ALL"]

    user_countries_upper = {c.upper() for c in user_countries}
    user_regions_upper = {r.upper() for r in user_regions}

    allowed_countries = job.get("applicant_countries", [])
    allowed_regions = job.get("applicant_regions", [])

    # If Djinni specified no restrictions -> open Worldwide
    if not allowed_countries and not allowed_regions:
        return True

    # If any broad region matches (e.g. Europe, Worldwide)
    for reg in allowed_regions:
        if reg.upper() in user_regions_upper:
            return True

    # If candidate's specific country is listed (e.g. IE / IRL)
    for country in allowed_countries:
        if country.upper() in user_countries_upper:
            return True

    return False
