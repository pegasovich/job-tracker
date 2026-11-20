from unittest.mock import patch, MagicMock
import urllib.error
import json
import pytest
from justjoin_scraper import JustJoinJobScraper
from telegram_notifier import TelegramNotifier


SAMPLE_JJIT_PAGE = {
    "data": [
        {
            "guid": "45d2ef6c-99c2-453f-b4bf-abc989511429",
            "slug": "act-digital-wcag-manual-tester-warszawa-testing",
            "title": "WCAG Manual Tester",
            "workplaceType": "remote",
            "experienceLevel": "senior",
            "companyName": "act digital",
            "publishedAt": "2026-11-20T15:50:02.6617177Z",
            "employmentTypes": [
                {
                    "from": 10000.0,
                    "to": 20000.0,
                    "currency": "PLN",
                    "type": "b2b"
                },
                {
                    "from": 2200.0,
                    "to": 4500.0,
                    "currency": "EUR",
                    "type": "b2b"
                }
            ],
            "requiredSkills": [
                {"name": "Manual Testing"},
                {"name": "Jira"}
            ]
        },
        {
            "guid": "09b2274b-6fdd-4528-a03a-34d31a764d04",
            "slug": "qa-automation-engineer-remote",
            "title": "QA Automation Engineer",
            "workplaceType": "hybrid",
            "city": "Krakow",
            "experienceLevel": "mid",
            "companyName": "LLInformatics",
            "publishedAt": "2026-11-20T10:00:00.0000000Z",
            "employmentTypes": [],
            "requiredSkills": [
                {"name": "Playwright"}
            ]
        }
    ],
    "meta": {
        "from": 0,
        "totalItems": 2
    }
}


class TestJustJoinScraper:
    """Tests for JustJoin.it candidate API scraper."""

    def test_parse_single_offer_extracts_correct_fields(self):
        scraper = JustJoinJobScraper()
        offer = SAMPLE_JJIT_PAGE["data"][0]
        parsed = scraper._parse_single_offer(offer, currency="EUR")

        assert parsed is not None
        assert parsed["id"] == "jjit_45d2ef6c-99c2-453f-b4bf-abc989511429"
        assert parsed["title"] == "WCAG Manual Tester"
        assert parsed["company"] == "act digital"
        assert parsed["location"] == "Remote (Europe / Worldwide)"
        assert parsed["url"] == "https://justjoin.it/offers/act-digital-wcag-manual-tester-warszawa-testing"
        assert parsed["salary"] == "2200–4500 EUR (B2B)"
        assert "Уровень: Senior" in parsed["description"]
        assert "Manual Testing" in parsed["description"]
        assert parsed["source"] == "JustJoinIT"
        assert parsed["workplace_type"] == "remote"

    def test_search_jobs_remote_only_filters_out_hybrid(self):
        scraper = JustJoinJobScraper()
        with patch.object(scraper, "_fetch_page", return_value=SAMPLE_JJIT_PAGE):
            jobs = scraper.search_jobs(remote_only=True, max_pages=1)
            assert len(jobs) == 1
            assert jobs[0]["title"] == "WCAG Manual Tester"

    def test_search_jobs_allows_hybrid_when_not_remote_only(self):
        scraper = JustJoinJobScraper()
        with patch.object(scraper, "_fetch_page", return_value=SAMPLE_JJIT_PAGE):
            jobs = scraper.search_jobs(remote_only=False, max_pages=1)
            assert len(jobs) == 2
            assert jobs[1]["location"] == "Hybrid (Krakow)"

    @patch("urllib.request.urlopen")
    def test_fetch_page_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Network unreachable")

        scraper = JustJoinJobScraper()
        data = scraper._fetch_page()
        assert data is None

    def test_justjoin_telegram_badge_formatting(self, notifier_configured):
        job = {
            "id": "jjit_45d2ef6c-99c2-453f-b4bf-abc989511429",
            "title": "WCAG Manual Tester",
            "company": "act digital",
            "location": "Remote (Europe / Worldwide)",
            "url": "https://justjoin.it/offers/act-digital-wcag-manual-tester-warszawa-testing",
            "source": "JustJoinIT",
            "salary": "2200–4500 EUR (B2B)",
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
            assert "JustJoin.it" in text
            assert "2200–4500 EUR (B2B)" in text
            assert "Открыть вакансию на JustJoin.it" in text
