# Körjournal Webapp

En enkel och stabil körjournal med **Home Assistant-integration**.

**Senaste versioner:**  
- v1.5.0 – Förbättrad PDF-rapport, månadssummor & totalsumma, **PDF kräver year** (breaking)  
- v1.4.0 – HA force update/poll-endpoint, `/trips/start` & `/trips/finish`, PAT-förbättringar, rate limiting, structured logging

---

## 🚀 Funktionalitet

- Skapa resor med start-/sluttid, adresser, mätarställning (start/slut) och automatisk distans.
- Går att redigera redan skapade/pågående resor.
- Typer: **Tjänst** eller **Privat**, syfte, förare och registreringsnummer.
- Lista resor sorterade per datum.
- Rimlighetskontroll: max 2000 km/resa.
- **Exportera PDF per år** med månadssummor och totalsumma. **Kräver `?year=`** (sedan v1.5.0).
- Home Assistant-integration inkl. **force-update-and-poll** av mätarställning.

### Kända begränsningar
- Går **inte** att låsa/stänga resor. 

---

## 🧱 Arkitektur

- **API:** FastAPI (Python)
- **DB:** MariaDB (prod) / SQLite (dev)
- **Frontend:** Webklient (`/web`)
- **Reverse proxy:** Valfritt (t.ex. Nginx)
- **Distribuering:** Docker Compose

---

## 📦 Installation (Docker)

1) Klona:
```bash
git clone https://github.com/<user>/<repo>.git
cd <repo>
```

2) Skapa `.env` (se `.env.example` i repot):
```env
# === Timezone ===
TZ=Europe/Stockholm

# === DB (MariaDB) ===
MYSQL_HOST=db
MYSQL_PORT=3306
MYSQL_DATABASE=korjournal
MYSQL_USER=korj
MYSQL_PASSWORD=changeme
MYSQL_ROOT_PASSWORD=rootchangeme

# === API ===
API_PORT=8000
SECRET_KEY=please_change_me_min_64_chars
ACCESS_TOKEN_EXPIRE_MINUTES=43200
CORS_ORIGINS=http://localhost:3000

# === Home Assistant (valfritt) ===
HA_URL=http://homeassistant.local:8123
HA_TOKEN=<ha_long_lived_token>

# === Bootstrap admin (om init-skript används) ===
ADMIN_USERNAME=admin@korjournal.local
ADMIN_PASSWORD=ChangeMe!123
```

3) Starta:
```bash
docker compose up -d
# (om migrations inte körs automatiskt)
docker exec -it korjournal-api alembic upgrade head
```

4) Öppna webben:
```
http://localhost:3000
```

---

## 🔐 Autentisering

- **Endpoint:** `POST /auth/token`
- **Body:**
```json
{"username":"<email>","password":"<password>"}
```
- **Svar:**
```json
{"access_token":"<JWT/PAT>","token_type":"bearer","expires_in":2592000}
```
- **Header i skyddade anrop:** `Authorization: Bearer <token>`

---

## 🧪 API – cURL-exempel

> Lokalt i Docker: `BASE="http://localhost:8000"`

```bash
BASE="http://localhost:8000"
TOKEN="<DIN_TOKEN>"
AUTH="Authorization: Bearer $TOKEN"
CT="Content-Type: application/json"
```

### Hälsa på
```bash
curl -s "$BASE/health"
```

### Logga in
```bash
curl -sX POST "$BASE/auth/token" -H "$CT" \
  -d '{"username":"admin@korjournal.local","password":"ChangeMe!123"}'
```

### Skapa resa (direkt)
```bash
curl -sX POST "$BASE/trips" -H "$AUTH" -H "$CT" -d '{
  "date": "2025-10-25",
  "startTime": "2025-10-25T08:00:00Z",
  "endTime": "2025-10-25T09:15:00Z",
  "startAddress": "Jakobsberg",
  "startCity": "Järfälla",
  "endAddress": "Norrtälje Sjukhus",
  "endCity": "Norrtälje",
  "startOdo": 10000,
  "endOdo": 10085,
  "type": "Tjänst",
  "purpose": "Pendling",
  "driverName": "Johan Ö",
  "carReg": "ABC123"
}'
```

### Starta/avsluta resa
```bash
# Start
curl -sX POST "$BASE/trips/start" -H "$AUTH" -H "$CT" -d '{
  "date": "2025-10-25",
  "startTime": "2025-10-25T08:00:00Z",
  "startAddress": "Jakobsberg",
  "startCity": "Järfälla",
  "startOdo": 10000,
  "type": "Tjänst",
  "purpose": "Pendling",
  "driverName": "Johan Ö",
  "carReg": "ABC123"
}'

# Finish
curl -sX POST "$BASE/trips/finish" -H "$AUTH" -H "$CT" -d '{
  "endTime": "2025-10-25T09:15:00Z",
  "endAddress": "Norrtälje Sjukhus",
  "endCity": "Norrtälje",
  "endOdo": 10085
}'
```

### Lista/Hämta/Radera
```bash
curl -s "$BASE/trips?limit=50&offset=0" -H "$AUTH"
curl -s "$BASE/trips/123" -H "$AUTH"
curl -sX DELETE "$BASE/trips/123" -H "$AUTH"
```

### Exportera PDF **(kräver year)**
```bash
curl -s "$BASE/exports/journal.pdf?year=2025" -H "$AUTH" -o "journal_2025.pdf"
```

### Home Assistant – force update/poll
```bash
curl -sX POST "$BASE/integrations/home-assistant/force-update-and-poll" -H "$AUTH"
```

---

## 🏠 Home Assistant (exempel)

`secrets.yaml`:
```yaml
korjournal_token: <DIN_TOKEN>
korjournal_base: http://localhost:8000
```

`configuration.yaml`:
```yaml
rest_command:
  kj_force_update:
    url: "!secret korjournal_base/integrations/home-assistant/force-update-and-poll"
    method: POST
    headers:
      Authorization: "Bearer !secret korjournal_token"

  kj_create_trip:
    url: "!secret korjournal_base/trips"
    method: POST
    headers:
      Authorization: "Bearer !secret korjournal_token"
      Content-Type: "application/json"
    payload: |
      {
        "date": "{{ now().date() }}",
        "startTime": "{{ now().isoformat() }}",
        "endTime": "{{ (now() + timedelta(hours=1)).isoformat() }}",
        "startAddress": "{{ start_addr }}",
        "startCity": "{{ start_city }}",
        "endAddress": "{{ end_addr }}",
        "endCity": "{{ end_city }}",
        "startOdo": {{ start_odo }},
        "endOdo": {{ end_odo }},
        "type": "Tjänst",
        "purpose": "{{ purpose }}",
        "driverName": "{{ driver }}",
        "carReg": "{{ car_reg }}"
      }
```

---

## ⚙️ Felsökning

- **PDF fel utan `year`** → krävs `?year=`.  
- **401 Unauthorized** → kontrollera `Authorization: Bearer <token>`.  
- **CORS** → lägg till front-origin i `CORS_ORIGINS`.  
- **DB/migration** → `alembic upgrade head`.  
- **HA** → giltig `HA_TOKEN` + nätverksåtkomst från API:t.

---

## 📜 Licens
MIT
