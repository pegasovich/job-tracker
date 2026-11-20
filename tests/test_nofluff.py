from unittest.mock import patch, MagicMock
import urllib.error
import pytest
from nofluff_scraper import NoFluffJobScraper
from telegram_notifier import TelegramNotifier


SAMPLE_NFJ_JSON = {
    "postings": [
        {
            "id": "sr-qa-engineer-bamboo-health-Remote-1",
            "name": "Bamboo Health Sp. z o.o.",
            "title": "Sr QA Engineer",
            "technology": "Java",
            "seniority": ["Senior"],
            "url": "sr-qa-engineer-bamboo-health-remote-1",
            "posted": 1732100000000,
            "salary": {
                "from": 3000,
                "to": 4500,
                "type": "b2b",
                "currency": "EUR"
            },
            "tiles": {
                "values": [
                    {"value": "Java"},
                    {"value": "Test automation"},
                    {"value": "pl"}
                ]
            }
        },
        {
            "id": "qa-lead-upvanta-1",
            "name": "Upvanta",
            "title": "QA Lead",
            "technology": "Python",
            "seniority": "Lead",
            "url": "qa-lead-upvanta-1",
            "salary": {
                "from": 5000,
                "type": "permanent",
                "currency": "EUR"
            },
            "tiles": {
                "values": []
            }
        },
        {
            "id": "",
            "name": "Invalid Posting",
            "title": "Ignored Job"
        }
    ]
}


class TestNoFluffScraper:
    """Tests for No Fluff Jobs API scraper."""

    def test_parse_postings_extracts_correct_fields(self):
        scraper = NoFluffJobScraper()
        jobs = scraper.parse_postings(SAMPLE_NFJ_JSON)

        assert len(jobs) == 2

        # First job verification
        job1 = jobs[0]
        assert job1["id"] == "nfj_sr-qa-engineer-bamboo-health-Remote-1"
        assert job1["title"] == "Sr QA Engineer"
        assert job1["company"] == "Bamboo Health Sp. z o.o."
        assert job1["url"] == "https://nofluffjobs.com/job/sr-qa-engineer-bamboo-health-remote-1"
        assert job1["salary"] == "3000–4500 EUR (B2B)"
        assert "Уровень: Senior" in job1["description"]
        assert "Основной стек: Java" in job1["description"]
        assert "Test automation" in job1["description"]
        assert job1["source"] == "NoFluffJobs"
        assert job1["workplace_type"] == "remote"

        # Second job verification (single salary bound, permanent)
        job2 = jobs[1]
        assert job2["id"] == "nfj_qa-lead-upvanta-1"
        assert job2["title"] == "QA Lead"
        assert job2["company"] == "Upvanta"
        assert job2["salary"] == "from 5000 EUR (PERMANENT)"
        assert "Уровень: Lead" in job2["description"]

    def test_parse_postings_handles_empty_or_malformed(self):
        scraper = NoFluffJobScraper()
        assert scraper.parse_postings({}) == []
        assert scraper.parse_postings({"postings": []}) == []

    @patch("urllib.request.urlopen")
    def test_search_jobs_network_success(self, mock_urlopen):
        import json
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(SAMPLE_NFJ_JSON).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        scraper = NoFluffJobScraper()
        jobs = scraper.search_jobs(category="testing", remote_only=True, limit=1)
        assert len(jobs) == 1
        assert jobs[0]["title"] == "Sr QA Engineer"
        assert mock_urlopen.called

    @patch("urllib.request.urlopen")
    def test_search_jobs_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        scraper = NoFluffJobScraper()
        jobs = scraper.search_jobs(category="testing", remote_only=True)
        assert jobs == []

    def test_nofluff_telegram_badge_formatting(self, notifier_configured):
        job = {
            "id": "nfj_sr-qa-engineer-bamboo-health-Remote-1",
            "title": "Sr QA Engineer",
            "company": "Bamboo Health Sp. z o.o.",
            "location": "Remote (Europe / Worldwide)",
            "url": "https://nofluffjobs.com/job/sr-qa-engineer-bamboo-health-remote-1",
            "source": "NoFluffJobs",
            "salary": "3000–4500 EUR (B2B)",
        }
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            notifier_configured.send_job_alert(job)
            assert mock_urlopen.called

            request_obj = mock_urlopen.call_args[0][0]
            import json
            payload_data = json.loads(request_obj.data.decode("utf-8"))
            text = payload_data["text"]
            assert "No Fluff Jobs (nofluffjobs.com)" in text
            assert "3000–4500 EUR (B2B)" in text
