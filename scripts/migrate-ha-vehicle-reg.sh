#!/usr/bin/env bash
#
# Lägger till ha_settings.vehicle_reg i den databas som API-containern använder.
#
# Varför inte alembic: schemat sköts av Base.metadata.create_all(), som skapar
# tabeller men aldrig lägger till kolumner i befintliga. Databasen har därför
# ingen alembic_version-tabell alls, och alembic ligger inte ens i imagen
# (Dockerfile kopierar bara app/). Migreringen 002 finns i repot för den som
# kör alembic på riktigt; det här skriptet är vägen för den här installationen.
#
# Idempotent — finns kolumnen redan görs ingenting.
#
# MÅSTE köras INNAN den nya API-imagen startas: modellen deklarerar kolumnen,
# så varje SELECT mot ha_settings misslyckas tills den finns.

set -euo pipefail

CONTAINER="${CONTAINER:-korjournal-api}"

docker exec -i "$CONTAINER" python - <<'PY'
import os
from sqlalchemy import create_engine, text

url = os.environ.get("DATABASE_URL")
engine = create_engine(url) if url else __import__("app.db", fromlist=["engine"]).engine

with engine.begin() as c:
    cols = [r[0] for r in c.execute(text("SHOW COLUMNS FROM ha_settings"))]
    if "vehicle_reg" in cols:
        print("vehicle_reg finns redan — inget gjort")
    else:
        c.execute(text("ALTER TABLE ha_settings ADD COLUMN vehicle_reg VARCHAR(64) NULL"))
        print("vehicle_reg tillagd")

with engine.connect() as c:
    print("ha_settings:", ", ".join(r[0] for r in c.execute(text("SHOW COLUMNS FROM ha_settings"))))
PY
