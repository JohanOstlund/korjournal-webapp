# Changelog

All notable changes to this project will be documented in this file.

## [1.5.0] - 2025-10-22
### Added
- Förbättrad PDF-rapport: månadssummor per månad och totalsumma.
### Changed
- **Breaking:** PDF-export kräver nu ett år (`/exports/journal.pdf?year=YYYY`).
### Fixed
- Radbrytningar i PDF som kunde dela upp resor mitt i en tabellrad.

## [1.4.0] - 2025-10-15
### Added
- Home Assistant: `/integrations/home-assistant/force-update-and-poll`.
- Endpoints: `/trips/start` och `/trips/finish` med auto-beräkning av distans.
- Förbättrat PAT-/auth-flöde.
### Improved
- Route-skydd, rate limiting, structured logging.

## [1.3.0] - 2025-10-01
- Se `RELEASE_NOTES_v1.3.0.md` i repot.

## [1.0.0] - 2025-09-xx
- Första officiella release.
