#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-http://localhost:8000}"
TOKEN="${TOKEN:-}"
[ -z "$TOKEN" ] && { echo "Set TOKEN env var"; exit 1; }

ids=$(curl -s "$BASE/trips?limit=1000" -H "Authorization: Bearer $TOKEN" | jq -r '.[].id')
if [ -z "$ids" ]; then echo "No trips"; exit 0; fi
for id in $ids; do
  curl -sX DELETE "$BASE/trips/$id" -H "Authorization: Bearer $TOKEN" >/dev/null
done
echo "Deleted trips: $(echo "$ids" | wc -w)"
