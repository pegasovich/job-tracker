from unittest.mock import patch, MagicMock
import urllib.error
import json
import pytest
from dou_scraper import DouJobScraper
from telegram_notifier import TelegramNotifier


SAMPLE_DOU_RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>Нові вакансії на ДОУ</title>
    <link>https://jobs.dou.ua/vacancies/</link>
    <description>Вакансії категорії QA</description>
    <item>
      <title>Middle Manual &amp; AI Automation QA в DevCom, Львів, за кордоном, віддалено</title>
      <link>https://jobs.dou.ua/companies/dev-com/vacancies/380650/?utm_source=jobsrss</link>
      <description>&lt;p&gt;&lt;strong&gt;We’re looking for a QA Engineer!&lt;/strong&gt;&lt;/p&gt;</description>
      <pubDate>Fri, 20 Nov 2026 16:52:38 +0200</pubDate>
    </item>
    <item>
      <title>Senior SDET Engineer в FinTech Group, $5000–6000, віддалено</title>
      <link>https://jobs.dou.ua/companies/fintech/vacancies/380999/</link>
      <description>Exciting role with high scale distributed systems.</description>
      <pubDate>Fri, 20 Nov 2026 14:00:00 +0200</pubDate>
    </item>
    <item>
      <title>QA Lead without company marker</title>
      <link>https://jobs.dou.ua/companies/x/vacancies/381111/</link>
      <description>Simple description</description>
      <pubDate>Fri, 20 Nov 2026 12:00:00 +0200</pubDate>
    </item>
  </channel>
</rss>
"""


class TestDouScraper:
    """Tests for DOU.ua RSS scraper."""

    def test_parse_feed_extracts_correct_fields(self):
        scraper = DouJobScraper()
        jobs = scraper.parse_feed(SAMPLE_DOU_RSS)

        assert len(jobs) == 3

        # First job verification
        job1 = jobs[0]
        assert job1["id"] == "dou_380650"
        assert job1["title"] == "Middle Manual & AI Automation QA"
        assert job1["company"] == "DevCom"
        assert "Львів" in job1["location"]
        assert job1["url"] == "https://jobs.dou.ua/companies/dev-com/vacancies/380650/"
        assert job1["source"] == "DOU"
        assert job1["workplace_type"] == "remote"
        assert "We’re looking for a QA Engineer!" in job1["description"]
        assert "<p>" not in job1["description"]

        # Second job with salary
        job2 = jobs[1]
        assert job2["id"] == "dou_380999"
        assert job2["title"] == "Senior SDET Engineer"
        assert job2["company"] == "FinTech Group"
        assert "$5000–6000" in job2["salary"]
        assert "$5000–6000" not in job2["location"]

        # Third job fallback when no " в " delimiter
        job3 = jobs[2]
        assert job3["id"] == "dou_381111"
        assert job3["title"] == "QA Lead without company marker"
        assert job3["company"] == "Unknown Company"

    def test_parse_feed_handles_invalid_xml(self):
        scraper = DouJobScraper()
        assert scraper.parse_feed("not valid xml <<<") == []
        assert scraper.parse_feed("<rss><other></other></rss>") == []

    @patch("urllib.request.urlopen")
    def test_search_jobs_network_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = SAMPLE_DOU_RSS.encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        scraper = DouJobScraper()
        jobs = scraper.search_jobs(category="QA", remote_only=True, limit=2)
        assert len(jobs) == 2
        assert mock_urlopen.called

    @patch("urllib.request.urlopen")
    def test_search_jobs_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection timed out")

        scraper = DouJobScraper()
        jobs = scraper.search_jobs(category="QA", remote_only=True)
        assert jobs == []

    def test_dou_telegram_badge_formatting(self, notifier_configured):
        job = {
            "id": "dou_380650",
            "title": "Middle QA Automation",
            "company": "DevCom",
            "location": "Remote",
            "url": "https://jobs.dou.ua/vacancies/380650/",
            "source": "DOU",
            "salary": "$3000",
        }
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            notifier_configured.send_job_alert(job)
            assert mock_urlopen.called

            # Check sent payload contains DOU badge
            request_obj = mock_urlopen.call_args[0][0]
            payload_data = json.loads(request_obj.data.decode("utf-8"))
            text = payload_data["text"]
            assert "DOU (jobs.dou.ua)" in text
            assert "$3000" in text
            assert "Открыть вакансию на DOU" in text
