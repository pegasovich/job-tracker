from unittest.mock import patch, MagicMock
import urllib.error
import json
import pytest
from ashby_scraper import AshbyJobScraper
from telegram_notifier import TelegramNotifier

SAMPLE_ASHBY_RESPONSE = {
    "jobs": [
        {
            "id": "ashby-uuid-1",
            "title": "Senior SDET - Core Infrastructure",
            "department": "Engineering",
            "employmentType": "FullTime",
            "location": "Remote - Europe",
            "isRemote": True,
            "workplaceType": "Remote",
            "address": {
                "postalAddress": {
                    "addressCountry": "Ireland",
                    "addressLocality": "Dublin"
                }
            },
            "jobUrl": "https://jobs.ashbyhq.com/synthesia/ashby-uuid-1",
            "applyUrl": "https://jobs.ashbyhq.com/synthesia/ashby-uuid-1/application",
            "descriptionPlain": "We are seeking a Senior SDET with Python experience. Salary: €85,000 - €105,000.",
            "publishedAt": "2026-11-20T10:00:00Z"
        },
        {
            "id": "ashby-uuid-2",
            "title": "Product Marketing Manager",
            "department": "Marketing",
            "employmentType": "FullTime",
            "location": "Remote",
            "isRemote": True,
            "workplaceType": "Remote",
            "address": {
                "postalAddress": {
                    "addressCountry": "United Kingdom"
                }
            },
            "jobUrl": "https://jobs.ashbyhq.com/synthesia/ashby-uuid-2",
            "descriptionPlain": "Product marketing manager role.",
            "publishedAt": "2026-11-20T10:00:00Z"
        },
        {
            "id": "ashby-uuid-3",
            "title": "QA Automation Engineer",
            "department": "Engineering",
            "employmentType": "FullTime",
            "location": "New York Office",
            "isRemote": False,
            "workplaceType": "OnSite",
            "address": {
                "postalAddress": {
                    "addressCountry": "United States"
                }
            },
            "jobUrl": "https://jobs.ashbyhq.com/synthesia/ashby-uuid-3",
            "descriptionPlain": "Onsite QA role in NYC.",
            "publishedAt": "2026-11-20T10:00:00Z"
        },
        {
            "id": "ashby-uuid-4",
            "title": "Lead SDET Engineer",
            "department": "Engineering",
            "employmentType": "FullTime",
            "location": "US Remote",
            "isRemote": True,
            "workplaceType": "Remote",
            "address": {
                "postalAddress": {
                    "addressCountry": "United States"
                }
            },
            "jobUrl": "https://jobs.ashbyhq.com/synthesia/ashby-uuid-4",
            "descriptionPlain": "USA base pay range: $150,000 - $190,000.",
            "publishedAt": "2026-11-20T10:00:00Z"
        }
    ]
}


class TestAshbyScraper:
    """Tests for Ashby direct ATS scraper."""

    def test_parse_single_job_extracts_correct_fields(self):
        scraper = AshbyJobScraper(companies=["synthesia"])
        job_raw = SAMPLE_ASHBY_RESPONSE["jobs"][0]
        parsed = scraper._parse_single_job(job_raw, company_fallback="synthesia", remote_only=True)

        assert parsed is not None
        assert parsed["id"] == "ashby_synthesia_ashby-uuid-1"
        assert parsed["title"] == "Senior SDET - Core Infrastructure"
        assert parsed["company"] == "Synthesia"
        assert "Remote" in parsed["location"]
        assert parsed["url"] == "https://jobs.ashbyhq.com/synthesia/ashby-uuid-1"
        assert "€85,000" in parsed["salary"]
        assert parsed["source"] == "Ashby"
        assert parsed["workplace_type"] == "remote"
        assert parsed["posted_date"] == "2026-11-20"

    def test_search_jobs_remote_only_filters_out_onsite(self):
        scraper = AshbyJobScraper(companies=["synthesia"])
        with patch.object(scraper, "_fetch_company_jobs", return_value=SAMPLE_ASHBY_RESPONSE):
            jobs = scraper.search_jobs(remote_only=True, qa_only=True)
            # Job 1 (Europe SDET) passes. Job 2 is non-QA, Job 3 is OnSite, Job 4 is US Remote.
            assert len(jobs) == 1
            assert jobs[0]["title"] == "Senior SDET - Core Infrastructure"

    def test_search_jobs_qa_only_filters_out_non_qa_roles(self):
        scraper = AshbyJobScraper(companies=["synthesia"])
        with patch.object(scraper, "_fetch_company_jobs", return_value=SAMPLE_ASHBY_RESPONSE):
            jobs = scraper.search_jobs(remote_only=False, qa_only=True)
            titles = [j["title"] for j in jobs]
            assert "Product Marketing Manager" not in titles

    def test_us_remote_and_geo_blocked_roles_rejected(self):
        scraper = AshbyJobScraper(companies=["synthesia"])
        job_us = SAMPLE_ASHBY_RESPONSE["jobs"][3]
        parsed = scraper._parse_single_job(job_us, company_fallback="synthesia", remote_only=True)
        assert parsed is None

    def test_fetch_company_jobs_network_error(self):
        scraper = AshbyJobScraper(companies=["synthesia"])
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
            res = scraper._fetch_company_jobs("synthesia")
            assert res is None

    def test_ashby_telegram_badge_formatting(self, notifier_configured):
        job = {
            "id": "ashby_synthesia_ashby-uuid-1",
            "title": "Senior SDET - Core Infrastructure",
            "company": "Synthesia",
            "location": "Remote (Europe)",
            "url": "https://jobs.ashbyhq.com/synthesia/ashby-uuid-1",
            "source": "Ashby",
            "salary": "€85,000 - €105,000",
        }
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            notifier_configured.send_job_alert(job)
            assert mock_urlopen.called

            request_obj = mock_urlopen.call_args[0][0]
            payload_data = json.loads(request_obj.data.decode("utf-8"))
            text = payload_data["text"]
            assert "Ashby (Direct ATS)" in text
            assert "€85,000" in text
            assert "Открыть вакансию на Ashby" in text
