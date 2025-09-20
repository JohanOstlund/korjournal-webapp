# Körjournal – Docker-skelett

## Snabbstart

```bash
docker compose up --build
# API:  http://localhost:8080/docs
# Webb: http://localhost:3000
```
## Start/Stop via Home Assistant (odometer)
- Knappen **Starta resa** kallar API:t `/integrations/home-assistant/force-update-and-poll` och fyller starttid + start-odo.
- Knappen **Avsluta resa** kallar samma endpoint, fyller sluttid + slut-odo, räknar km och sparar resan.

> API:t behöver HA-konfig i `docker-compose.yml` (api):
