import urllib.error
from unittest.mock import patch

from smartrecruiters_scraper import SmartRecruitersJobScraper
from workable_scraper import WorkableJobScraper


class TestWorkableJobScraper:
    def test_parses_ireland_and_eu_remote_qa_and_rejects_domestic_foreign_or_onsite(self):
        payload = {
            "name": "Zyte",
            "jobs": [
                {
                    "shortcode": "ABC123",
                    "title": "Senior QA Automation Engineer",
                    "telecommuting": True,
                    "country": "Ireland",
                    "city": "Dublin",
                    "url": "https://apply.workable.com/j/ABC123",
                    "published_on": "2026-11-22",
                    "employment_type": "Contract",
                    "description": "<p>Playwright &amp; Python SDET. €450 per day.</p>",
                },
                {
                    "shortcode": "DEF456",
                    "title": "QA Engineer",
                    "telecommuting": True,
                    "country": "Germany",
                    "city": "Berlin",
                    "url": "https://apply.workable.com/j/DEF456",
                    "description": "<p>Join our Berlin QA team.</p>",
                },
                {
                    "shortcode": "GHI789",
                    "title": "Manual QA Tester",
                    "telecommuting": False,
                    "country": "Ireland",
                    "city": "Dublin",
                    "url": "https://apply.workable.com/j/GHI789",
                    "description": "<p>Dublin office role.</p>",
                },
                {
                    "shortcode": "JKL000",
                    "title": "Senior Backend Engineer",
                    "telecommuting": True,
                    "country": "Ireland",
                    "url": "https://apply.workable.com/j/JKL000",
                    "description": "<p>Backend Go role.</p>",
                },
            ],
        }

        scraper = WorkableJobScraper(companies=["zyte"])
        with patch.object(scraper, "_fetch_company_jobs", return_value=payload):
            jobs = scraper.search_jobs(remote_only=True, qa_only=True)

        assert len(jobs) == 1
        assert jobs[0]["id"] == "workable_zyte_ABC123"
        assert jobs[0]["company"] == "Zyte"
        assert jobs[0]["source"] == "Workable"
        assert jobs[0]["workplace_type"] == "remote"
        assert "€450" in jobs[0]["salary"]

    def test_fetch_error_returns_empty(self):
        scraper = WorkableJobScraper(companies=["zyte"])
        with patch("workable_scraper.urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            assert scraper.search_jobs() == []


class TestSmartRecruitersJobScraper:
    def test_filters_non_qa_and_blocked_countries_before_detail_fetch(self):
        list_items = [
            {
                "id": "sr_1",
                "name": "Senior SDET",
                "location": {"fullLocation": "Dublin, Ireland", "country": "ie", "remote": True, "hybrid": False},
            },
            {
                "id": "sr_2",
                "name": "QA Engineer",
                "location": {"fullLocation": "Austin, TX, United States", "country": "us", "remote": True, "hybrid": False},
            },
            {
                "id": "sr_3",
                "name": "QA Automation Engineer",
                "location": {"fullLocation": "Sofia, Bulgaria", "country": "bg", "remote": True, "hybrid": False},
            },
            {
                "id": "sr_4",
                "name": "Senior Backend Engineer",
                "location": {"fullLocation": "Ireland", "country": "ie", "remote": True, "hybrid": False},
            },
        ]
        detail_ie = {
            "id": "sr_1",
            "name": "Senior SDET",
            "company": {"name": "Mirantis"},
            "releasedDate": "2026-11-23T10:00:00.000Z",
            "postingUrl": "https://jobs.smartrecruiters.com/Mirantis/sr_1",
            "typeOfEmployment": {"label": "Contract"},
            "location": {"fullLocation": "Dublin, Ireland", "country": "ie", "remote": True, "hybrid": False},
            "jobAd": {"sections": {"jobDescription": {"text": "<p>Remote across Ireland &amp; EU. €500/day.</p>"}}},
        }
        detail_bg = {
            "id": "sr_3",
            "name": "QA Automation Engineer",
            "company": {"name": "Mirantis"},
            "postingUrl": "https://jobs.smartrecruiters.com/Mirantis/sr_3",
            "location": {"fullLocation": "Sofia, Bulgaria", "country": "bg", "remote": True, "hybrid": False},
            "jobAd": {"sections": {"jobDescription": {"text": "<p>Remote role for Sofia team.</p>"}}},
        }

        scraper = SmartRecruitersJobScraper(companies=["Mirantis"])
        with (
            patch.object(scraper, "_fetch_company_postings", return_value=list_items),
            patch.object(scraper, "_fetch_posting_detail", side_effect=[detail_ie, detail_bg]) as mock_detail,
        ):
            jobs = scraper.search_jobs(queries=["QA"], remote_only=True, qa_only=True)

        # Only sr_1 (IE) and sr_3 (BG without blocked code) hit detail; US (sr_2) and Dev (sr_4) skipped locally.
        assert mock_detail.call_count == 2
        # sr_3 domestic Bulgaria without pan-EU marker rejected by detect_workplace_type; sr_1 accepted.
        assert len(jobs) == 1
        assert jobs[0]["id"] == "smartrecruiters_Mirantis_sr_1"
        assert jobs[0]["source"] == "SmartRecruiters"
        assert jobs[0]["workplace_type"] == "remote"
        assert jobs[0]["employment_type"] == "Contract"
        assert jobs[0]["salary"] == "€500/day"

    def test_network_error_returns_empty(self):
        scraper = SmartRecruitersJobScraper(companies=["Mirantis"])
        with patch("smartrecruiters_scraper.urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
            assert scraper.search_jobs(queries=["QA"]) == []
