SHELL := /bin/bash
BASE ?= http://localhost:8000
TOKEN ?= your_token_here

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f api

migrate:
	docker exec -it korjournal-api alembic upgrade head

seed-admin:
	@echo "ADMIN: $$ADMIN_USERNAME"
	docker exec -e ADMIN_USERNAME -e ADMIN_PASSWORD korjournal-api \
	  sh -lc 'python /app/scripts/create_admin_and_token.py'

export-year:
	curl -s "$(BASE)/exports/journal.pdf?year=$(YEAR)" -H "Authorization: Bearer $(TOKEN)" -o "journal_$(YEAR).pdf"

purge-trips:
	bash scripts/delete_all_trips.sh

ha-force:
	curl -sX POST "$(BASE)/integrations/home-assistant/force-update-and-poll" -H "Authorization: Bearer $(TOKEN)"
