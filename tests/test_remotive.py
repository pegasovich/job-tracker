from unittest.mock import patch, MagicMock
import urllib.error
import pytest
from remotive_scraper import RemotiveJobScraper, is_remotive_location_eligible
from telegram_notifier import TelegramNotifier

SAMPLE_REMOTIVE_RESPONSE = [
    {
        "id": 1001,
        "url": "https://remotive.com/remote-jobs/qa/senior-qa-engineer-1001",
        "title": "Senior QA Engineer",
        "company_name": "Tech Corp",
        "category": "qa",
        "job_type": "full_time",
        "publication_date": "2026-11-20T12:00:00",
        "candidate_required_location": "Worldwide",
        "salary": "$90k - $120k",
        "description": "<p>We need an experienced <b>QA Engineer</b> to build test automation frameworks.</p>"
    },
    {
        "id": 1002,
        "url": "https://remotive.com/remote-jobs/qa/content-reviewer-1002",
        "title": "Content Reviewer - USA Only",
        "company_name": "Data Inc",
        "category": "qa",
        "job_type": "contract",
        "publication_date": "2026-11-20T11:00:00",
        "candidate_required_location": "USA",
        "salary": "$15/hour",
        "description": "<p>Review user generated content.</p>"
    },
    {
        "id": 1003,
        "url": "https://remotive.com/remote-jobs/qa/lead-sdet-europe-1003",
        "title": "Lead SDET",
        "company_name": "Euro FinTech",
        "category": "qa",
        "job_type": "full_time",
        "publication_date": "2026-11-20T10:00:00",
        "candidate_required_location": "Europe, UK",
        "salary": "€85,000",
        "description": "<p>Lead SDET position for our payments infrastructure.</p>"
    },
    {
        "id": 1004,
        "url": "https://remotive.com/remote-jobs/qa/devops-engineer-1004",
        "title": "Senior DevOps Engineer",
        "company_name": "Cloud Ltd",
        "category": "qa",
        "job_type": "full_time",
        "publication_date": "2026-11-20T09:00:00",
        "candidate_required_location": "Worldwide",
        "salary": "$140k",
        "description": "<p>Kubernetes and AWS platform engineer.</p>"
    }
]


class TestRemotiveScraper:
    """Tests for Remotive job board API scraper."""

    def test_location_eligibility_allowed(self):
        assert is_remotive_location_eligible("Worldwide") is True
        assert is_remotive_location_eligible("Anywhere") is True
        assert is_remotive_location_eligible("Europe") is True
        assert is_remotive_location_eligible("UK, Ireland") is True
        assert is_remotive_location_eligible("EMEA") is True
        assert is_remotive_location_eligible("LATAM, Europe, USA, Canada") is True
        assert is_remotive_location_eligible("") is True
        assert is_remotive_location_eligible("Global") is True

    def test_location_eligibility_blocked(self):
        assert is_remotive_location_eligible("USA") is False
        assert is_remotive_location_eligible("United States") is False
        assert is_remotive_location_eligible("Canada") is False
        assert is_remotive_location_eligible("LATAM") is False
        assert is_remotive_location_eligible("Latin America") is False
        assert is_remotive_location_eligible("India") is False
        assert is_remotive_location_eligible("APAC") is False
        assert is_remotive_location_eligible("Brazil") is False

    def test_parse_single_job_extracts_correct_fields(self):
        scraper = RemotiveJobScraper()
        job_raw = SAMPLE_REMOTIVE_RESPONSE[0]
        parsed = scraper._parse_single_job(job_raw)

        assert parsed is not None
        assert parsed["id"] == "remotive_1001"
        assert parsed["title"] == "Senior QA Engineer"
        assert parsed["company"] == "Tech Corp"
        assert "Remote" in parsed["location"]
        assert parsed["url"] == "https://remotive.com/remote-jobs/qa/senior-qa-engineer-1001"
        assert parsed["salary"] == "$90k - $120k"
        assert "<p>" not in parsed["description"]
        assert "QA Engineer" in parsed["description"]
        assert parsed["source"] == "Remotive"
        assert parsed["workplace_type"] == "remote"

    def test_parse_single_job_filters_ineligible_location(self):
        scraper = RemotiveJobScraper()
        job_raw = SAMPLE_REMOTIVE_RESPONSE[1]  # USA only
        parsed = scraper._parse_single_job(job_raw)
        assert parsed is None

    def test_search_jobs_filters_non_qa_titles(self):
        scraper = RemotiveJobScraper()
        with patch.object(scraper, "_fetch_jobs", return_value=SAMPLE_REMOTIVE_RESPONSE):
            jobs = scraper.search_jobs(qa_only=True)
            titles = [j["title"] for j in jobs]
            assert "Senior QA Engineer" in titles
            assert "Lead SDET" in titles
            # DevOps engineer should be filtered out by is_qa_title
            assert "Senior DevOps Engineer" not in titles
            # USA only job should be filtered out by location
            assert "Content Reviewer - USA Only" not in titles

    def test_fetch_jobs_network_error(self):
        scraper = RemotiveJobScraper()
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network down")):
            result = scraper._fetch_jobs()
            assert result is None

    def test_remotive_telegram_badge_formatting(self):
        notifier = TelegramNotifier("fake_token", "fake_chat")
        job = {
            "title": "QA Automation Engineer",
            "company": "Automate Inc",
            "location": "Remote (Worldwide)",
            "url": "https://remotive.com/remote-jobs/123",
            "source": "Remotive",
            "salary": "$90,000 - $110,000",
        }
        with patch.object(notifier, "send_message", return_value=True) as mock_send:
            sent = notifier.send_job_alert(job, snippet="Remote Python automation testing", workplace_type="remote")
            assert sent is True
            msg = mock_send.call_args[0][0]
            assert "Remotive (remotive.com)" in msg
            assert "Automate Inc" in msg
            assert "QA Automation Engineer" in msg
            assert "Remote (Удалёнка)" in msg
            assert "Открыть вакансию на Remotive" in msg
