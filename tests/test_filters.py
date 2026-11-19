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
