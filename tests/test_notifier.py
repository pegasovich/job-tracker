from unittest.mock import patch, MagicMock
import urllib.error
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
