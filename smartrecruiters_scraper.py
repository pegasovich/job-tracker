"""SmartRecruiters ATS scraper for direct tech company career portals.

Queries public SmartRecruiters Postings API:
https://api.smartrecruiters.com/v1/companies/{company}/postings
"""

import html
import json
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.parse
import urllib.request

try:
    import config
except ImportError:
    config = None

from linkedin_scraper import LinkedInJobScraper

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]

# Country codes outside Ireland that represent domestic non-Irish markets
# unless the posting body explicitly confirms pan-European/worldwide remote eligibility.
_BLOCKED_DOMESTIC_COUNTRIES = {
    "us", "ca", "in", "br", "mx", "ar", "co", "cl", "pe",
    "au", "nz", "ph", "pk", "bd", "vn", "id", "my", "sg",
    "th", "cn", "jp", "kr", "tw", "za", "ng", "ke", "eg",
    "ae", "sa", "qa", "il", "tr", "gb", "uk", "kz",
}


class SmartRecruitersJobScraper:
    """Fetch QA/SDET roles from public SmartRecruiters company posting feeds."""

    LIST_URL = "https://api.smartrecruiters.com/v1/companies/{company}/postings"
    DETAIL_URL = "https://api.smartrecruiters.com/v1/companies/{company}/postings/{posting_id}"

    def __init__(self, companies: Optional[List[str]] = None):
        if companies is not None:
            self.companies = companies
        elif config and hasattr(config, "SMARTRECRUITERS_COMPANIES"):
            self.companies = config.SMARTRECRUITERS_COMPANIES
        else:
            self.companies = [
                "Mirantis",
                "InvisibleTechnologies",
                "Wise",
                "DeliveryHero",
                "Devoteam",
                "Experian",
                "WesternDigital",
                "BoschGroup",
            ]

    def _get_json(self, url: str) -> Optional[Dict[str, Any]]:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                    return data if isinstance(data, dict) else None
                logger.warning("Unexpected status %s for SmartRecruiters URL: %s", resp.status, url)
        except Exception as exc:
            logger.error("Error querying SmartRecruiters API (%s): %s", url, exc)
        return None

    def _fetch_company_postings(self, company: str, query: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"limit": limit}
        if query:
            params["q"] = query
        url = f"{self.LIST_URL.format(company=urllib.parse.quote(company))}?{urllib.parse.urlencode(params)}"
        data = self._get_json(url)
        return data.get("content") or [] if data else []

    def _fetch_posting_detail(self, company: str, posting_id: str) -> Optional[Dict[str, Any]]:
        url = self.DETAIL_URL.format(
            company=urllib.parse.quote(company),
            posting_id=urllib.parse.quote(posting_id),
        )
        return self._get_json(url)

    @staticmethod
    def is_qa_title(title: str) -> bool:
        return LinkedInJobScraper.is_qa_title(title)

    @staticmethod
    def _extract_description(detail: Dict[str, Any]) -> str:
        sections = (detail.get("jobAd") or {}).get("sections") or {}
        parts = []
        for key in ("jobDescription", "qualifications", "additionalInformation", "companyDescription"):
            sec = sections.get(key)
            if isinstance(sec, dict) and sec.get("text"):
                parts.append(str(sec["text"]))
        raw_html = " ".join(parts)
        clean = html.unescape(re.sub(r"<[^>]+>", " ", raw_html))
        return re.sub(r"\s+", " ", clean).strip()

    def search_jobs(
        self,
        companies: Optional[List[str]] = None,
        queries: Optional[List[str]] = None,
        remote_only: bool = True,
        limit_per_company: int = 20,
        qa_only: bool = True,
    ) -> List[Dict[str, Any]]:
        target_companies = companies or self.companies
        search_queries = queries if queries is not None else ["QA", "SDET", "Test"]
        all_jobs: List[Dict[str, Any]] = []
        classifier = LinkedInJobScraper(location="Ireland")

        for company in target_companies:
            seen_ids = set()
            company_jobs_count = 0

            for q_idx, query in enumerate(search_queries):
                if company_jobs_count >= limit_per_company:
                    break
                if q_idx:
                    time.sleep(0.2)

                postings = self._fetch_company_postings(company, query=query, limit=50)
                for item in postings:
                    if company_jobs_count >= limit_per_company:
                        break
                    posting_id = str(item.get("id") or "").strip()
                    if not posting_id or posting_id in seen_ids:
                        continue
                    seen_ids.add(posting_id)

                    title = (item.get("name") or "").strip()
                    if qa_only and not self.is_qa_title(title):
                        continue

                    loc_obj = item.get("location") or {}
                    full_loc = (loc_obj.get("fullLocation") or "").strip()
                    country = str(loc_obj.get("country") or "").lower().strip()
                    is_remote_flag = loc_obj.get("remote") is True
                    is_hybrid_flag = loc_obj.get("hybrid") is True

                    if remote_only:
                        if is_hybrid_flag:
                            continue
                        if not is_remote_flag and "remote" not in f"{title} {full_loc}".lower():
                            continue
                        if country in _BLOCKED_DOMESTIC_COUNTRIES:
                            continue
                        if full_loc and LinkedInJobScraper.is_location_blocked(full_loc):
                            continue

                    detail = self._fetch_posting_detail(company, posting_id)
                    if not detail:
                        continue
                    parsed = self._parse_detail_job(
                        detail,
                        company_id=company,
                        remote_only=remote_only,
                        classifier=classifier,
                    )
                    if parsed:
                        all_jobs.append(parsed)
                        company_jobs_count += 1

        return all_jobs

    def _parse_detail_job(
        self,
        detail: Dict[str, Any],
        company_id: str,
        remote_only: bool = True,
        classifier: Optional[LinkedInJobScraper] = None,
    ) -> Optional[Dict[str, Any]]:
        posting_id = str(detail.get("id") or "").strip()
        if not posting_id:
            return None

        title = (detail.get("name") or "").strip()
        company_name = ((detail.get("company") or {}).get("name") or company_id).strip()
        loc_obj = detail.get("location") or {}
        full_loc = (loc_obj.get("fullLocation") or "").strip()
        country = str(loc_obj.get("country") or "").lower().strip()
        is_remote_flag = loc_obj.get("remote") is True
        is_hybrid_flag = loc_obj.get("hybrid") is True

        if remote_only:
            if is_hybrid_flag:
                return None
            if country in _BLOCKED_DOMESTIC_COUNTRIES:
                return None
            if full_loc and LinkedInJobScraper.is_location_blocked(full_loc):
                return None

        description = self._extract_description(detail)
        if remote_only and LinkedInJobScraper.is_description_blocked(description):
            return None

        is_remote = is_remote_flag or "remote" in f"{title} {full_loc}".lower()
        if remote_only and not is_remote:
            return None

        classifier = classifier or LinkedInJobScraper(location="Ireland")
        title_hint = f"{title} (Remote)" if is_remote and "remote" not in title.lower() else title
        detected = classifier.detect_workplace_type(title_hint, full_loc or "Remote", description)
        if remote_only and detected != "remote":
            return None

        workplace_type = detected if detected in ("remote", "hybrid", "onsite") else ("remote" if is_remote else "onsite")
        location = f"Remote ({full_loc})" if is_remote and full_loc and "remote" not in full_loc.lower() else (full_loc or ("Remote" if is_remote else "On-Site"))

        salary = ""
        sal_m = re.search(
            r'([$€£]\s*[\d,\.]+\s*(?:k|K)?(?:\s*[-–]\s*[$€£]?\s*[\d,\.]+\s*(?:k|K)?)?(?:/(?:hr|hour|day|year|mo|month|yr))?|\b\d+k\b)',
            f"{title} {description[:400]}",
            re.IGNORECASE,
        )
        if sal_m:
            salary = sal_m.group(1).strip()

        url = (detail.get("postingUrl") or detail.get("applyUrl") or f"https://jobs.smartrecruiters.com/{company_id}/{posting_id}").strip()
        posted_date = str(detail.get("releasedDate") or "")[:10]
        emp_type = str(((detail.get("typeOfEmployment") or {}).get("label")) or "").strip()

        result: Dict[str, Any] = {
            "id": f"smartrecruiters_{company_id}_{posting_id}",
            "title": title,
            "company": company_name,
            "location": location,
            "url": url,
            "posted_date": posted_date,
            "description": description,
            "salary": salary,
            "source": "SmartRecruiters",
            "workplace_type": workplace_type,
        }
        if emp_type:
            result["employment_type"] = emp_type
        return result
