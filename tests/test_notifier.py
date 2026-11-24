from unittest.mock import patch, MagicMock
import urllib.error
import json
import pytest


class TestTelegramNotifier:
    """Tests for Telegram alerting and message generation."""

    def test_unconfigured_notifier(self, notifier_unconfigured):
        """Unconfigured notifier reports is_configured=False and skips sending."""
        assert notifier_unconfigured.is_configured is False
        assert notifier_unconfigured.send_message("Test") is False

    def test_configured_notifier_properties(self, notifier_configured):
        """Properly set bot token and chat ID marks notifier as configured."""
        assert notifier_configured.is_configured is True
        assert notifier_configured.bot_token == "fake_bot_token"
        assert notifier_configured.chat_id == "123456789"

    @patch("urllib.request.urlopen")
    def test_send_message_success(self, mock_urlopen, notifier_configured):
        """Successful 200 HTTP response returns True."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        result = notifier_configured.send_message("Hello from Pytest")
        assert result is True
        assert mock_urlopen.called

    @patch("urllib.request.urlopen")
    def test_send_message_http_error_handled_gracefully(
        self, mock_urlopen, notifier_configured
    ):
        """Network/HTTP exceptions must be caught and return False without raising."""
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        result = notifier_configured.send_message("Test notification")
        assert result is False

    @patch("urllib.request.urlopen")
    def test_send_job_alert_formats_and_escapes(
        self, mock_urlopen, notifier_configured, sample_job
    ):
        """Job alert escapes HTML special characters (<, >, &) in title and company."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        sample_job["title"] = "QA <Lead> & 'SDET'"
        sample_job["company"] = "R&D Co."

        result = notifier_configured.send_job_alert(
            sample_job, snippet="Short snippet description", workplace_type="remote"
        )
        assert result is True

    @patch("urllib.request.urlopen")
    def test_linkedin_alert_reminds_user_to_check_screening_questions(
        self, mock_urlopen, notifier_configured, sample_job
    ):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        assert notifier_configured.send_job_alert(sample_job) is True

        payload = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        assert "Перед Easy Apply" in payload["text"]
        assert "укажи реальный стаж" in payload["text"]
        assert "могут не отображаться в этой карточке" in payload["text"]

    @patch("urllib.request.urlopen")
    def test_non_linkedin_alert_does_not_show_linkedin_screening_reminder(
        self, mock_urlopen, notifier_configured, sample_job
    ):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        sample_job["source"] = "Remote OK"

        assert notifier_configured.send_job_alert(sample_job) is True

        payload = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        assert "Перед Easy Apply" not in payload["text"]

    @pytest.mark.parametrize(
        "source,expected_badge,expected_link",
        [
            ("WorkRemotely.eu", "WorkRemotely.eu", "Открыть вакансию на WorkRemotely.eu"),
            ("TechJobs.ie", "TechJobs.ie", "Открыть вакансию на TechJobs.ie"),
            ("WeWorkRemotely", "WeWorkRemotely", "Открыть вакансию на WeWorkRemotely"),
        ],
    )
    @patch("urllib.request.urlopen")
    def test_source_presentation_matches_new_irish_and_eu_boards(
        self, mock_urlopen, notifier_configured, sample_job, source, expected_badge, expected_link
    ):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        sample_job["source"] = source

        assert notifier_configured.send_job_alert(sample_job) is True

        payload = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        assert expected_badge in payload["text"]
        assert expected_link in payload["text"]
        assert "Перед Easy Apply" not in payload["text"]

    @patch("urllib.request.urlopen")
    def test_boolean_keyword_and_url_query_are_html_escaped_cleanly(
        self, mock_urlopen, notifier_configured, sample_job
    ):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        sample_job["keyword"] = '("SDET" OR "QA Automation") AND ("Contract" OR "B2B")'
        sample_job["url"] = "https://example.com/jobs?id=1&ref=tracker"

        assert notifier_configured.send_job_alert(sample_job) is True

        payload = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        assert "<code>(&quot;SDET&quot; OR &quot;QA Automation&quot;) AND (&quot;Contract&quot; OR &quot;B2B&quot;)</code>" in payload["text"]
        assert 'href="https://example.com/jobs?id=1&amp;ref=tracker"' in payload["text"]
