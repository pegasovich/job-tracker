from unittest.mock import patch, MagicMock
import urllib.error
import pytest
from main import is_hybrid_nearby
from djinni_scraper import is_djinni_country_eligible


class TestHybridNearbyFilter:
    """Tests the geographical distance filter for hybrid positions around Co. Kerry."""

    @pytest.mark.parametrize(
        "location",
        [
            "Cahersiveen, Co. Kerry",
            "Tralee, Kerry, Ireland",
            "Killarney, County Kerry",
            "Dingle, Co Kerry",
            "Killorglin, Kerry",
            "Kenmare, Ireland",
            "Listowel, Kerry",
        ],
    )
    def test_hybrid_nearby_allowed_locations(self, location):
        """Locations within or near Kerry commuting distance must be accepted."""
        assert is_hybrid_nearby(location) is True

    @pytest.mark.parametrize(
        "location",
        [
            "Dublin, Ireland",
            "Galway, Ireland",
            "Limerick, Ireland",
            "Cork, Ireland",  # Removed in commit be57b75
            "London, United Kingdom",
            "Berlin, Germany",
            "Warsaw, Poland",
        ],
    )
    def test_hybrid_nearby_disallowed_locations(self, location):
        """Locations too far from Cahersiveen must be rejected."""
        assert is_hybrid_nearby(location) is False


class TestLinkedInWorkplaceTypeDetection:
    """Tests workplace type categorization (remote, hybrid, onsite, blocked regions)."""

    @pytest.mark.parametrize(
        "description",
        [
            "We are looking for an SDET based in Poland to join our team.",
            "Candidate must currently be living in Germany.",
            "Residents of United Kingdom only.",
            "Remote work is only permitted within France.",
            "This position is strictly for Latam candidates.",
            "Must be resident in Spain with local tax registration.",
        ],
    )
    def test_domestic_country_restrictions_blocked(self, linkedin_scraper, description):
        """Roles requiring residence in a foreign domestic country must be treated as onsite/blocked."""
        detected = linkedin_scraper.detect_workplace_type(
            title="QA Automation Engineer",
            location="European Union",
            description=description,
        )
        assert detected == "onsite"

    @pytest.mark.parametrize(
        "description",
        [
            "This is a pan-European remote role open for all EU residents.",
            "Remote across Europe with flexible B2B contractor agreement.",
            "Work from anywhere in the EU. Candidates worldwide considered.",
            "Remote in Ireland. Flexible hours.",
        ],
    )
    def test_pan_european_and_ireland_remote_allowed(self, linkedin_scraper, description):
        """Explicit pan-European or Ireland-wide remote roles should be recognized as remote."""
        detected = linkedin_scraper.detect_workplace_type(
            title="Senior QA Engineer",
            location="Europe",
            description=description,
        )
        assert detected == "remote"

    @pytest.mark.parametrize(
        "description",
        [
            "Hybrid setup with 2 days a week in the office.",
            "We offer a flexible hybrid working model.",
            "Split between home and office with core office days.",
            "Candidate must be commutable to our office hub.",
            "We will require you to access the office in Dublin 3 x a week, and 2 days remote working from home.",
            "Expectation of 2 days remote and 3 days in office.",
            "Requires attending the office 2 times a week.",
            "Flexible/remote working, Version 1 is understanding of life events.",
            "Employees work in a hybrid mode across all locations.",
        ],
    )
    def test_hybrid_markers_detected(self, linkedin_scraper, description):
        """Hybrid policies and office-day requirements must be classified as hybrid."""
        detected = linkedin_scraper.detect_workplace_type(
            title="SDET",
            location="Kerry, Ireland",
            description=description,
        )
        assert detected == "hybrid"

    @pytest.mark.parametrize(
        "description",
        [
            "Office-based position in Dublin city centre.",
            "100% on-site presence required at our headquarters.",
            "Relocation required to Frankfurt, Germany. Relocation package provided.",
        ],
    )
    def test_onsite_markers_detected(self, linkedin_scraper, description):
        """Explicit on-site requirements must be classified as onsite."""
        detected = linkedin_scraper.detect_workplace_type(
            title="Automation QA",
            location="Dublin",
            description=description,
        )
        assert detected == "onsite"

    @pytest.mark.parametrize(
        "location",
        [
            "Belfast, Northern Ireland, United Kingdom",
            "London, England, United Kingdom",
            "Manchester, United Kingdom",
            "Edinburgh, Scotland, United Kingdom",
            "Berlin, Germany",
        ],
    )
    def test_uk_and_foreign_cities_treated_as_onsite_for_domestic_remote(self, linkedin_scraper, location):
        """Domestic remote roles in UK/foreign cities without pan-European/Ireland remote markers are onsite."""
        detected = linkedin_scraper.detect_workplace_type(
            title="QA Engineer",
            location=location,
            description="We offer remote work for our UK-based team with great benefits.",
        )
        assert detected == "onsite"


class TestDjinniCountryEligibility:
    """Tests geographic applicant restrictions from Djinni JSON-LD."""

    def test_open_worldwide_when_no_restrictions(self):
        """Jobs with empty applicant countries/regions are open worldwide."""
        job = {"applicant_countries": [], "applicant_regions": []}
        assert is_djinni_country_eligible(job) is True

    def test_allowed_when_europe_or_worldwide_in_regions(self):
        """Jobs allowing Europe or Worldwide regions should accept candidates in Ireland."""
        job = {"applicant_countries": ["PL"], "applicant_regions": ["Europe"]}
        assert is_djinni_country_eligible(job) is True

    def test_allowed_when_ireland_explicitly_included(self):
        """Jobs listing IE/Ireland in country codes must be accepted."""
        job = {"applicant_countries": ["IE", "GB"], "applicant_regions": []}
        assert is_djinni_country_eligible(job) is True

    def test_rejected_when_restricted_to_other_countries(self):
        """Jobs restricted to specific other countries must be rejected for candidate in Ireland."""
        job = {"applicant_countries": ["UA", "PL"], "applicant_regions": []}
        assert is_djinni_country_eligible(job) is False


class TestQATitleFilter:
    """Tests title validation ensuring developer, DevOps, PM, etc. positions are rejected."""

    @pytest.mark.parametrize(
        "title",
        [
            "Software Engineer, Backend - Engineering Operations",
            "Senior Backend Developer",
            "Frontend Engineer (React / TypeScript)",
            "DevOps Engineer",
            "Site Reliability Engineer (SRE)",
            "Full Stack Developer (Java + Vue)",
            "Data Engineer - ETL / Pipelines",
            "Product Manager - Core Platform",
            "Scrum Master / Agile Coach",
            "Engineering Operations Specialist",
            "Java Developer",
            "Cloud Infrastructure Architect",
            "Backend Developer (TDD)",
            "Software Engineer, Backend (Unit Testing)",
            "PLC Automation Engineer",
        ],
    )
    def test_non_qa_titles_rejected(self, linkedin_scraper, title):
        """Pure developer, ops, and management titles must be rejected."""
        assert linkedin_scraper.is_qa_title(title) is False

    @pytest.mark.parametrize(
        "title",
        [
            "QA Analyst",
            "QA Engineer",
            "Senior QA Engineer",
            "SDET",
            "Senior SDET",
            "Software Development Engineer in Test (SDET)",
            "Software Engineer in Test",
            "Test Automation Engineer",
            "Automation QA Lead",
            "Manual QA Tester",
            "Software Tester",
            "Quality Assurance Engineer",
            "Lead Quality Engineer",
            "Performance Test Engineer",
            "QA / Automation Engineer",
            "Backend QA Automation Engineer",
            "AQA Engineer (Python)",
            "SQA Specialist",
            "Automation Engineer",
        ],
    )
    def test_valid_qa_titles_accepted(self, linkedin_scraper, title):
        """Legitimate QA, SDET, Tester, and Quality Engineering titles must be accepted."""
        assert linkedin_scraper.is_qa_title(title) is True


class TestLinkedInRateLimitAndTuning:
    """Tests rate limit 429 backoff handling and configuration limit tuning."""

    @patch("time.sleep", return_value=None)
    @patch("urllib.request.urlopen")
    def test_rate_limit_sets_flag_and_retries(self, mock_urlopen, mock_sleep, linkedin_scraper):
        mock_resp_429 = urllib.error.HTTPError(
            url="http://test", code=429, msg="Too Many Requests", hdrs={}, fp=None
        )
        mock_resp_200 = MagicMock()
        mock_resp_200.status = 200
        mock_resp_200.read.return_value = b"<html>OK</html>"
        mock_resp_200.__enter__.return_value = mock_resp_200

        mock_urlopen.side_effect = [mock_resp_429, mock_resp_200]

        res = linkedin_scraper._make_request("http://test", max_retries=1)
        assert res == "<html>OK</html>"
        assert mock_sleep.called
        assert mock_urlopen.call_count == 2

    @patch("time.sleep", return_value=None)
    @patch("urllib.request.urlopen")
    def test_exhausted_retries_returns_none_and_flags_rate_limit(self, mock_urlopen, mock_sleep, linkedin_scraper):
        mock_resp_429 = urllib.error.HTTPError(
            url="http://test", code=429, msg="Too Many Requests", hdrs={}, fp=None
        )
        mock_urlopen.side_effect = mock_resp_429

        res = linkedin_scraper._make_request("http://test", max_retries=1)
        assert res is None
        assert linkedin_scraper.last_hit_rate_limit is True

    @patch("linkedin_scraper.LinkedInJobScraper._make_request", return_value=None)
    def test_search_jobs_respects_default_limit(self, mock_make_req, linkedin_scraper):
        jobs = linkedin_scraper.search_jobs("SDET")
        assert jobs == []
        assert mock_make_req.called

