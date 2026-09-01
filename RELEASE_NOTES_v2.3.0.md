# Release Notes – Körjournal v2.3.0

**Releasedatum:** 2026-09-01
**Föregående version:** v2.2.10

---

## 🎉 Översikt

Den här versionen gör körjournalen användbar från telefonen när man står vid
bilen: installerbar som app på iPhone och Android, nåbar utifrån bakom en
registreringslänk, och utan att be om lösenord varje gång.

Den rättar också tre saker som gjorde att appen inte gick att använda utanför
hemmanätet över huvud taget, och en som tyst skrev in fel bils mätarställning i
journalen.

---

## ✨ Nytt

### 📱 Installerbar app (PWA)

- Manifest, ikoner (192/512/maskable), apple-touch-icon och service worker.
- **iPhone:** Safari → Dela → *Lägg till på hemskärmen*.
  **Android:** Chrome → menyn → *Installera app*.
- Offline-sida i stället för webbläsarens felsida.
- Innehåll ritas ut i skärmens kanter, med safe-area-marginaler så att
  ingenting hamnar under kameraurtag eller hemknappsstreck.
- Service workern cachar **aldrig** en sida som svar på en navigering. Sidorna
  är inloggningsskyddade och resorna ändras hela tiden — en cachad sida skulle
  kunna visa ett skal som tror att du fortfarande är inloggad. Bara hashade
  byggartefakter och ikoner ligger i cachen.

### 🔐 Åtkomst utifrån bakom en registreringslänk

- `scripts/deploy-access.sh` sätter upp en nginx-vhost där åtkomsten styrs av
  en **engångsregistrerad cookie per person**. Du öppnar din länk en gång på
  telefonen och är därefter inne för gott.
- Enheter på LAN släpps förbi utan cookie. Alla andra får 404 — en portscanner
  ska inte ens se att det finns något här.
- Grinden gäller **både** webben och `/api/`. Bara webben hade varit dekoration:
  frontenden är ett skal över API:t.
- Grinden ersätter inte inloggningen. Appens egen auth (bcrypt, JWT, rate limit
  på 5 försök/minut) gäller fortfarande — det här är ett lager utanpå.
- Skriptet är idempotent, backar upp den befintliga konfigurationen, återställer
  den om `nginx -t` underkänner, och verifierar sedan grinden skarpt innan det
  skriver ut länkarna. `--rotate` ger nya hemligheter och av-registrerar alla.

### 🚗 Home Assistant kan låsas till ett regnr

- Nytt fält **Gäller regnr** under *Inställningar*. Tomt = alla fordon, precis
  som förut.
- Kör du flera bilar där bara en finns i Home Assistant hämtas mätarställningen
  nu bara för den bilen. Övriga fylls i för hand.

---

## 🐛 Rättat

- **Appen fungerade inte utifrån.** Webben anropade `http://<LAN-IP>:8080` från
  browsern — onåbart utanför hemmanätet, och blockerat som mixed content på en
  https-sida. Allt går nu via `/api` på samma origin. Ingen CORS inblandad.
- **nginx skickade `/api`-prefixet vidare till API:t**, som svarar på `/trips`,
  inte `/api/trips`. Varje anrop blev 404.
- **Sessionen försvann så fort iOS dödade appen.** Cookien sattes utan
  `Max-Age` och var alltså en ren sessionscookie. Livslängden följer nu JWT:ns,
  höjd från 24 timmar till 30 dagar.
- **`Secure` följde en fast inställning i stället för protokollet.** Antingen
  kastades cookien över LAN:ets http, eller skickades i klartext. Följer nu
  `X-Forwarded-Proto`.
- **`/auth/logout` raderade inte cookien** när den satts med `Secure`/`SameSite`.
  Attributen måste matcha för att webbläsaren ska ta bort den.
- **Fel bils mätarställning kunde hamna i journalen.** HA-inställningen gäller
  en användare, inte ett fordon, så en resa med den andra bilen fick den
  kopplade bilens siffra — tyst, och efter 35 sekunders väntan i `force_update`.
  Nu svarar API:t 409 direkt, och webben ber om siffran i stället för att
  avsluta resan med 0 km.
- Mätarställningsfältet zoomade in på iOS vid fokus (inputs var 15px, gränsen
  är 16px).
- Byggets platshållare för API-URL:en ersattes bara i `.js`, inte i förrenderad
  `.html`, så den syntes i klartext tills sidan hydrerat.

---

## ⬆️ Uppgradering

Ordningen spelar roll:

```bash
# 1. Databaskolumnen. MÅSTE ligga före den nya API-imagen: modellen
#    deklarerar den, så varje ha_settings-query failar tills den finns.
scripts/migrate-ha-vehicle-reg.sh

# 2. Nya images.
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d

# 3. Grinden. Fram tills den körts fungerar appen inte utifrån — den gamla
#    vhosten 404:ar fortfarande på /api — så det finns inget fönster där
#    appen ligger öppen.
sudo -v && scripts/deploy-access.sh
```

Sätt `PUBLIC_ORIGIN` i `.env` till adressen appen nås på utifrån.

### Två saker att kontrollera

- **Port 3001 och 8080 får inte vara port-forwardade i routern** parallellt med
  443 — då går hela grinden att gå runt.
- **LAN-undantaget bygger på att externa anrop har publika käll-IP:n.** En
  router som source-NAT:ar port forwards får hela internet att se ut som LAN.
  Skriptet tittar i `access.log` och varnar om det inte kan bekräfta motsatsen.

### Noterat på vägen

- `api/app/routes/auth.py` är död kod — den routern inkluderas aldrig, den
  skarpa inloggningen ligger i `main.py`. Värd att radera.
- Schemat sköts av `Base.metadata.create_all()`, som skapar tabeller men aldrig
  lägger till kolumner i befintliga. Databasen har därför ingen
  `alembic_version`-tabell. Migrering `002` finns för den som kör alembic;
  `scripts/migrate-ha-vehicle-reg.sh` är vägen för den här installationen.

---

Se [README.md](README.md) för fullständig dokumentation.
