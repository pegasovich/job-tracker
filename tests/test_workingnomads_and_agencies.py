import json
import urllib.error
from unittest.mock import patch

from irish_agencies_scraper import (
    ArcherJobScraper,
    RealTimeJobScraper,
    ReperioJobScraper,
)
from workingnomads_scraper import (
    WorkingNomadsJobScraper,
    is_working_nomads_location_eligible,
)


class TestWorkingNomadsScraper:
    def test_location_eligibility_accepts_global_and_cet_timezones(self):
        assert is_working_nomads_location_eligible("Global") is True
        assert is_working_nomads_location_eligible("Europe") is True
        assert is_working_nomads_location_eligible("Time zone: CET (+/- 3 hours)") is True
        assert is_working_nomads_location_eligible("North America") is False
        assert is_working_nomads_location_eligible("USA only") is False
        assert is_working_nomads_location_eligible("Time zone: CET", "Europe excluding Ireland") is False

    def test_parse_jobs_accepts_cet_qa_and_rejects_language_or_hybrid(self):
        raw_jobs = [
            {
                "url": "https://www.workingnomads.com/job/go/2007928/",
                "title": "Senior QA Automation Engineer",
                "description": "<p>Playwright &amp; CI automation role across CET timezones. B2B contract.</p>",
                "company_name": "Proxify",
                "tags": "playwright,test automation,qa",
                "location": "Time zone: CET (+/- 3 hours)",
                "pub_date": "2026-11-09T08:43:40-05:00",
            },
            {
                "url": "https://www.workingnomads.com/job/go/2033949/",
                "title": "Quality Assurance Rater - Spanish speakers in Spain",
                "description": (
                    "<p>Working as a freelancer with excellent communication skills in Spanish &amp; English. "
                    "Resident in Spain for the last 5 consecutive years.</p>"
                ),
                "company_name": "TELUS Digital",
                "tags": "spanish,content moderation,training,english",
                "location": "Global",
                "pub_date": "2026-11-10T08:00:00Z",
            },
            {
                "url": "https://www.workingnomads.com/job/go/2033999/",
                "title": "SDET",
                "description": "<p>Hybrid working model 2 days in office.</p>",
                "company_name": "HybridCo",
                "tags": "sdet",
                "location": "Europe",
                "pub_date": "2026-11-10T08:00:00Z",
            },
            {
                "url": "https://www.workingnomads.com/job/go/2034000/",
                "title": "Backend Engineer",
                "description": "<p>Python backend.</p>",
                "company_name": "DevCo",
                "tags": "python",
                "location": "Global",
            },
        ]

        jobs = WorkingNomadsJobScraper.parse_jobs(raw_jobs, limit=10)

        assert len(jobs) == 1
        assert jobs[0]["id"] == "workingnomads_2007928"
        assert jobs[0]["source"] == "Working Nomads"
        assert jobs[0]["workplace_type"] == "remote"
        assert "B2B stated" in jobs[0]["employment_type"]
        assert "<p>" not in jobs[0]["description"]

    @patch("workingnomads_scraper.urllib.request.urlopen", side_effect=urllib.error.URLError("timeout"))
    def test_working_nomads_network_error_returns_empty(self, mock_urlopen):
        assert WorkingNomadsJobScraper().search_jobs() == []


class TestReperioJobScraper:
    def test_search_jobs_parses_remote_sdet_and_skips_onsite_and_non_qa(self):
        search_html = """
        <article class="node--type-job">
          <div class="details"><p>QA / Ireland / €500-550</p></div>
          <h3><a href="/job/101/sdet-remote-ireland"><span>SDET (Daily Rate Contract)</span></a></h3>
        </article>
        <article class="node--type-job">
          <div class="details"><p>QA / Dublin / €500-550</p></div>
          <h3><a href="/job/102/qa-onsite-dublin"><span>QA Engineer (Dublin)</span></a></h3>
        </article>
        <article class="node--type-job">
          <div class="details"><p>Dev / Dublin</p></div>
          <h3><a href="/job/103/backend-dev"><span>Senior Backend Developer</span></a></h3>
        </article>
        """
        remote_detail = (
            '<script type="application/ld+json">'
            + json.dumps({
                "@graph": [{
                    "@type": "JobPosting",
                    "identifier": "101",
                    "title": "SDET (Daily Rate Contract)",
                    "employmentType": "Contract",
                    "datePosted": "2026-11-20T10:00:00+00:00",
                    "baseSalary": {"currency": "€", "value": {"minValue": "500", "maxValue": "550", "unitText": "day"}},
                    "jobLocation": {"address": {"addressLocality": "Ireland", "addressCountry": "Ireland"}},
                    "description": "<p>Fully remote in Ireland daily rate contract.</p>",
                }]
            })
            + "</script>"
        )
        onsite_detail = (
            '<script type="application/ld+json">'
            + json.dumps({
                "@graph": [{
                    "@type": "JobPosting",
                    "identifier": "102",
                    "title": "QA Engineer (Dublin)",
                    "employmentType": "Contract",
                    "jobLocation": {"address": {"addressLocality": "Dublin", "addressCountry": "Ireland"}},
                    "description": "<p>Office-based role in Dublin city centre.</p>",
                }]
            })
            + "</script>"
        )

        scraper = ReperioJobScraper()
        with (
            patch.object(scraper, "_fetch_search", return_value=search_html),
            patch.object(scraper, "_fetch_detail", side_effect=[remote_detail, onsite_detail]) as mock_detail,
            patch("irish_agencies_scraper.time.sleep", return_value=None),
        ):
            jobs = scraper.search_jobs(keywords=["SDET"], limit=10)

        assert mock_detail.call_count == 2  # Non-QA card 103 skipped before detail fetch
        assert len(jobs) == 1
        assert jobs[0]["id"] == "reperio_101"
        assert jobs[0]["source"] == "Reperio"
        assert jobs[0]["salary"] == "€500–€550 / day"
        assert jobs[0]["workplace_type"] == "remote"
        assert "Daily Rate" in jobs[0]["employment_type"]


class TestRealTimeJobScraper:
    def test_search_jobs_parses_remote_qa_and_rejects_onsite(self):
        ajax_html = """
        <li class="post-32001 job_listing type-job_listing">
          <a href="https://realtime.jobs/job/qa-automation-remote-32001/">
            <div class="position"><h3>QA Automation Engineer</h3></div>
            <div class="location">Remote, Ireland</div>
            <ul class="meta"><li class="job-type contract">Contract</li><li class="date"><time datetime="2026-11-21"></time></li></ul>
          </a>
        </li>
        <li class="post-32002 job_listing type-job_listing">
          <a href="https://realtime.jobs/job/qa-dublin-32002/">
            <div class="position"><h3>QA Engineer</h3></div>
            <div class="location">Dublin</div>
            <ul class="meta"><li class="job-type contract">Contract</li><li class="date"><time datetime="2026-11-21"></time></li></ul>
          </a>
        </li>
        <li class="post-32003 job_listing type-job_listing">
          <a href="https://realtime.jobs/job/angular-32003/">
            <div class="position"><h3>Angular Developer</h3></div>
            <div class="location">Dublin</div>
          </a>
        </li>
        """
        scraper = RealTimeJobScraper()
        with (
            patch.object(scraper, "_fetch_listings", return_value=ajax_html),
            patch.object(
                scraper,
                "_fetch_detail",
                side_effect=[
                    '<div class="job_description">Fully remote in Ireland. €450 per day contract.</div>',
                    '<div class="job_description">Working from our Dublin office 5 days a week.</div>',
                ],
            ) as mock_detail,
            patch("irish_agencies_scraper.time.sleep", return_value=None),
        ):
            jobs = scraper.search_jobs(keywords=["QA"], limit=10)

        assert mock_detail.call_count == 2  # Non-QA Angular Developer skipped before detail fetch
        assert len(jobs) == 1
        assert jobs[0]["id"] == "realtime_32001"
        assert jobs[0]["source"] == "RealTime"
        assert jobs[0]["salary"] == "€450 per day"
        assert jobs[0]["workplace_type"] == "remote"


class TestArcherJobScraper:
    def test_parse_feed_accepts_remote_eu_contract_and_rejects_onsite(self):
        xml_feed = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0" xmlns:job_listing="https://www.archer.ie">
          <channel>
            <item>
              <title>QA Automation Lead</title>
              <link>https://www.archer.ie/job/qa-automation-lead-1/</link>
              <pubDate>Wed, 18 Nov 2026 12:25:14 +0000</pubDate>
              <description><![CDATA[Work from anywhere in the EU fully remote. €500 per day.]]></description>
              <job_listing:location><![CDATA[Remote]]></job_listing:location>
              <job_listing:job_type><![CDATA[Contract]]></job_listing:job_type>
            </item>
            <item>
              <title>QA Engineer</title>
              <link>https://www.archer.ie/job/qa-dublin-onsite-2/</link>
              <pubDate>Wed, 18 Nov 2026 12:25:14 +0000</pubDate>
              <description><![CDATA[Dublin city centre office-based role.]]></description>
              <job_listing:location><![CDATA[Dublin, Ireland]]></job_listing:location>
              <job_listing:job_type><![CDATA[Permanent]]></job_listing:job_type>
            </item>
            <item>
              <title>Senior DevOps Engineer</title>
              <link>https://www.archer.ie/job/devops-3/</link>
              <description><![CDATA[Work from anywhere in Europe fully remote.]]></description>
              <job_listing:location><![CDATA[Remote]]></job_listing:location>
            </item>
          </channel>
        </rss>
        """

        jobs = ArcherJobScraper.parse_feed(xml_feed, limit=10)

        assert len(jobs) == 1
        assert jobs[0]["id"] == "archer_qa-automation-lead-1"
        assert jobs[0]["source"] == "Archer"
        assert jobs[0]["posted_date"] == "2026-11-18"
        assert jobs[0]["salary"] == "€500 per day"
        assert jobs[0]["workplace_type"] == "remote"
        assert "Daily Rate" in jobs[0]["employment_type"]

    def test_parse_feed_handles_malformed_xml_gracefully(self):
        assert ArcherJobScraper.parse_feed("<rss><broken") == []

    def test_parse_feed_deduplicates_identical_loxo_reposts(self):
        xml_feed = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0" xmlns:job_listing="https://www.archer.ie">
          <channel>
            <item>
              <title>QA Automation Lead</title>
              <link>https://www.archer.ie/job/loxo-306179-qa-automation-lead-1795004714/</link>
              <pubDate>Wed, 18 Nov 2026 12:25:14 +0000</pubDate>
              <description><![CDATA[Work from anywhere in the EU fully remote. Lead AI-driven QA automation.]]></description>
              <job_listing:location><![CDATA[Remote]]></job_listing:location>
              <job_listing:job_type><![CDATA[Contract]]></job_listing:job_type>
            </item>
            <item>
              <title>QA Automation Lead</title>
              <link>https://www.archer.ie/job/loxo-217517-qa-automation-lead-1794910913/</link>
              <pubDate>Tue, 17 Nov 2026 12:25:14 +0000</pubDate>
              <description><![CDATA[Work from anywhere in the EU fully remote. Lead AI-driven QA automation.]]></description>
              <job_listing:location><![CDATA[Remote]]></job_listing:location>
              <job_listing:job_type><![CDATA[Contract]]></job_listing:job_type>
            </item>
            <item>
              <title>QA Automation Lead</title>
              <link>https://www.archer.ie/job/loxo-217517-qa-automation-lead-1794911371/</link>
              <pubDate>Tue, 17 Nov 2026 12:25:14 +0000</pubDate>
              <description><![CDATA[Dublin based, Hybrid working. Lead AI-driven QA automation.]]></description>
              <job_listing:location><![CDATA[Dublin Hybrid, Ireland]]></job_listing:location>
              <job_listing:job_type><![CDATA[Contract]]></job_listing:job_type>
            </item>
          </channel>
        </rss>
        """

        jobs = ArcherJobScraper.parse_feed(xml_feed, limit=10)

        assert [j["id"] for j in jobs] == [
            "archer_loxo-306179-qa-automation-lead-1795004714",
            "archer_loxo-217517-qa-automation-lead-1794911371",
        ]
