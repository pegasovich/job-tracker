from unittest.mock import patch, MagicMock
import urllib.error
import json
import pytest
from adzuna_scraper import AdzunaJobScraper
from telegram_notifier import TelegramNotifier


SAMPLE_ADZUNA_IE_RESPONSE = {
    "results": [
        {
            "id": "4892019283",
            "title": "Senior <strong>QA</strong> Automation Engineer (Remote)",
            "description": "We are seeking a <strong>QA Engineer</strong> with Python and Selenium. Work from home in Ireland.",
            "company": {"display_name": "Dublin Tech Ltd"},
            "location": {"display_name": "Dublin, Ireland"},
            "salary_min": 65000,
            "salary_max": 80000,
            "contract_type": "permanent",
            "redirect_url": "https://www.adzuna.ie/land/ad/4892019283",
            "created": "2026-11-20T12:00:00Z"
        },
        {
            "id": "4892019284",
            "title": "Onsite Manual QA Tester",
            "description": "Requires 5 days onsite at Cork office.",
            "company": {"display_name": "Cork BioLab"},
            "location": {"display_name": "Cork, Ireland"},
            "salary_min": 40000,
            "contract_type": "contract",
            "redirect_url": "https://www.adzuna.ie/land/ad/4892019284",
            "created": "2026-11-20T11:00:00Z"
        }
    ]
}


class TestAdzunaScraper:
    """Tests for Adzuna API scraper."""

    def test_unconfigured_scraper(self):
        scraper = AdzunaJobScraper(app_id="", app_key="")
        assert scraper.is_configured is False
        assert scraper.search_jobs() == []

    def test_configured_scraper_properties(self):
        scraper = AdzunaJobScraper(app_id="test_id", app_key="test_key", countries=["ie"])
        assert scraper.is_configured is True
        assert scraper.app_id == "test_id"
        assert scraper.app_key == "test_key"
        assert scraper.countries == ["ie"]

    def test_search_jobs_remote_only_filters_correctly(self):
        scraper = AdzunaJobScraper(app_id="test_id", app_key="test_key", countries=["ie"])
        with patch.object(scraper, "_fetch_page", return_value=SAMPLE_ADZUNA_IE_RESPONSE):
            jobs = scraper.search_jobs(remote_only=True)
            assert len(jobs) == 1

            job = jobs[0]
            assert job["id"] == "adzuna_4892019283"
            assert job["title"] == "Senior QA Automation Engineer (Remote)"
            assert "<strong>" not in job["title"]
            assert job["company"] == "Dublin Tech Ltd"
            assert "65 000–80 000 € (PERMANENT)" in job["salary"]
            assert job["source"] == "Adzuna"
            assert job["workplace_type"] == "remote"

    def test_search_jobs_allows_onsite_when_not_remote_only(self):
        scraper = AdzunaJobScraper(app_id="test_id", app_key="test_key", countries=["ie"])
        with patch.object(scraper, "_fetch_page", return_value=SAMPLE_ADZUNA_IE_RESPONSE):
            jobs = scraper.search_jobs(remote_only=False)
            assert len(jobs) == 2
            assert jobs[1]["workplace_type"] == "onsite"
            assert "from 40 000 € (CONTRACT)" in jobs[1]["salary"]

    @patch("urllib.request.urlopen")
    def test_fetch_page_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection reset")

        scraper = AdzunaJobScraper(app_id="test_id", app_key="test_key")
        result = scraper._fetch_page(country="ie", page=1, what="QA")
        assert result is None

    def test_adzuna_telegram_badge_formatting(self, notifier_configured):
        job = {
            "id": "adzuna_4892019283",
            "title": "Senior QA Automation Engineer",
            "company": "Dublin Tech Ltd",
            "location": "Remote (Dublin, Ireland)",
            "url": "https://www.adzuna.ie/land/ad/4892019283",
            "source": "Adzuna",
            "salary": "65 000–80 000 €",
            "region": "IE",
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
            assert "Adzuna (api.adzuna.com)" in text
            assert "65 000–80 000 €" in text
            assert "Открыть вакансию на Adzuna" in text
