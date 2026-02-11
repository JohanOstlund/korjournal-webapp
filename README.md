# Korjournal Webapp

En fullständig körjournal med **fleranvändarsupport**, **resmallar**, **milersättningsberäkning** och **Home Assistant-integration**.

**Senaste versioner:**
- v2.1.0 – Milersättnings- och reseavdragsberäkning (`/reseavdrag`)
- v2.0.0 – Helt ny responsiv frontend, mobilanpassad design, CSS design system

---

## Funktionalitet

- **Fleranvändarsupport** med admin-roll och användarhantering.
- Skapa resor med start-/sluttid, adresser, mätarställning och automatisk distansberäkning.
- Starta och avsluta resor i två steg (`/trips/start` + `/trips/finish`).
- Typer: **Tjänst** eller **Privat**, med syfte, förare och registreringsnummer.
- **Resmallar** – spara och återanvänd vanliga resor.
- **Milersättning/reseavdrag** – beräkna avdrag enligt Skatteverkets regler (egen bil, förmånsbil el/fossil).
- Exportera **PDF** och **CSV** per år med månadssummor och totalsumma.
- **Home Assistant-integration** med force-update av mätarställning (konfigurerbart per användare).
- **Personal Access Tokens (PAT)** för API-åtkomst från automationer.
- Rate limiting, structured logging och bcrypt-hashade lösenord.

---

## Arkitektur

| Komponent | Teknologi |
|-----------|-----------|
| **API** | FastAPI (Python 3.12) |
| **Frontend** | Next.js 14 + React 18 |
| **Databas** | MariaDB, PostgreSQL eller SQLite |
| **Distribuering** | Docker Compose |

---

## Installation (Docker)

### 1. Klona

```bash
git clone https://github.com/JohanOstlund/korjournal-webapp.git
cd korjournal-webapp
```

### 2. Skapa `.env`

```bash
cp .env.example .env
# Redigera .env med dina värden
```

Se `.env.example` för dokumentation av alla variabler.

### 3. Välj databas och starta

Det finns tre alternativ:

**Extern MariaDB** (t.ex. NAS) – fyll i `NAS_DB_*`-variablerna i `.env`:
```bash
docker compose up -d
```

**PostgreSQL i Docker** – fyll i `DB_USER`/`DB_PASS` i `.env`:
```bash
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d
```

**SQLite** (enklast, bra för test) – kommentera bort `DATABASE_URL` i `docker-compose.yml`:
```bash
docker compose up -d
```

### 4. Öppna webben

```
http://<SERVER_HOST>:3001
```

Admin-användare skapas automatiskt vid första start utifrån `ADMIN_USERNAME` / `ADMIN_PASSWORD` i `.env`.

---

## Autentisering

### Logga in (cookie-baserat, används av webben)
```bash
curl -sX POST "$BASE/auth/login" -H "$CT" \
  -d '{"username":"admin","password":"ditt_lösenord"}'
```

### Hämta token (JWT, för API-anrop)
```bash
curl -sX POST "$BASE/auth/token" -H "$CT" \
  -d '{"username":"admin","password":"ditt_lösenord"}'
```

**Svar:**
```json
{"access_token":"<JWT>","token_type":"bearer","expires_in":86400}
```

**Skyddade anrop:** `Authorization: Bearer <token>`

---

## API-översikt

> `BASE="http://localhost:8080"` (default API-port)

```bash
TOKEN="<DIN_TOKEN>"
AUTH="Authorization: Bearer $TOKEN"
CT="Content-Type: application/json"
```

### Resor

| Metod | Endpoint | Beskrivning |
|-------|----------|-------------|
| `POST` | `/trips` | Skapa resa (komplett) |
| `POST` | `/trips/start` | Starta resa |
| `POST` | `/trips/finish` | Avsluta pågående resa |
| `GET` | `/trips` | Lista resor (`?limit=&offset=&year=&month=`) |
| `PUT` | `/trips/{id}` | Uppdatera resa |
| `DELETE` | `/trips/{id}` | Ta bort resa |

### Mallar

| Metod | Endpoint | Beskrivning |
|-------|----------|-------------|
| `GET` | `/templates` | Lista mallar |
| `POST` | `/templates` | Skapa mall |
| `PUT` | `/templates/{id}` | Uppdatera mall |
| `DELETE` | `/templates/{id}` | Ta bort mall |

### Export

| Metod | Endpoint | Beskrivning |
|-------|----------|-------------|
| `GET` | `/exports/journal.pdf?year=2025` | PDF-rapport |
| `GET` | `/exports/journal.csv?year=2025` | CSV-export |

### Admin

| Metod | Endpoint | Beskrivning |
|-------|----------|-------------|
| `GET` | `/admin/users` | Lista användare |
| `POST` | `/admin/users` | Skapa användare |
| `DELETE` | `/admin/users/{id}` | Ta bort användare |

### Home Assistant

| Metod | Endpoint | Beskrivning |
|-------|----------|-------------|
| `POST` | `/integrations/home-assistant/poll` | Hämta mätarställning |
| `POST` | `/integrations/home-assistant/force-update-and-poll` | Force update + hämta |
| `GET` | `/integrations/home-assistant/settings` | Hämta HA-inställningar |
| `PUT` | `/integrations/home-assistant/settings` | Uppdatera HA-inställningar |

### Övrigt

| Metod | Endpoint | Beskrivning |
|-------|----------|-------------|
| `GET` | `/health` | Hälsokontroll (inkl. DB) |
| `POST` | `/auth/change-password` | Byt lösenord |
| `GET` | `/auth/me` | Aktuell användare |

---

## Home Assistant (exempel)

`secrets.yaml`:
```yaml
korjournal_token: <DIN_PAT_TOKEN>
korjournal_base: http://<SERVER_HOST>:8080
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
        "endAddress": "{{ end_addr }}",
        "startOdo": {{ start_odo }},
        "endOdo": {{ end_odo }},
        "type": "Tjänst",
        "purpose": "{{ purpose }}",
        "driverName": "{{ driver }}",
        "carReg": "{{ car_reg }}"
      }
```

HA-inställningar (URL, token, odometer-entity) kan konfigureras per användare i webbens **Settings**-sida.

---

## Felsökning

- **401 Unauthorized** – kontrollera `Authorization: Bearer <token>`.
- **CORS-fel** – lägg till frontend-origin i `CORS_ORIGINS` i `.env`.
- **DB/migration** – `docker exec -it korjournal-api alembic upgrade head`.
- **HA-integration** – kontrollera `HA_TOKEN` och nätverksåtkomst från API-containern.
- **PDF kräver year** – `/exports/journal.pdf?year=2025`.

---

## Licens

MIT
