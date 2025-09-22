# Körjournal Webapp

En enkel och stabil körjournal-webapp med stöd för **Home Assistant-integration**.  
Version **1.0.0** (första officiella release).

---

## 🚀 Funktionalitet

### Körjournal
- Skapa resor med:
  - Start- och sluttid
  - Start- och slutadress (inkl. stad)
  - Odometer (mätarställning) vid start och slut
  - Automatiskt beräknad körsträcka (km)
  - Syfte med resa
  - Typ av resa (**Tjänst** eller **Privat**)
  - Förarnamn
  - Bilens registreringsnummer
- Visa resor i en översikt sorterad per datum.
- Begränsning av orimliga körsträckor (max 2000 km per resa).
- Exportera årsfil (YearFile) för bokföring eller rapportering.

### Home Assistant-integration
- Direktkoppling till Home Assistant för att hämta fordonsdata (t.ex. mätarställning).
- Säker kommunikation mellan webappen och din Home Assistant-instans.
- Automatisk uppdatering av fordonsdata vid skapande av ny resa.

---

## 🛠 Tekniskt
- Byggd med **SwiftUI** (frontend) och **API-backend** för lagring.
- JSON-hantering uppdaterad för stabilitet och kompatibilitet.
- Körs via **Docker Compose** för enkel deployment.

---

## 🐞 Kända begränsningar
- Det går inte att **låsa, öppna eller stänga resor**.
- Det går inte att **redigera redan skapade resor**.
- Dessa funktioner kan komma i en framtida release.

---

## 📦 Sammanfattning
- Körjournal med resor (skapande, visning, export).
- Automatiska beräkningar av körsträcka.
- Stöd för resetyper (Tjänst/Privat).
- Export av årsfil.
- Home Assistant-integration för fordonsdata.

---

## 🔧 Installation

1. Klona repot:
   ```bash
   git clone https://github.com/<user>/<repo>.git
   cd <repo>
   ```

2. Skapa en `.env`-fil med nödvändiga variabler (exempel):
   ```env
   API_KEY=din_api_nyckel
   HA_URL=http://homeassistant.local:8123
   HA_TOKEN=din_home_assistant_token
   ```

3. Starta med Docker Compose:
   ```bash
   docker compose up -d
   ```

4. Öppna webappen i din browser:
   ```
   http://localhost:3000
   ```

---

## 📜 Licens
MIT