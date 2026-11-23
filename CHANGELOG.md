# Changelog

Notable project changes are recorded here.

## [Unreleased]

### Added

- Add a LinkedIn alert reminder to review Easy Apply screening questions and use accurate experience figures. The LinkedIn guest API does not expose employer-added screening questions, so the alert says they may be missing from the card.

### Fixed

- Filter remote contractor listings when an explicit `Locations:` country list excludes Ireland and does not include a broader eligible region such as Europe, the EU, EMEA, or Worldwide. A B2B contract label alone no longer makes a country-restricted role eligible.
- Reject Himalayas and Remotive jobs restricted to another single European country, such as the Netherlands. Himalayas accepts only Ireland, the user's accepted UK scope, or an explicit broad region such as Europe, EMEA, or Worldwide.
