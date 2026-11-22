from unittest.mock import patch, MagicMock
import urllib.error
import json
import pytest
from greenhouse_scraper import GreenhouseJobScraper
from telegram_notifier import TelegramNotifier


SAMPLE_GREENHOUSE_RESPONSE = {
    "jobs": [
        {
            "id": 2969042,
            "title": "Distributed Systems Testing Software Engineer",
            "company_name": "Canonical",
            "location": {"name": "Home Based - EMEA"},
            "content": "<p>We offer $120,000 to $150,000 for top SDETs. Remote across Europe.</p>",
            "absolute_url": "https://job-boards.greenhouse.io/canonical/jobs/2969042",
            "updated_at": "2026-11-20T10:00:00-04:00"
        },
        {
            "id": 8248986,
            "title": "Software Quality Assurance Engineer",
            "company_name": "Canonical",
            "location": {"name": "Office Based - Beijing, China"},
            "content": "<p>Must work onsite in Beijing lab.</p>",
            "absolute_url": "https://job-boards.greenhouse.io/canonical/jobs/8248986",
            "updated_at": "2026-11-20T08:00:00-04:00"
        }
    ]
}


class TestGreenhouseScraper:
    """Tests for Greenhouse direct ATS scraper."""

    def test_parse_single_job_extracts_correct_fields(self):
        scraper = GreenhouseJobScraper(companies=["canonical"])
        job_raw = SAMPLE_GREENHOUSE_RESPONSE["jobs"][0]
        parsed = scraper._parse_single_job(job_raw, company_fallback="canonical", remote_only=True)

        assert parsed is not None
        assert parsed["id"] == "gh_canonical_2969042"
        assert parsed["title"] == "Distributed Systems Testing Software Engineer"
        assert parsed["company"] == "Canonical"
        assert "Remote" in parsed["location"]
        assert parsed["url"] == "https://job-boards.greenhouse.io/canonical/jobs/2969042"
        assert "$120,000" in parsed["salary"]
        assert "<p>" not in parsed["description"]
        assert parsed["source"] == "Greenhouse"
        assert parsed["workplace_type"] == "remote"

    def test_search_jobs_remote_only_filters_out_onsite(self):
        scraper = GreenhouseJobScraper(companies=["canonical"])
        with patch.object(scraper, "_fetch_company_jobs", return_value=SAMPLE_GREENHOUSE_RESPONSE):
            jobs = scraper.search_jobs(remote_only=True)
            assert len(jobs) == 1
            assert jobs[0]["title"] == "Distributed Systems Testing Software Engineer"

    def test_search_jobs_allows_onsite_when_not_remote_only(self):
        scraper = GreenhouseJobScraper(companies=["canonical"])
        with patch.object(scraper, "_fetch_company_jobs", return_value=SAMPLE_GREENHOUSE_RESPONSE):
            jobs = scraper.search_jobs(remote_only=False)
            assert len(jobs) == 2
            assert jobs[1]["workplace_type"] == "onsite"
            assert jobs[1]["location"] == "Office Based - Beijing, China"

    @patch("urllib.request.urlopen")
    def test_fetch_company_jobs_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection reset")

        scraper = GreenhouseJobScraper(companies=["canonical"])
        result = scraper._fetch_company_jobs("canonical")
        assert result is None

    def test_greenhouse_telegram_badge_formatting(self, notifier_configured):
        job = {
            "id": "gh_canonical_2969042",
            "title": "Distributed Systems Testing Software Engineer",
            "company": "Canonical",
            "location": "Remote (Home Based - EMEA)",
            "url": "https://job-boards.greenhouse.io/canonical/jobs/2969042",
            "source": "Greenhouse",
            "salary": "$120,000",
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
            assert "Greenhouse (Direct ATS)" in text
            assert "$120,000" in text
            assert "Открыть вакансию на Greenhouse" in text

    def test_search_jobs_qa_only_filters_out_non_qa_roles(self):
        scraper = GreenhouseJobScraper(companies=["canonical"])
        mixed_response = {
            "jobs": [
                {
                    "id": 101,
                    "title": "Senior Frontend Developer",
                    "location": {"name": "Remote"},
                },
                {
                    "id": 102,
                    "title": "Senior QA Automation Engineer",
                    "location": {"name": "Remote"},
                },
                {
                    "id": 103,
                    "title": "Product Marketing Manager",
                    "location": {"name": "Remote"},
                },
            ]
        }
        with patch.object(scraper, "_fetch_company_jobs", return_value=mixed_response):
            # qa_only=True should only return the QA role
            jobs = scraper.search_jobs(remote_only=True, qa_only=True)
            assert len(jobs) == 1
            assert jobs[0]["title"] == "Senior QA Automation Engineer"

    def test_search_jobs_does_not_exhaust_limit_on_non_qa_roles(self):
        """Non-QA jobs must not consume the limit_per_company quota."""
        scraper = GreenhouseJobScraper(companies=["canonical"])
        # 5 non-QA jobs followed by 1 QA job, limit=2
        jobs_list = [
            {"id": i, "title": f"Software Engineer {i}", "location": {"name": "Remote"}}
            for i in range(5)
        ]
        jobs_list.append(
            {"id": 999, "title": "Lead SDET Engineer", "location": {"name": "Remote"}}
        )
        with patch.object(scraper, "_fetch_company_jobs", return_value={"jobs": jobs_list}):
            jobs = scraper.search_jobs(remote_only=True, limit_per_company=2, qa_only=True)
            assert len(jobs) == 1
            assert jobs[0]["title"] == "Lead SDET Engineer"

    def test_compliance_and_us_remote_roles_filtered_out(self):
        """Jobs like 'Compliance Lead, Testing' and US Remote roles must be rejected."""
        scraper = GreenhouseJobScraper(companies=["affirm"])
        affirm_response = {
            "jobs": [
                {
                    "id": 7994549003,
                    "title": "Compliance Lead, Testing",
                    "company_name": "Affirm",
                    "location": {"name": "Remote US"},
                    "content": "<p>USA base pay range: $130,000 - $180,000. Compliance testing program.</p>",
                },
                {
                    "id": 7994549004,
                    "title": "Lead SDET Engineer",
                    "company_name": "Affirm",
                    "location": {"name": "Remote US"},
                    "content": "<p>USA base pay range: $150,000 - $190,000. US remote only.</p>",
                },
                {
                    "id": 7994549005,
                    "title": "Senior SDET - Automation",
                    "company_name": "Affirm",
                    "location": {"name": "Remote (Europe)"},
                    "content": "<p>Pan-European remote SDET role.</p>",
                },
            ]
        }
        with patch.object(scraper, "_fetch_company_jobs", return_value=affirm_response):
            jobs = scraper.search_jobs(remote_only=True, qa_only=True)
            # Only the European remote SDET role should pass; compliance and US remote must be rejected
            assert len(jobs) == 1
            assert jobs[0]["title"] == "Senior SDET - Automation"
            assert jobs[0]["id"] == "gh_affirm_7994549005"

