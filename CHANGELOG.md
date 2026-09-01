# Changelog

All notable changes to this project will be documented in this file.

## [2.3.0] - 2026-08-31
### Added
- **Åtkomst utifrån bakom en engångsregistrerad cookie.** `scripts/deploy-access.sh`
  genererar en nginx-vhost med en `/enroll/<hemlighet>`-länk per person; enheter
  på LAN släpps förbi utan cookie och allt annat får 404. Grinden gäller både
  webben och `/api/`, och verifieras av skriptet från 127.0.0.1 (som med flit
  ligger utanför LAN-undantaget). Appens egen inloggning gäller fortfarande —
  grinden är ett lager utanpå den.
- **PWA för iPhone och Android.** Manifest, ikoner (192/512/maskable),
  apple-touch-icon, service worker och offline-sida. Navigeringar går alltid
  till nätet så att en utgången session ger inloggningssidan i stället för ett
  cachat skal; bara hashade byggartefakter och ikoner cachas.
- **Home Assistant kan låsas till ett regnr** (`ha_settings.vehicle_reg`, tomt =
  alla fordon som förut). Gäller anropet en annan bil svarar API:t 409 direkt i
  stället för att lämna ut den kopplade bilens mätarställning — och utan att
  först sova bort 35 sekunder i `force_update`.

### Fixed
- **Appen fungerade inte utifrån.** Webben anropade `http://<LAN-IP>:8080` från
  browsern, vilket är onåbart utanför hemmanätet och dessutom blockeras som
  mixed content på en https-sida. Nu går allt via `/api` på samma origin, med en
  Next-rewrite för den som når Next direkt på LAN. Ingen CORS inblandad längre.
- **nginx skickade `/api`-prefixet vidare till API:t**, som svarar på `/trips`,
  inte `/api/trips` — varje anrop blev 404. `proxy_pass` har nu avslutande slash.
- **Sessionen försvann så fort iOS dödade appen.** Cookien sattes utan `Max-Age`
  och var alltså en ren sessionscookie. Nu följer den JWT:ns livslängd
  (`ACCESS_TOKEN_EXPIRE_MINUTES`, höjd till 30 dagar).
- **`Secure` sattes efter en fast inställning** i stället för efter protokollet:
  antingen kastades cookien över LAN:ets http, eller skickades i klartext.
  Följer nu `X-Forwarded-Proto`.
- **`/auth/logout` raderade inte cookien** när den satts med `Secure`/`SameSite` —
  attributen måste matcha för att webbläsaren ska ta bort den.
- Mätarställningsfältet zoomade in på iOS vid fokus (inputs var 15px, gränsen är 16px).
- Byggets platshållare för API-URL:en ersattes bara i `.js`, inte i förrenderad
  `.html`, så den syntes i klartext tills sidan hydrerat.

### Notes
- `api/app/routes/auth.py` är död kod — den routern inkluderas aldrig, den
  skarpa inloggningen ligger i `main.py`. Rörd men återställd; värd att radera.
- Schemat sköts av `Base.metadata.create_all()`, som skapar tabeller men aldrig
  lägger till kolumner i befintliga. Den nya kolumnen läggs därför till med
  `scripts/migrate-ha-vehicle-reg.sh` (migrering `002` finns för den som kör alembic).

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
