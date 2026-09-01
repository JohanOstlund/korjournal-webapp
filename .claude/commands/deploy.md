---
name: deploy
description: Deploya körjournalen — databaskolumner, images och nginx-grinden i rätt ordning. Använd när ändringar ska ut i produktion.
argument-hint: [pull|build] (default: pull — färdiga images från ghcr)
---

Deploya körjournalen. Läge: $ARGUMENTS (default: `pull`).

- **`pull`** — hämta de images CI byggde på senaste taggen. Det normala efter `/release`.
- **`build`** — bygg lokalt från arbetsträdet. För att testa innan en release; publicerar ingenting.

## ⚠️ Compose-anropet

Produktionen kör **båda** filerna överlagrade. Kör alltid:

```
docker compose -f docker-compose.yml -f docker-compose.prod.yml <kommando>
```

`docker-compose.prod.yml` ensam har `DATABASE_URL` bortkommenterad, vilket
betyder SQLite. Kör man bara den byter man tyst ut MariaDB på NAS:en mot en tom
databas i containern — resorna ser ut att vara borta. Verifiera vid tveksamhet:

```
docker inspect korjournal-api --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}'
```

## Steg

1. **Kolla om modellen fått nya kolumner** — före allt annat.

   Schemat sköts av `Base.metadata.create_all()` i `main.py`s lifespan. Den
   skapar tabeller men lägger **aldrig** till kolumner i befintliga. Databasen
   har ingen `alembic_version`-tabell, och alembic ligger inte ens i imagen
   (`api/Dockerfile` kopierar bara `app/`).

   Startar en ny image med en kolumn databasen saknar kraschar varje query mot
   den tabellen. Jämför modellen med databasen:

   ```
   git diff <förra-taggen>..HEAD -- api/app/models.py
   docker exec -i korjournal-api python -c "
   import os; from sqlalchemy import create_engine, text
   e = create_engine(os.environ['DATABASE_URL'])
   with e.connect() as c:
       print([r[0] for r in c.execute(text('SHOW COLUMNS FROM ha_settings'))])"
   ```

   Saknas en kolumn: lägg till den med ett idempotent skript i `scripts/` innan
   du fortsätter (se `scripts/migrate-ha-vehicle-reg.sh` för mönstret), och
   skriv migreringsfilen i `api/alembic/versions/` för formens skull.

   DDL mot produktionsdatabasen blockeras ofta av auto-mode-klassificeraren när
   det körs som ett inline-kommando, men går igenom som ett granskat skript i
   repot. Blockeras det ändå — lämna kommandot till Johan, kör inte runt det.

2. **Hämta eller bygg images.**

   ```
   # pull
   docker compose -f docker-compose.yml -f docker-compose.prod.yml pull

   # build
   docker compose -f docker-compose.yml -f docker-compose.prod.yml build
   ```

3. **Starta om.**

   ```
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
   ```

   `korjournal-api` ska bli `healthy` innan `korjournal-web` startar — det är
   inlagt som `depends_on: condition: service_healthy`.

4. **Röktesta skarpt.** Inte bara att containrarna lever:

   ```
   for p in /login /manifest.webmanifest /sw.js /api/health; do
     printf '%-24s %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3001$p --max-time 10)"
   done
   ```

   Och en inloggning genom `/api` (samma origin), med lösenordet läst ur `.env`
   utan att skrivas ut. Kontrollera att `Set-Cookie` har `Max-Age` — saknas den
   är sessionen tillbaka till att dö när iOS dödar PWA:n:

   ```
   U=$(grep -E '^ADMIN_USERNAME=' .env | cut -d= -f2- | awk '{print $1}')
   P=$(grep -E '^ADMIN_PASSWORD=' .env | cut -d= -f2- | awk '{print $1}')
   curl -s -i -X POST http://127.0.0.1:3001/api/auth/login -H 'Content-Type: application/json' \
     -d "{\"username\":\"$U\",\"password\":\"$P\"}" | grep -i '^set-cookie:' | sed -E 's/(session=)[^;]+/\1<TOKEN>/'
   ```

   Rör ändringen databasen: hämta även `/api/settings` med cookien, så att den
   nya kolumnen bevisligen fungerar mot den skarpa databasen.

5. **nginx-grinden** — bara om `scripts/deploy-access.sh` eller vhosten ändrats.

   Skriptet kräver sudo-lösenord och kan inte köras non-interaktivt. Lämna det
   till Johan med `!`-prefix så hamnar utdatan i samtalet:

   ```
   ! sudo -v && scripts/deploy-access.sh
   ```

   Skriptet backar upp, kör `nginx -t`, återställer vid fel, och verifierar
   sedan grinden från 127.0.0.1 (som med flit ligger utanför LAN-undantaget).
   Läs igenom dess fyra OK/FEL-rader innan du kallar deployen klar.

6. **Kontrollera externt läge.** Appen ska vara nåbar utifrån **bara** bakom
   grinden:

   ```
   HOST=$(sed -n 's|^PUBLIC_ORIGIN=https\?://||p' .env | cut -d'#' -f1 | tr -d ' "')
   curl -sk -o /dev/null -w '%{http_code}\n' --resolve "$HOST:443:127.0.0.1" \
     "https://$HOST/api/health"
   ```

   404 utan cookie är rätt svar. Får du 200 utan cookie är grinden inte uppe —
   säg det rakt ut i stället för att rapportera en lyckad deploy.

## Ordningen spelar roll

Databaskolumn → images → grind. Grinden sist är säkert eftersom den gamla
vhosten 404:ar på `/api` ändå, så det finns inget fönster där appen fungerar
utifrån utan grind. Kolumnen först är däremot inte förhandlingsbart.
