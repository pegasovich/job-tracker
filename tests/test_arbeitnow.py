from unittest.mock import patch, MagicMock
import urllib.error
import json
import pytest
from arbeitnow_scraper import ArbeitnowJobScraper
from telegram_notifier import TelegramNotifier


SAMPLE_ARBEITNOW_RESPONSE = {
    "data": [
        {
            "slug": "senior-qa-automation-engineer-remote-12345",
            "company_name": "EuroTech Solutions",
            "title": "Senior QA Automation Engineer",
            "description": "<p>We offer a great salary of €75,000 per year. Fully remote anywhere in Europe.</p>",
            "remote": True,
            "url": "https://www.arbeitnow.com/jobs/companies/eurotech/senior-qa-12345",
            "tags": ["QA", "Python", "Automation"],
            "job_types": ["Full-Time"],
            "location": "Berlin",
            "created_at": 1732100000
        },
        {
            "slug": "onsite-manual-tester-munich-67890",
            "company_name": "Munich Auto",
            "title": "Manual Tester",
            "description": "Onsite testing in lab environment.",
            "remote": False,
            "url": "https://www.arbeitnow.com/jobs/companies/munich-auto/tester-67890",
            "tags": ["Testing"],
            "job_types": ["Full-Time"],
            "location": "Munich",
            "created_at": 1732100000
        }
    ]
}


class TestArbeitnowScraper:
    """Tests for Arbeitnow REST API scraper."""

    def test_parse_single_item_extracts_correct_fields(self):
        scraper = ArbeitnowJobScraper()
        item = SAMPLE_ARBEITNOW_RESPONSE["data"][0]
        parsed = scraper._parse_single_item(item, remote_only=True)

        assert parsed is not None
        assert parsed["id"] == "arbeitnow_senior-qa-automation-engineer-remote-12345"
        assert parsed["title"] == "Senior QA Automation Engineer"
        assert parsed["company"] == "EuroTech Solutions"
        assert parsed["location"] == "Remote (Berlin)"
        assert parsed["url"] == "https://www.arbeitnow.com/jobs/companies/eurotech/senior-qa-12345"
        assert parsed["salary"] == "€75,000"
        assert "Python" in parsed["description"]
        assert "<p>" not in parsed["description"]
        assert parsed["source"] == "Arbeitnow"
        assert parsed["workplace_type"] == "remote"

    def test_search_jobs_remote_only_filters_out_onsite(self):
        scraper = ArbeitnowJobScraper()
        with patch.object(scraper, "_fetch_page", return_value=SAMPLE_ARBEITNOW_RESPONSE):
            jobs = scraper.search_jobs(remote_only=True, max_pages=1)
            assert len(jobs) == 1
            assert jobs[0]["title"] == "Senior QA Automation Engineer"

    def test_search_jobs_allows_onsite_when_not_remote_only(self):
        scraper = ArbeitnowJobScraper()
        with patch.object(scraper, "_fetch_page", return_value=SAMPLE_ARBEITNOW_RESPONSE):
            jobs = scraper.search_jobs(remote_only=False, max_pages=1)
            assert len(jobs) == 2
            assert jobs[1]["workplace_type"] == "onsite"
            assert jobs[1]["location"] == "Munich"

    @patch("urllib.request.urlopen")
    def test_fetch_page_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        scraper = ArbeitnowJobScraper()
        result = scraper._fetch_page(page=1)
        assert result is None

    def test_arbeitnow_telegram_badge_formatting(self, notifier_configured):
        job = {
            "id": "arbeitnow_senior-qa-automation-engineer-remote-12345",
            "title": "Senior QA Automation Engineer",
            "company": "EuroTech Solutions",
            "location": "Remote (Berlin)",
            "url": "https://www.arbeitnow.com/jobs/companies/eurotech/senior-qa-12345",
            "source": "Arbeitnow",
            "salary": "€75,000",
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
            assert "Arbeitnow (arbeitnow.com)" in text
            assert "€75,000" in text
            assert "Открыть вакансию на Arbeitnow" in text
