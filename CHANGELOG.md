# Changelog

Notable project changes are recorded here.

## [Unreleased]

### Added

- Add a LinkedIn alert reminder to review Easy Apply screening questions and use accurate experience figures. The LinkedIn guest API does not expose employer-added screening questions, so the alert says they may be missing from the card.
- Add TechJobs.ie and WorkRemotely.eu as hourly-polled sources. Their parsers keep concise listing metadata, require QA/SDET titles and Ireland-compatible remote scope, and reject explicit hybrid/on-site roles; WorkRemotely.eu is limited to its Ireland contractor/freelance results.
- Widen LinkedIn discovery from the past 24 hours to the past 7 days, retaining newest-first sorting and database deduplication.

### Fixed

- Filter remote contractor listings when an explicit `Locations:` country list excludes Ireland and does not include a broader eligible region such as Europe, the EU, EMEA, or Worldwide. A B2B contract label alone no longer makes a country-restricted role eligible.
- Reject Himalayas and Remotive jobs restricted to another country, including the UK and the Netherlands. Ireland-specific and broad scopes such as Europe, EMEA, or Worldwide remain eligible; UK-only search results are removed from LinkedIn targets.
