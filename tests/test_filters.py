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
            "Compliance Lead, Testing",
            "Compliance Testing Analyst",
            "Audit Manager - Financial & Controls Testing",
            "SOX Testing Lead",
            "Regulatory Reporting & Testing Analyst",
            "Penetration Tester / Security Consultant",
            "Clinical Testing Coordinator",
            "Materials Testing Technician",
            "A/B Testing Specialist",
            "PAT Testing Engineer",
            "Non-Destructive Testing (NDT) Inspector",
        ],
    )
    def test_non_qa_titles_rejected(self, linkedin_scraper, title):
        """Pure developer, ops, management, compliance, and non-software testing titles must be rejected."""
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


class TestPolishDomesticFiltering:
    """Tests filtering out Polish-domestic job titles and Polish language requirements."""

    @pytest.mark.parametrize(
        "title",
        [
            "Tester Manualny (k/m)",
            "Senior Tester Automatyzujący",
            "QA Engineer (osoba na stanowisku QA Engineera)",
            "Specjalista ds. Testów Penetracyjnych - Pentester MID (k/m)",
            "Senior QA Engineer (m/k)",
            "Inżynier Testów Oprogramowania",
        ],
    )
    def test_polish_domestic_titles_rejected(self, title):
        from config import is_polish_domestic_title
        assert is_polish_domestic_title(title) is True

    @pytest.mark.parametrize(
        "title",
        [
            "Senior QA Engineer",
            "SDET",
            "QA Automation Engineer (Java)",
            "Quality Assurance Analyst",
            "Test Automation Engineer",
            "Lead QA Specialist",
        ],
    )
    def test_international_titles_accepted(self, title):
        from config import is_polish_domestic_title
        assert is_polish_domestic_title(title) is False

    def test_nofluff_polish_language_tile_detection(self):
        from nofluff_scraper import has_polish_language_tile
        # Polish language tile formats
        assert has_polish_language_tile({"values": [{"value": "pl", "type": "jobLanguage"}]}) is True
        assert has_polish_language_tile({"values": [{"value": "pl"}]}) is True
        assert has_polish_language_tile({"values": [{"value": "Polish"}]}) is True
        # English only or tech tiles
        assert has_polish_language_tile({"values": [{"value": "en", "type": "jobLanguage"}]}) is False
        assert has_polish_language_tile({"values": [{"value": "Java"}, {"value": "Selenium"}]}) is False
        assert has_polish_language_tile({}) is False

    def test_justjoin_polish_language_requirement_detection(self):
        from justjoin_scraper import has_polish_language_requirement
        # Polish language requirement formats
        assert has_polish_language_requirement([{"code": "pl", "level": "B2"}]) is True
        assert has_polish_language_requirement([{"code": "en", "level": "C1"}, {"code": "pl", "level": "B2"}]) is True
        # English only
        assert has_polish_language_requirement([{"code": "en", "level": "C1"}]) is False
        assert has_polish_language_requirement([]) is False
        assert has_polish_language_requirement(None) is False


class TestLanguageWhitelistFilter:
    """Tests the language whitelist filter that blocks non-English language requirements."""

    def test_justjoin_german_language_blocked(self):
        """JustJoin offers requiring German should be blocked."""
        from justjoin_scraper import has_non_allowed_language_requirement
        assert has_non_allowed_language_requirement(
            [{"code": "en", "level": "B2"}, {"code": "de", "level": "B2"}],
            allowed_codes=["en", "english"],
        ) is True

    def test_justjoin_french_language_blocked(self):
        """JustJoin offers requiring French should be blocked."""
        from justjoin_scraper import has_non_allowed_language_requirement
        assert has_non_allowed_language_requirement(
            [{"code": "fr", "level": "B2"}],
            allowed_codes=["en", "english"],
        ) is True

    def test_justjoin_english_only_allowed(self):
        """JustJoin offers requiring only English should pass."""
        from justjoin_scraper import has_non_allowed_language_requirement
        assert has_non_allowed_language_requirement(
            [{"code": "en", "level": "C1"}],
            allowed_codes=["en", "english"],
        ) is False

    def test_justjoin_no_languages_allowed(self):
        """JustJoin offers with no language requirements should pass."""
        from justjoin_scraper import has_non_allowed_language_requirement
        assert has_non_allowed_language_requirement([], allowed_codes=["en", "english"]) is False
        assert has_non_allowed_language_requirement(None, allowed_codes=["en", "english"]) is False

    def test_justjoin_polish_blocked_by_whitelist(self):
        """Polish should also be caught by the whitelist filter (not just the legacy blacklist)."""
        from justjoin_scraper import has_non_allowed_language_requirement
        assert has_non_allowed_language_requirement(
            [{"code": "pl", "level": "B2"}],
            allowed_codes=["en", "english"],
        ) is True

    def test_justjoin_spanish_and_english_blocked(self):
        """JustJoin offers requiring Spanish + English: Spanish should trigger block."""
        from justjoin_scraper import has_non_allowed_language_requirement
        assert has_non_allowed_language_requirement(
            [{"code": "en", "level": "B2"}, {"code": "es", "level": "B1"}],
            allowed_codes=["en", "english"],
        ) is True

    def test_nofluff_german_language_tile_blocked(self):
        """NoFluff offers requiring German via tiles should be blocked."""
        from nofluff_scraper import has_non_allowed_language_tile
        assert has_non_allowed_language_tile(
            {"values": [{"value": "de", "type": "jobLanguage"}]},
            allowed_codes=["en", "english"],
        ) is True

    def test_nofluff_english_tile_allowed(self):
        """NoFluff offers requiring only English via tiles should pass."""
        from nofluff_scraper import has_non_allowed_language_tile
        assert has_non_allowed_language_tile(
            {"values": [{"value": "en", "type": "jobLanguage"}]},
            allowed_codes=["en", "english"],
        ) is False

    def test_nofluff_no_language_tiles_allowed(self):
        """NoFluff offers with no language tiles should pass."""
        from nofluff_scraper import has_non_allowed_language_tile
        assert has_non_allowed_language_tile({}, allowed_codes=["en", "english"]) is False
        assert has_non_allowed_language_tile(
            {"values": [{"value": "Java"}, {"value": "Selenium"}]},
            allowed_codes=["en", "english"],
        ) is False

    def test_nofluff_french_language_tile_blocked(self):
        """NoFluff offers requiring French via tiles should be blocked."""
        from nofluff_scraper import has_non_allowed_language_tile
        assert has_non_allowed_language_tile(
            {"values": [{"value": "fr", "type": "jobLanguage"}]},
            allowed_codes=["en", "english"],
        ) is True


class TestGeoBlockedLocations:
    """Tests location blocking against US domestic, Latam, APAC, etc."""

    @pytest.mark.parametrize(
        "location",
        [
            "Remote US",
            "US Remote",
            "Remote, US",
            "Remote (US)",
            "Remote - US",
            "United States",
            "Remote - United States",
            "Remote, USA",
            "San Francisco, CA, US",
            "Austin, TX, US",
            "Remote - California",
            "Remote - Canada",
            "Remote Brazil",
            "India (Remote)",
            "Remote - Latam",
            "Remote - APAC",
        ],
    )
    def test_incompatible_locations_blocked(self, linkedin_scraper, location):
        """Domestic US and other non-European remote locations must be blocked."""
        assert linkedin_scraper.is_location_blocked(location) is True

    @pytest.mark.parametrize(
        "location",
        [
            "Ireland",
            "Remote (Ireland)",
            "Dublin, Ireland",
            "Remote - Europe",
            "Remote - EMEA",
            "Home Based - EMEA",
            "Worldwide",
            "Anywhere",
            "London, UK",
            "Remote",
        ],
    )
    def test_compatible_locations_allowed(self, linkedin_scraper, location):
        """Ireland, Europe, EMEA, UK, and Worldwide locations must not be blocked."""
        assert linkedin_scraper.is_location_blocked(location) is False


class TestDescriptionStopPatterns:
    """Tests detection of domestic US salary disclosures and regional restrictions in description."""

    @pytest.mark.parametrize(
        "text",
        [
            "USA base pay range (CA, WA, NY, NJ, CT) per year: $130,000 - $180,000",
            "base pay range (all other U.S. states) per year: $115,000 - $165,000",
            "This position is strictly for Latam candidates.",
            "Remote work is only permitted within the US.",
            "Candidates must be living in the US.",
            "Work authorization in the United States is required.",
            "For positions based in San Francisco or Los Angeles: Affirm considers qualified applicants.",
        ],
    )
    def test_incompatible_descriptions_blocked(self, linkedin_scraper, text):
        """Descriptions with domestic US salary grids or US/Latam residency rules must be blocked."""
        assert linkedin_scraper.is_description_blocked(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "We offer competitive salary for top SDETs across Europe.",
            "Remote role open to candidates in Ireland and the UK.",
            "Candidates worldwide considered. Flexible B2B contractor contract.",
            "Visa sponsorship is not available for this role. Candidates must have Stamp 4 or EU citizenship.",
        ],
    )
    def test_compatible_descriptions_allowed(self, linkedin_scraper, text):
        """European, Ireland, and global contractor descriptions must not be blocked."""
        assert linkedin_scraper.is_description_blocked(text) is False


