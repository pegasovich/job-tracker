from unittest.mock import patch, MagicMock
import urllib.error
import pytest
from weworkremotely_scraper import WeWorkRemotelyJobScraper
from telegram_notifier import TelegramNotifier

SAMPLE_WWR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>We Work Remotely</title>
    <link>https://weworkremotely.com</link>
    <description>Remote Jobs</description>
    <item>
      <title>Awesome Tech: Senior QA Automation Engineer ($90-$120/hr)</title>
      <link>https://weworkremotely.com/remote-jobs/awesome-tech-senior-qa-automation-engineer</link>
      <guid>https://weworkremotely.com/remote-jobs/awesome-tech-senior-qa-automation-engineer</guid>
      <pubDate>Fri, 20 Nov 2026 12:00:00 +0000</pubDate>
      <description><![CDATA[<p><strong>Headquarters:</strong> Dublin, Ireland<br />We are hiring a Senior QA Automation Engineer with Python and Playwright skills.</p>]]></description>
    </item>
    <item>
      <title>Dev House: Senior Backend Python Developer</title>
      <link>https://weworkremotely.com/remote-jobs/dev-house-senior-backend-python-developer</link>
      <guid>https://weworkremotely.com/remote-jobs/dev-house-senior-backend-python-developer</guid>
      <pubDate>Fri, 20 Nov 2026 11:00:00 +0000</pubDate>
      <description><![CDATA[<p>Django and FastAPI backend engineer.</p>]]></description>
    </item>
    <item>
      <title>Global QA: Lead Software Test Engineer</title>
      <link>https://weworkremotely.com/remote-jobs/global-qa-lead-software-test-engineer</link>
      <guid>https://weworkremotely.com/remote-jobs/global-qa-lead-software-test-engineer</guid>
      <pubDate>Fri, 20 Nov 2026 10:00:00 +0000</pubDate>
      <description><![CDATA[<p>Must be based in Latin America only. Residents of Brazil only.</p>]]></description>
    </item>
  </channel>
</rss>
"""


class TestWeWorkRemotelyScraper:
    """Tests for WeWorkRemotely RSS scraper."""

    def test_parse_feed_extracts_correct_fields(self):
        scraper = WeWorkRemotelyJobScraper()
        jobs = scraper.parse_feed(SAMPLE_WWR_XML, qa_only=True)

        assert len(jobs) == 1  # 2nd is backend, 3rd is Latam only
        job = jobs[0]
        assert job["title"] == "Senior QA Automation Engineer ($90-$120/hr)"
        assert job["company"] == "Awesome Tech"
        assert job["url"] == "https://weworkremotely.com/remote-jobs/awesome-tech-senior-qa-automation-engineer"
        assert job["id"] == "wwr_awesome-tech-senior-qa-automation-engineer"
        assert "$90-$120/hr" in job["salary"]
        assert "<p>" not in job["description"]
        assert "Playwright" in job["description"]
        assert job["source"] == "WeWorkRemotely"
        assert job["workplace_type"] == "remote"

    def test_parse_feed_filters_non_qa_roles(self):
        scraper = WeWorkRemotelyJobScraper()
        jobs = scraper.parse_feed(SAMPLE_WWR_XML, qa_only=True)
        titles = [j["title"] for j in jobs]
        assert "Senior Backend Python Developer" not in titles

    def test_parse_feed_filters_latam_only_description(self):
        scraper = WeWorkRemotelyJobScraper()
        jobs = scraper.parse_feed(SAMPLE_WWR_XML, qa_only=True)
        titles = [j["title"] for j in jobs]
        assert "Lead Software Test Engineer" not in titles

    def test_parse_feed_malformed_xml(self):
        scraper = WeWorkRemotelyJobScraper()
        jobs = scraper.parse_feed("<not valid xml>", qa_only=True)
        assert jobs == []

    def test_fetch_feed_network_error(self):
        scraper = WeWorkRemotelyJobScraper()
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network down")):
            result = scraper._fetch_feed("https://weworkremotely.com/remote-jobs.rss")
            assert result is None

    def test_search_jobs_deduplicates_by_url(self):
        scraper = WeWorkRemotelyJobScraper(feeds=["https://feed1.rss", "https://feed2.rss"])
        with patch.object(scraper, "_fetch_feed", return_value=SAMPLE_WWR_XML):
            jobs = scraper.search_jobs(remote_only=True, qa_only=True)
            # Both feeds return identical XML, so duplicate URL must be deduped
            assert len(jobs) == 1

    def test_wwr_telegram_badge_formatting(self):
        notifier = TelegramNotifier("fake_token", "fake_chat")
        job = {
            "title": "Software Test Engineer",
            "company": "Remote Works",
            "location": "Remote (Worldwide)",
            "url": "https://weworkremotely.com/remote-jobs/123",
            "source": "WeWorkRemotely",
            "salary": "$100,000",
        }
        with patch.object(notifier, "send_message", return_value=True) as mock_send:
            sent = notifier.send_job_alert(job, snippet="Remote QA SDET testing", workplace_type="remote")
            assert sent is True
            msg = mock_send.call_args[0][0]
            assert "WeWorkRemotely (weworkremotely.com)" in msg
            assert "Remote Works" in msg
            assert "Software Test Engineer" in msg
            assert "Remote (Удалёнка)" in msg
            assert "Открыть вакансию на WeWorkRemotely" in msg
