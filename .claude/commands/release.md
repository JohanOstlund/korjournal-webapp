---
name: release
description: Sätt ihop en release av körjournalen — changelog, release notes, tagg och GitHub-release. Använd efter att ändringarna deployats och verifierats.
argument-hint: [major|minor|patch] (default: härled från commits sedan förra taggen)
---

Gör en release av körjournalen. Nivå: $ARGUMENTS (default: härled själv).

Ett repo, `ghcr.io/johanostlund/korjournal-{api,web}`. CI bygger images
**bara på `v*`-taggar** (`.github/workflows/docker-publish.yml`) — en push till
`main` publicerar ingenting.

## Versionsnivå

Titta på commits sedan förra taggen och avgör:

```
git log $(git describe --tags --abbrev=0)..HEAD --oneline
```

- **MINOR** — nya användarsynliga funktioner.
- **PATCH** — fixar och förfiningar.
- **MAJOR** — bara vid brytande ändringar i API eller deploy-upplägg.

Är det blandat vinner det största. Föreslå nivån och motivera i en mening;
fråga inte om det är uppenbart.

## Steg

1. **Kontrollera att arbetet är deployat och verifierat.** En release beskriver
   något som redan bevisats fungera. Är det inte deployat, kör `/deploy` först.

   ```
   git status -s
   gh release list --limit 3
   ```

   Arbetsträdet ska vara rent så när som på det du är på väg att committa.

2. **Skriv changelog-posten** överst i `CHANGELOG.md`, under de befintliga
   rubrikerna. Svenska, `### Added` / `### Changed` / `### Fixed` / `### Notes`.

   Skriv vad som var **fel** och varför det spelade roll, inte bara vad som
   ändrades. "Sessionen försvann så fort iOS dödade appen" säger något;
   "uppdaterade cookie-hantering" säger ingenting.

   Har du hittat något som inte är en ändring men som nästa person går på —
   död kod, en fälla i deployen — lägg det under `### Notes`.

3. **Skriv `RELEASE_NOTES_vX.Y.Z.md`** enligt mönstret från befintliga filer:
   rubrik, releasedatum, föregående version, `## 🎉 Översikt`, `## ✨ Nytt`,
   `## 🐛 Rättat`, `## ⬆️ Uppgradering`, och en fot som länkar `README.md`.

   Uppgraderingsavsnittet ska vara körbara kommandon i rätt ordning, inte prosa.
   Nya databaskolumner måste stå **före** de nya images:erna — modellen
   deklarerar dem, så varje query mot tabellen failar tills kolumnen finns.

4. **Uppdatera `README.md`** om releasen ändrar hur appen sätts upp eller
   används. Funktionalitetslistan högst upp är lätt att glömma.

5. **Committa och pusha.** Atomiska commits, en sak per commit — dela upp om
   flera saker ändrats. Meddelandet förklarar *varför*, på engelska (README,
   CHANGELOG och release notes är svenska; commits och kod är engelska).

   ```
   git push origin main
   ```

6. **Tagga och pusha taggen.** Annoterad, med en svensk sammanfattning:

   ```
   git tag -a vX.Y.Z -m "Körjournal vX.Y.Z

   <två-tre stycken: vad releasen ger, vad den rättar, och en rad om
   uppgraderingsordningen om den är känslig>

   Se RELEASE_NOTES_vX.Y.Z.md."
   git push origin vX.Y.Z
   ```

7. **Vänta in CI.** Utan grönt bygge finns inga images att deploya:

   ```
   gh run list --limit 1
   gh run watch <run-id> --exit-status --interval 10
   ```

8. **Publicera GitHub-releasen.**

   ```
   gh release create vX.Y.Z --title "vX.Y.Z – <kort svensk titel>" \
     --notes-file RELEASE_NOTES_vX.Y.Z.md
   ```

   Publicering är utåtriktat och blockeras ofta av auto-mode-klassificeraren.
   Blockeras den — lämna kommandot till Johan med `!`-prefix, kör inte runt det:

   ```
   ! gh release create vX.Y.Z --title "..." --notes-file RELEASE_NOTES_vX.Y.Z.md
   ```

9. **Deploya**, om det inte redan är gjort: `/deploy pull`.

## Att tänka på

- **Repot är publikt.** Inga värdnamn, IP-adresser, familjenamn eller
  hemligheter i det som committas. Deployspecifika värden hör hemma i den
  gitignorerade `.env` (`PUBLIC_ORIGIN`, `ACCESS_PEOPLE`) och läses därifrån.
- **Taggar utan release finns sedan tidigare** (v2.1.1, v2.2.7, v2.2.8). Det är
  inget att städa upp i förbifarten, men lämna inte en ny tagg opublicerad utan
  att säga det.
- **Flytta inte en pushad tagg.** Är den fel, gör en ny patch-release.
