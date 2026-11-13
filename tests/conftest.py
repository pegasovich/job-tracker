import pytest
from database import JobDatabase
from linkedin_scraper import LinkedInJobScraper
from telegram_notifier import TelegramNotifier


@pytest.fixture
def memory_db(tmp_path):
    """Provides an isolated, clean SQLite database using pytest's tmp_path."""
    db_file = str(tmp_path / "test_jobs.db")
    return JobDatabase(db_file)


@pytest.fixture
def sample_job():
    """Provides a sample job dictionary for database and notification tests."""
    return {
        "id": "linkedin_123456",
        "title": "Senior SDET / QA Automation Engineer",
        "company": "Tech Innovations Ltd",
        "location": "Ireland (Remote)",
        "url": "https://www.linkedin.com/jobs/view/123456",
        "posted_date": "2026-11-13",
        "keyword": "SDET",
        "source": "LinkedIn",
        "workplace_type": "remote",
    }


@pytest.fixture
def linkedin_scraper():
    """Provides a configured LinkedInJobScraper instance."""
    return LinkedInJobScraper(location="Ireland", remote_only=True)


@pytest.fixture
def notifier_unconfigured():
    """Provides an unconfigured TelegramNotifier."""
    return TelegramNotifier(bot_token="", chat_id="")


@pytest.fixture
def notifier_configured():
    """Provides a configured TelegramNotifier with dummy credentials."""
    return TelegramNotifier(bot_token="fake_bot_token", chat_id="123456789")
