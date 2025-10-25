#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-http://localhost:8000}"
TOKEN="${TOKEN:-}"
[ -z "$TOKEN" ] && { echo "Set TOKEN env var"; exit 1; }

auth=(-H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json")

# Example trips
curl -sX POST "$BASE/trips" "${auth[@]}" -d '{
  "date":"2025-10-20","startTime":"2025-10-20T07:30:00Z","endTime":"2025-10-20T08:20:00Z",
  "startAddress":"Jakobsberg","startCity":"Järfälla","endAddress":"Norrtälje Sjukhus","endCity":"Norrtälje",
  "startOdo":12345,"endOdo":12420,"type":"Tjänst","purpose":"Pendling","driverName":"Johan","carReg":"ABC123"
}'
curl -sX POST "$BASE/trips" "${auth[@]}" -d '{
  "date":"2025-10-21","startTime":"2025-10-21T16:10:00Z","endTime":"2025-10-21T17:00:00Z",
  "startAddress":"Norrtälje Sjukhus","startCity":"Norrtälje","endAddress":"Jakobsberg","endCity":"Järfälla",
  "startOdo":12420,"endOdo":12500,"type":"Privat","purpose":"Hem","driverName":"Johan","carReg":"ABC123"
}'
echo "Seeded example trips."
