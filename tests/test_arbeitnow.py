from unittest.mock import patch, MagicMock
import urllib.error
import json
import pytest
from arbeitnow_scraper import ArbeitnowJobScraper, is_non_english_text
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


    @pytest.mark.parametrize(
        "location",
        [
            "Austria, Germany, Spain, Italy, Hungary, Portugal, Croatia",
            "Germany, Poland, Czech Republic",
            "Poland, Portugal - Remote",
            "Spain, France, Netherlands",
            "Austria / Germany / Switzerland",
        ],
    )
    def test_multi_country_location_without_ireland_rejected(self, location):
        """Remote jobs listing multiple specific countries without Ireland must be rejected."""
        scraper = ArbeitnowJobScraper()
        item = {
            "slug": "ecosio-qa-test-automation-456789",
            "company_name": "ecosio",
            "title": "(Senior) Java Test Automation Engineer",
            "description": "<p>Great remote role for QA engineers.</p>",
            "remote": True,
            "url": "https://www.arbeitnow.com/jobs/companies/ecosio/qa-456789",
            "tags": ["QA", "Java"],
            "location": location,
            "created_at": 1732100000,
        }
        parsed = scraper._parse_single_item(item, remote_only=True)
        assert parsed is None

    @pytest.mark.parametrize(
        "location",
        [
            "Ireland, Germany, Poland",
            "Europe",
            "Remote",
            "Berlin",
            "Worldwide",
            "Germany, Ireland, Spain",
            "Austria, Germany, Europe",
            "",
        ],
    )
    def test_location_with_ireland_or_broad_scope_accepted(self, location):
        """Remote jobs with Ireland, broad scope, or a single city must be accepted."""
        scraper = ArbeitnowJobScraper()
        item = {
            "slug": "acme-qa-engineer-123456",
            "company_name": "Acme Corp",
            "title": "QA Automation Engineer",
            "description": "<p>Remote QA role open across the region.</p>",
            "remote": True,
            "url": "https://www.arbeitnow.com/jobs/companies/acme/qa-123456",
            "tags": ["QA"],
            "location": location,
            "created_at": 1732100000,
        }
        parsed = scraper._parse_single_item(item, remote_only=True)
        assert parsed is not None


class TestNonEnglishTextDetection:
    """Tests for detecting non-English (German, French, Spanish, Polish) job postings."""

    @pytest.mark.parametrize(
        "title,description",
        [
            (
                "Qualitätsmanager/in für App, Website und Filialen-Tests",
                "Wir suchen eine zuverlässige Person mit Erfahrung und Kenntnisse im Bereich Qualitätsmanagement.",
            ),
            (
                "Senior QA Tester (m/w/d)",
                "Für unser Team suchen wir einen erfahrenen QA Tester mit mindestens 3 Jahren Berufserfahrung und Kenntnisse in der Testautomatisierung.",
            ),
            (
                "Testingenieur Softwareentwicklung",
                "Ihre Aufgaben umfassen die Verantwortlich für automatisierte Tests und die Bewerbung neuer Testverfahren.",
            ),
        ],
    )
    def test_german_postings_detected(self, title, description):
        """German-language job postings must be detected as non-English."""
        assert is_non_english_text(title, description) is True

    @pytest.mark.parametrize(
        "title,description",
        [
            (
                "Ingénieur QA Automatisation",
                "Nous recherchons un ingénieur avec expérience pour notre poste. Vos missions incluent les compétences de test.",
            ),
        ],
    )
    def test_french_postings_detected(self, title, description):
        """French-language job postings must be detected as non-English."""
        assert is_non_english_text(title, description) is True

    @pytest.mark.parametrize(
        "title,description",
        [
            (
                "Ingeniero de QA",
                "Buscamos un profesional con experiencia para nuestro puesto. Requisitos incluyen conocimientos y habilidades técnicas.",
            ),
        ],
    )
    def test_spanish_postings_detected(self, title, description):
        """Spanish-language job postings must be detected as non-English."""
        assert is_non_english_text(title, description) is True

    @pytest.mark.parametrize(
        "title,description",
        [
            (
                "Senior QA Automation Engineer",
                "We are looking for a skilled QA engineer with 5 years of experience in test automation. Proficiency in Python and Selenium required.",
            ),
            (
                "SDET - Remote Europe",
                "Join our team to build and maintain test frameworks. This is a fully remote role open to candidates across Europe.",
            ),
            (
                "Test Automation Engineer",
                "Design, implement, and maintain automated test suites for web applications. Experience with Playwright and CI/CD pipelines.",
            ),
        ],
    )
    def test_english_postings_not_blocked(self, title, description):
        """English-language job postings must NOT be detected as non-English."""
        assert is_non_english_text(title, description) is False

    def test_german_title_with_empty_description(self):
        """Short German titles without enough markers should not false-positive."""
        # Only 1 marker ("für") — below threshold of 3
        assert is_non_english_text("QA Test für Berlin", "") is False

    def test_probantica_case_blocked(self):
        """The specific Probantica posting that triggered this filter should be blocked."""
        title = "Qualitätsmanager:in für App-, Website- und Filialen-Tests (m/w/d)"
        desc = (
            "Wir suchen eine zuverlässige Person für unsere Tests. "
            "Deine Aufgaben umfassen die Bewerbung und Erfahrung im Bereich Qualitätsmanagement. "
            "Anforderungen: mindestens 18 Jahre alt, eigenes Smartphone oder Laptop mit Internetzugang."
        )
        assert is_non_english_text(title, desc) is True

    def test_scraper_skips_german_posting(self):
        """Arbeitnow scraper should return None for a German-language posting."""
        scraper = ArbeitnowJobScraper()
        item = {
            "slug": "probantica-qualitatsmanagerin-berlin-74117",
            "company_name": "Probantica",
            "title": "Qualitätsmanager:in für App-, Website- und Filialen-Tests",
            "description": (
                "<p>Wir suchen eine zuverlässige Person für unsere Tests. "
                "Deine Aufgaben umfassen Erfahrung und Kenntnisse im Bereich "
                "Qualitätsmanagement und Anforderungen.</p>"
            ),
            "remote": True,
            "url": "https://www.arbeitnow.com/jobs/companies/probantica/qualitatsmanagerin-berlin-74117",
            "tags": ["Quality Assurance", "Remote"],
            "location": "Berlin",
            "created_at": 1732200000,
        }
        parsed = scraper._parse_single_item(item, remote_only=True)
        assert parsed is None
