# Release Notes – Körjournal v2.3.1

**Releasedatum:** 2026-11-05
**Föregående version:** v2.3.0

---

## 🎉 Översikt

En hotfix: sluttiden på en resa gick inte att rensa från telefonen, så en resa
som avslutats av misstag gick inte att göra pågående igen. Dessutom rättningar
i `deploy-access.sh` som gjorde att skriptet antingen inte startade eller
rapporterade fel resultat.

---

## ✨ Nytt

- **Rensa-knapp vid Sluttid** i redigeringsvyn.

---

## 🐛 Rättat

- **Sluttiden gick inte att rensa från mobilen.** Ett datum- och tidsfält går
  inte att markera och radera på iPhone, och *Nollställ* i datumväljaren
  återställer till fältets ursprungsvärde — inte till tomt — så den gjorde
  ingenting. Rensa och spara gör resan pågående igen.
- **`deploy-access.sh` avbröt med "saknar nginx"** för en vanlig användare,
  eftersom `/usr/sbin` inte finns i PATH. Kontrollen går nu via sudo, som
  resten av skriptet.
- **Grindverifieringen kördes för tidigt** och mätte den gamla
  nginx-konfigurationen, som ännu svarade under en graceful reload. Skriptet
  väntar nu in den nya.
- `http2` flyttat från `listen`-direktivet, så `nginx -t` inte längre visar en
  varning som ser ut som ett fel.
- Värdnamn och registreringsnamn läses från `.env` (`PUBLIC_ORIGIN`,
  `ACCESS_PEOPLE`) i stället för att stå i repot.

---

## ⬆️ Uppgradering

Inga databasändringar.

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Lägg till `ACCESS_PEOPLE` i `.env` (se `.env.example`) innan du kör
`scripts/deploy-access.sh` nästa gång.

---

Se [README.md](README.md) för fullständig dokumentation.
