# Release Notes – Körjournal v2.3.2

**Releasedatum:** 2026-11-06
**Föregående version:** v2.3.1

---

## 🎉 Översikt

En hotfix: en resa som startats från Home Assistant-knappen och avslutades i
webben fick ingen slutmätarställning. Webben frågade HA om fel regnr, fick nej
och sparade resan med tomt slutvärde utan att säga något.

---

## ✨ Nytt

Inget nytt i den här versionen.

---

## 🐛 Rättat

- **Tom slutmätarställning vid avslut.** Webben skickade regnumret i
  formulärets fält till HA i stället för resans. Startades resan från
  HA-knappen var fältet tomt, och fordonslåset nekade frågan (409). Nu skickas
  resans regnr, och mätarställningen hämtas som den ska.
- **Testknapparna för HA i Inställningar** fick alltid 409 när kopplingen var
  låst till en bil. Nu fungerar de oavsett lås.

> Har du resor som avslutats med tomt slutvärde: öppna dem i redigeringsvyn och
> fyll i slutmätarställningen för hand.

---

## ⬆️ Uppgradering

Inga databasändringar.

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

Se [README.md](README.md) för fullständig dokumentation.
