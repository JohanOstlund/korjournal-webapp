# Changelog

All notable changes to this project will be documented in this file.

## [2.2.10] - 2026-07-11
### Fixed
- Web-imagen gick inte längre att bygga: `typescript`/`@types` saknades i
  `devDependencies` så Next försökte auto-installera dem under `next build`,
  vilket kraschar med nyare npm ("The \"id\" argument must be of type string").
  Nu explicita devDependencies och package-lock i synk.

## [2.2.9] - 2026-07-11
### Fixed
- `force-update-and-poll` gav 400 mot nyare kia_uvo-versioner som kräver `device_id`:
  ny env-variabel `HA_FORCE_DATA` (JSON) skickas som payload till force-tjänsten.
- Timeout mot HA höjd 20→60 s — kia_uvo:s force_update blockerar tills coordinatorn
  svarat, vilket kunde ta längre än 20 s och ge `ReadTimeout`.
- Efter force-anropet hämtas nu molncachen med `{domain}/update` innan sensorn läses av.
  Nyare kia_uvo uppdaterar inte odometer-entiteten vid force_update (den ber bara bilen
  ladda upp till molnet), vilket gav gammal mätarställning vid avläsning direkt efter resa.

## [2.0.0] - 2026-02-11
### Added
- `globals.css` design system med CSS custom properties och responsiva breakpoints.
- Mobilanpassad layout: kortvy för resor, mallar och användare på skärmar under 768px.
- Viewport meta-tag för korrekt rendering på mobil.
- Sticky navigation med tydlig aktiv-markering.
- Färgkodade knappar: grön (starta), röd (avsluta/ta bort), blå (spara), grå (sekundär).
- Badges för restyp (Tjänst/Privat) och status (Pågående).
- Mobilanpassade kort för reshistorik med datum, km, syfte och adresser.
### Changed
- **Breaking:** All inline-styling ersatt med CSS-klasser. Alla 6 frontend-sidor omskrivna.
- Formulär använder nu konsekvent `.field`/`.form-grid`-mönster med labels ovanför inputs.
- Login-sidan centrerad med kortlayout.
- Inställningar grupperade i separata kort (Home Assistant / Force Update).
- Touch-targets minst 44px höjd (Apple Human Interface Guidelines).
### Fixed
- Decimalinmatning på mobil (komma som decimaltecken gav NaN) — `DecimalInput`-komponent.

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
