from unittest.mock import patch, MagicMock
import urllib.error
import json
import pytest
from himalayas_scraper import HimalayasJobScraper, is_himalayas_location_eligible
from telegram_notifier import TelegramNotifier

SAMPLE_HIMALAYAS_RESPONSE = {
    "totalCount": 100,
    "jobs": [
        {
            "guid": "him-uuid-1",
            "title": "Senior SDET / Automation Engineer",
            "companyName": "Automattic",
            "companySlug": "automattic",
            "locationRestrictions": ["Ireland", "United Kingdom", "Europe"],
            "timezoneRestrictions": [0, 1, 2],
            "minSalary": 80000,
            "maxSalary": 100000,
            "currency": "$",
            "salaryPeriod": "year",
            "applicationLink": "https://himalayas.app/companies/automattic/jobs/him-uuid-1",
            "description": "We are looking for a Senior SDET with Python and Selenium. Fully remote.",
            "pubDate": "2026-11-20T10:00:00Z"
        },
        {
            "guid": "him-uuid-2",
            "title": "Marketing Operations Manager",
            "companyName": "Buffer",
            "companySlug": "buffer",
            "locationRestrictions": [],
            "timezoneRestrictions": [],
            "minSalary": 60000,
            "maxSalary": 80000,
            "currency": "$",
            "salaryPeriod": "year",
            "applicationLink": "https://himalayas.app/companies/buffer/jobs/him-uuid-2",
            "description": "Marketing role open worldwide.",
            "pubDate": "2026-11-20T10:00:00Z"
        },
        {
            "guid": "him-uuid-3",
            "title": "Lead QA Engineer",
            "companyName": "US Only Tech",
            "companySlug": "us-tech",
            "locationRestrictions": ["United States"],
            "timezoneRestrictions": [-8, -7, -6, -5],
            "minSalary": 120000,
            "maxSalary": 150000,
            "currency": "$",
            "salaryPeriod": "year",
            "applicationLink": "https://himalayas.app/companies/us-tech/jobs/him-uuid-3",
            "description": "Must be located in the US. USA base pay range.",
            "pubDate": "2026-11-20T10:00:00Z"
        },
        {
            "guid": "him-uuid-4",
            "title": "Performance Test Engineer",
            "companyName": "GitLab",
            "companySlug": "gitlab",
            "locationRestrictions": [],
            "timezoneRestrictions": [],
            "minSalary": None,
            "maxSalary": None,
            "applicationLink": "https://himalayas.app/companies/gitlab/jobs/him-uuid-4",
            "description": "Worldwide remote performance test engineer with Playwright.",
            "pubDate": "2026-11-20T10:00:00Z"
        }
    ]
}


class TestHimalayasEligibility:
    """Tests location and timezone eligibility for Himalayas jobs."""

    def test_open_worldwide_when_empty_restrictions(self):
        assert is_himalayas_location_eligible([]) is True
        assert is_himalayas_location_eligible(None) is True

    def test_allowed_when_ireland_or_europe_specified(self):
        assert is_himalayas_location_eligible(["Ireland"]) is True
        assert is_himalayas_location_eligible(["United Kingdom"]) is True
        assert is_himalayas_location_eligible(["Europe"]) is True
        assert is_himalayas_location_eligible(["EMEA"]) is True
        assert is_himalayas_location_eligible(["Worldwide"]) is True

    def test_country_specific_restrictions_must_include_ireland_or_accepted_scope(self):
        assert is_himalayas_location_eligible(["Netherlands"]) is False
        assert is_himalayas_location_eligible(["Poland", "Portugal", "Serbia", "Croatia"]) is False
        assert is_himalayas_location_eligible(["Ireland", "Netherlands"]) is True
        assert is_himalayas_location_eligible(["Europe", "Netherlands"]) is True

    def test_blocked_when_domestic_foreign_country(self):
        assert is_himalayas_location_eligible(["United States"]) is False
        assert is_himalayas_location_eligible(["Australia", "Singapore"]) is False
        assert is_himalayas_location_eligible(["India"]) is False
        assert is_himalayas_location_eligible(["Brazil"]) is False

    def test_timezone_overlap_with_ireland(self):
        # Irish/EMEA timezones (-2 to +4)
        assert is_himalayas_location_eligible(["Ireland"], [0, 1]) is True
        assert is_himalayas_location_eligible(["Europe"], [2, 3]) is True
        # Pure US or APAC timezones
        assert is_himalayas_location_eligible(["Ireland"], [-8, -7, -6, -5]) is False
        assert is_himalayas_location_eligible(["Ireland"], [8, 9, 10]) is False


class TestHimalayasScraper:
    """Tests for Himalayas scraper."""

    def test_parse_single_job_rejects_netherlands_only_remote_project(self):
        scraper = HimalayasJobScraper()
        job_raw = {
            "guid": "tester-work-netherlands",
            "title": "App Testers wanted in the Netherlands!",
            "companyName": "Tester Work",
            "companySlug": "tester-work",
            "locationRestrictions": ["Netherlands"],
            "timezoneRestrictions": [0, 1, 2],
            "description": "Flexible part-time remote app testing project.",
            "applicationLink": "https://himalayas.app/companies/tester-work/jobs/app-testers-wanted-in-the-netherlands",
        }
        assert scraper._parse_single_job(job_raw) is None

    def test_parse_single_job_extracts_correct_fields(self):
        scraper = HimalayasJobScraper()
        job_raw = SAMPLE_HIMALAYAS_RESPONSE["jobs"][0]
        parsed = scraper._parse_single_job(job_raw)

        assert parsed is not None
        assert parsed["id"] == "himalayas_him-uuid-1"
        assert parsed["title"] == "Senior SDET / Automation Engineer"
        assert parsed["company"] == "Automattic"
        assert "Remote" in parsed["location"]
        assert "$80,000 - $100,000 / year" in parsed["salary"]
        assert parsed["source"] == "Himalayas"
        assert parsed["workplace_type"] == "remote"
        assert parsed["posted_date"] == "2026-11-20"

    def test_search_jobs_filters_non_qa_roles(self):
        scraper = HimalayasJobScraper(max_pages=1)
        with patch.object(scraper, "_fetch_page", return_value=SAMPLE_HIMALAYAS_RESPONSE):
            jobs = scraper.search_jobs(max_pages=1, remote_only=True, qa_only=True)
            titles = [j["title"] for j in jobs]
            assert "Marketing Operations Manager" not in titles

    def test_search_jobs_filters_ineligible_us_location(self):
        scraper = HimalayasJobScraper(max_pages=1)
        with patch.object(scraper, "_fetch_page", return_value=SAMPLE_HIMALAYAS_RESPONSE):
            jobs = scraper.search_jobs(max_pages=1, remote_only=True, qa_only=True)
            titles = [j["title"] for j in jobs]
            # Job 3 is US Only QA, must be filtered out
            assert "Lead QA Engineer" not in titles
            # Job 1 (Europe SDET) and Job 4 (Worldwide QA) should pass
            assert "Senior SDET / Automation Engineer" in titles
            assert "Performance Test Engineer" in titles
            assert len(jobs) == 2

    def test_fetch_page_network_error(self):
        scraper = HimalayasJobScraper()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Timeout")
            res = scraper._fetch_page(0)
            assert res is None

    def test_himalayas_telegram_badge_formatting(self, notifier_configured):
        job = {
            "id": "himalayas_him-uuid-1",
            "title": "Senior SDET / Automation Engineer",
            "company": "Automattic",
            "location": "Remote (Ireland)",
            "url": "https://himalayas.app/companies/automattic/jobs/him-uuid-1",
            "source": "Himalayas",
            "salary": "$80,000 - $100,000 / year",
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
            assert "Himalayas (himalayas.app)" in text
            assert "$80,000" in text
            assert "Открыть вакансию на Himalayas" in text
