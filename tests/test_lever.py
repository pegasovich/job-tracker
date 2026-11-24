from unittest.mock import patch, MagicMock
import urllib.error
import pytest
from lever_scraper import LeverJobScraper
from telegram_notifier import TelegramNotifier

SAMPLE_LEVER_RESPONSE = [
    {
        "id": "12345-abcde",
        "text": "Senior QA Automation Engineer",
        "createdAt": 1732000000000,
        "categories": {
            "commitment": "Full-time",
            "location": "Remote - Europe",
            "team": "Quality Engineering",
            "allLocations": ["Remote - Europe"]
        },
        "workplaceType": "remote",
        "hostedUrl": "https://jobs.lever.co/palantir/12345-abcde",
        "applyUrl": "https://jobs.lever.co/palantir/12345-abcde/apply",
        "descriptionPlain": "We are seeking a Senior SDET with Python experience. Salary: $130k - $160k."
    },
    {
        "id": "67890-fghij",
        "text": "Frontend Software Developer",
        "createdAt": 1732000000000,
        "categories": {
            "commitment": "Full-time",
            "location": "London, UK",
            "team": "Frontend",
            "allLocations": ["London, UK"]
        },
        "workplaceType": "onsite",
        "hostedUrl": "https://jobs.lever.co/palantir/67890-fghij",
        "applyUrl": "https://jobs.lever.co/palantir/67890-fghij/apply",
        "descriptionPlain": "React and TypeScript frontend engineer."
    },
    {
        "id": "11111-klmno",
        "text": "QA Lead Engineer",
        "createdAt": 1732000000000,
        "categories": {
            "commitment": "Full-time",
            "location": "Dublin, Ireland",
            "team": "QA",
            "allLocations": ["Dublin, Ireland"]
        },
        "workplaceType": "onsite",
        "hostedUrl": "https://jobs.lever.co/palantir/11111-klmno",
        "applyUrl": "https://jobs.lever.co/palantir/11111-klmno/apply",
        "descriptionPlain": "On-site Dublin QA Lead."
    }
]


class TestLeverScraper:
    """Tests for Lever direct ATS scraper."""

    def test_parse_single_job_extracts_correct_fields(self):
        scraper = LeverJobScraper(companies=["palantir"])
        job_raw = SAMPLE_LEVER_RESPONSE[0]
        parsed = scraper._parse_single_job(job_raw, company_fallback="palantir", remote_only=True)

        assert parsed is not None
        assert parsed["id"] == "lever_palantir_12345-abcde"
        assert parsed["title"] == "Senior QA Automation Engineer"
        assert parsed["company"] == "Palantir"
        assert "Remote" in parsed["location"]
        assert parsed["url"] == "https://jobs.lever.co/palantir/12345-abcde"
        assert "$130k" in parsed["salary"]
        assert "SDET with Python" in parsed["description"]
        assert parsed["source"] == "Lever"
        assert parsed["workplace_type"] == "remote"
        assert parsed["posted_date"] != ""

    def test_search_jobs_remote_only_filters_out_onsite(self):
        scraper = LeverJobScraper(companies=["palantir"])
        with patch.object(scraper, "_fetch_company_jobs", return_value=SAMPLE_LEVER_RESPONSE):
            jobs = scraper.search_jobs(remote_only=True, qa_only=True)
            assert len(jobs) == 1
            assert jobs[0]["title"] == "Senior QA Automation Engineer"

    def test_search_jobs_allows_onsite_when_not_remote_only(self):
        scraper = LeverJobScraper(companies=["palantir"])
        with patch.object(scraper, "_fetch_company_jobs", return_value=SAMPLE_LEVER_RESPONSE):
            jobs = scraper.search_jobs(remote_only=False, qa_only=True)
            assert len(jobs) == 2
            titles = [j["title"] for j in jobs]
            assert "Senior QA Automation Engineer" in titles
            assert "QA Lead Engineer" in titles

    def test_search_jobs_qa_only_filters_out_non_qa_roles(self):
        scraper = LeverJobScraper(companies=["palantir"])
        with patch.object(scraper, "_fetch_company_jobs", return_value=SAMPLE_LEVER_RESPONSE):
            jobs = scraper.search_jobs(remote_only=False, qa_only=True)
            titles = [j["title"] for j in jobs]
            assert "Frontend Software Developer" not in titles

    def test_fetch_company_jobs_network_error(self):
        scraper = LeverJobScraper(companies=["nonexistent"])
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network down")):
            result = scraper._fetch_company_jobs("nonexistent")
            assert result is None

    def test_lever_telegram_badge_formatting(self):
        notifier = TelegramNotifier("fake_token", "fake_chat")
        job = {
            "title": "Senior SDET",
            "company": "Spotify",
            "location": "Remote (Europe)",
            "url": "https://jobs.lever.co/spotify/123",
            "source": "Lever",
            "salary": "€80,000",
        }
        with patch.object(notifier, "send_message", return_value=True) as mock_send:
            sent = notifier.send_job_alert(job, snippet="Test automation framework engineer", workplace_type="remote")
            assert sent is True
            msg = mock_send.call_args[0][0]
            assert "Lever (Direct ATS)" in msg
            assert "Spotify" in msg
            assert "Senior SDET" in msg
            assert "Remote (Удалёнка)" in msg
            assert "Открыть вакансию на Lever" in msg

    def test_search_jobs_rejects_apac_and_hong_kong_lever_postings(self):
        apac_jobs = [
            {
                "id": "binance-hk-1",
                "text": "Web/App Test Engineer",
                "createdAt": 1732000000000,
                "categories": {
                    "commitment": "Full-time: Remote",
                    "location": "Hong Kong",
                    "team": "QA",
                    "allLocations": ["Hong Kong", "Taiwan, Taipei", "Asia"],
                },
                "workplaceType": "remote",
                "country": "HK",
                "hostedUrl": "https://jobs.lever.co/binance/binance-hk-1",
                "descriptionPlain": "Cross-platform Web/App QA automation role.",
            },
            {
                "id": "generic-remote-apac-2",
                "text": "Senior QA Engineer",
                "createdAt": 1732000000000,
                "categories": {
                    "commitment": "Full-time: Remote",
                    "location": "Remote",
                    "team": "QA",
                    "allLocations": ["Remote", "Hong Kong"],
                },
                "workplaceType": "remote",
                "country": "HK",
                "hostedUrl": "https://jobs.lever.co/binance/generic-remote-apac-2",
                "descriptionPlain": "Automation role with Python and Playwright.",
            },
        ]

        scraper = LeverJobScraper(companies=["binance"])
        with patch.object(scraper, "_fetch_company_jobs", return_value=apac_jobs):
            jobs = scraper.search_jobs(remote_only=True, qa_only=True)

        assert jobs == []

    def test_search_jobs_keeps_multi_region_lever_posting_when_europe_or_ireland_listed(self):
        multi_region_job = [
            {
                "id": "multi-eu-1",
                "text": "Senior SDET",
                "createdAt": 1732000000000,
                "categories": {
                    "commitment": "Full-time: Remote",
                    "location": "Hong Kong",
                    "team": "QA",
                    "allLocations": ["Hong Kong", "Remote - Europe"],
                },
                "workplaceType": "remote",
                "country": "HK",
                "hostedUrl": "https://jobs.lever.co/example/multi-eu-1",
                "descriptionPlain": "Pan-European and APAC QA automation team.",
            }
        ]

        scraper = LeverJobScraper(companies=["example"])
        with patch.object(scraper, "_fetch_company_jobs", return_value=multi_region_job):
            jobs = scraper.search_jobs(remote_only=True, qa_only=True)

        assert len(jobs) == 1
        assert jobs[0]["id"] == "lever_example_multi-eu-1"
