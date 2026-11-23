import json
from unittest.mock import patch

from database import JobDatabase
from config import has_non_allowed_language_requirement
from jobicy_scraper import JobicyJobScraper, is_eligible_for_ireland
from remoteok_scraper import RemoteOKJobScraper
from techjobs_ie_scraper import TechJobsIEScraper
from workremotely_eu_scraper import WorkRemotelyEUScraper


def test_jobicy_requires_an_explicit_eligible_location():
    assert is_eligible_for_ireland("Europe")
    assert is_eligible_for_ireland("Anywhere")
    assert is_eligible_for_ireland("Ireland")
    assert not is_eligible_for_ireland("Remote")
    assert not is_eligible_for_ireland("United States")
    assert not is_eligible_for_ireland("Europe", "Europe excluding Ireland")


def test_jobicy_poll_is_limited_to_once_per_hour(tmp_path):
    db = JobDatabase(str(tmp_path / "jobs.db"))

    assert db.claim_source_poll("jobicy", min_interval_seconds=3600)
    assert not db.claim_source_poll("jobicy", min_interval_seconds=3600)


def test_jobicy_parses_eligible_qa_contract_listing():
    raw_job = {
        "id": 123,
        "jobTitle": "Senior QA Automation Engineer",
        "companyName": "Example Ltd",
        "jobGeo": "Europe",
        "url": "https://jobicy.com/jobs/123",
        "jobType": ["Contract"],
        "jobDescription": "<p>Build automated test suites.</p>",
        "salaryMin": 500,
        "salaryMax": 600,
        "salaryCurrency": "EUR",
        "salaryPeriod": "daily",
    }
    scraper = JobicyJobScraper()
    with patch.object(scraper, "_fetch", return_value=[raw_job]):
        jobs = scraper.search_jobs(tags=["QA"], limit=10)

    assert len(jobs) == 1
    assert jobs[0]["id"] == "jobicy_123"
    assert jobs[0]["location"] == "Remote (Europe)"
    assert jobs[0]["employment_type"] == "Contract; B2B not stated"
    assert jobs[0]["salary"] == "500–600 EUR daily"
    assert "<p>" not in jobs[0]["description"]


def test_jobicy_skips_non_qa_and_country_restricted_listings():
    raw_jobs = [
        {"id": 1, "jobTitle": "Backend Engineer", "jobGeo": "Worldwide"},
        {
            "id": 2,
            "jobTitle": "QA Engineer",
            "jobGeo": "United States",
            "jobDescription": "Remote US only",
        },
    ]
    scraper = JobicyJobScraper()
    with patch.object(scraper, "_fetch", return_value=raw_jobs):
        assert scraper.search_jobs(tags=["QA"], limit=10) == []


def test_foreign_language_tester_roles_are_excluded():
    assert has_non_allowed_language_requirement("Finnish Tech Linguistic Tester")
    assert has_non_allowed_language_requirement("German Language QA Tester")
    assert not has_non_allowed_language_requirement("English Language QA Tester")
    assert has_non_allowed_language_requirement("Fluent in French required")


def test_remoteok_parses_worldwide_qa_role_and_skips_hybrid():
    payload = [
        {"legal": "API notice"},
        {
            "id": "role-1",
            "position": "Senior SDET",
            "company": "Example Ltd",
            "location": "Worldwide",
            "url": "https://remoteok.com/remote-jobs/role-1",
            "description": "Build and maintain automated test suites.",
            "type": "Contract",
            "salary": "$90k",
            "tags": ["qa", "sdet"],
        },
        {
            "id": "role-2",
            "position": "QA Engineer",
            "company": "Office Ltd",
            "location": "Ireland",
            "url": "https://remoteok.com/remote-jobs/role-2",
            "description": "Hybrid work schedule with two days in office.",
        },
    ]

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    with patch("remoteok_scraper.urllib.request.urlopen", return_value=FakeResponse()):
        jobs = RemoteOKJobScraper().search_jobs(tags=["qa", "sdet"], limit=10)

    assert len(jobs) == 1
    assert jobs[0]["id"] == "remoteok_role-1"
    assert jobs[0]["source"] == "Remote OK"
    assert jobs[0]["employment_type"] == "Contract; B2B not stated"


def test_workremotely_eu_accepts_qa_listing_with_visible_ireland_eligible_scope():
    html = """
    <ul><li><a href="/jobs/senior-qa-engineer">Senior QA Engineer</a>
    <span>Example Ltd</span><span>Worldwide</span></li></ul>
    """

    jobs = WorkRemotelyEUScraper.parse_jobs(html)

    assert len(jobs) == 1
    assert jobs[0]["id"] == "workremotely_eu_senior-qa-engineer"
    assert jobs[0]["location"] == "Remote (Ireland eligible; Worldwide)"
    assert jobs[0]["url"] == "https://workremotely.eu/jobs/senior-qa-engineer"
    assert "requirements" in jobs[0]["description"]
    assert "full description" not in jobs[0]["description"]


def test_workremotely_eu_rejects_non_qa_and_ineligible_scopes():
    html = """
    <ul>
      <li><a href="/jobs/backend">Backend Engineer</a><span>Acme</span><span>Worldwide</span></li>
      <li><a href="/jobs/poland-qa">QA Engineer</a><span>Acme</span><span>Poland</span></li>
      <li><a href="/jobs/remote-qa">QA Engineer</a><span>Acme</span><span>Remote</span></li>
      <li><a href="/jobs/europe-ex-ireland">SDET</a><span>Acme</span><span>Europe excluding Ireland</span></li>
    </ul>
    """

    assert WorkRemotelyEUScraper.parse_jobs(html) == []


def test_techjobs_ie_accepts_explicit_remote_within_ireland():
    html = """
    <a href="/jobs/qa-testing/test-automation-engineer-at-cpl-570157">Test Automation Engineer</a>
    <span>CPL · Recruitment agency</span><span>Remote</span>
    <span>Contract</span><span>Galway, Ireland · Remote within Ireland</span>
    <time datetime="2026-11-20T10:00:00Z"></time>
    """

    jobs = TechJobsIEScraper.parse_jobs(html)

    assert len(jobs) == 1
    assert jobs[0]["id"] == "techjobs_ie_test-automation-engineer-at-cpl-570157"
    assert jobs[0]["company"] == "CPL"
    assert jobs[0]["location"] == "Remote (Ireland eligible; TechJobs.ie)"
    assert jobs[0]["employment_type"] == "Contract; B2B not stated"
    assert jobs[0]["posted_date"] == "2026-11-20"
    assert "requirements" in jobs[0]["description"]


def test_techjobs_ie_rejects_hybrid_and_country_only_jobs():
    html = """
    <a href="/jobs/qa-testing/hybrid-ireland">QA Automation Engineer</a>
    <span>Remote in Ireland, hybrid schedule with two office days.</span>
    <a href="/jobs/qa-testing/poland-only">SDET</a>
    <span>Remote within Poland.</span>
    <a href="/jobs/qa-testing/northern-ireland">QA Engineer</a>
    <span>Belfast, Northern Ireland · Remote within Northern Ireland</span>
    <a href="/jobs/qa-testing/europe-ex-ireland">QA Automation Engineer</a>
    <span>Remote throughout Europe except Ireland.</span>
    """

    assert TechJobsIEScraper.parse_jobs(html) == []
