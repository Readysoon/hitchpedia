# Release-Checkliste

Der vollständige Ablauf, um eine neue hitchpedia-Version über **alle Kanäle** zu veröffentlichen.
Selten nötig — nur bei Änderungen am Skill-Inhalt/den Manifesten. **Neue DB-Einträge brauchen KEINEN Release** (die laufen über die Live-API `POST /contribute`).

> Merksätze:
> - **Version muss höher sein als live** — und zwar auf **beiden** Namespaces: Skill *und* Package.
> - **Erst pushen, dann Package publishen** — der Package-Publish linkt auf den Commit-SHA, der muss auf GitHub liegen.
> - **Kanonisch sind nur** `SKILL.md` · `SKILL.de.md` · `skill.json` im Root. Alles andere generiert `sync.py`.

## 1. Inhalt bearbeiten (SSOT)
Nur die Root-Dateien anfassen:
```
SKILL.md · SKILL.de.md · skill.json
```

## 2. Version bumpen
In `skill.json` die `version` erhöhen. Vorher die Live-Versionen prüfen (neue muss höher sein):
```bash
clawhub inspect known-error-fixes-database   # Skill-Version
clawhub package explore hitchpedia           # Package-Version (Zeile "[Bundle Plugin]")
```

## 3. Sync
Verteilt die SSOT in alle Kopien und stempelt die Version in `plugin.json`, `marketplace.json`, `openclaw.plugin.json`:
```bash
python3 sync.py
```

## 4. Commit + Push (zwingend vor Schritt 6)
```bash
git add -A && git commit -m "Version -> <v>" && git push
git rev-parse HEAD    # SHA für Schritt 6 merken
```

## 5. Skill publishen
```bash
clawhub publish clawhub-skill --slug known-error-fixes-database
```
Falls die CLI zickt → Web-UI: Ordner `~/Desktop/hitchpedia-upload/hitchpedia/` **frisch neu** auswählen (Cache!), Name `known-error-fixes-database`, Version `<v>`.

## 6. Package (Bundle-Plugin) publishen
`openclaw.plugin.json` am Plugin-Root ist Pflicht (liegt schon im Repo, `sync.py` hält die Version aktuell):
```bash
clawhub package publish plugin \
  --family bundle-plugin \
  --name hitchpedia --display-name Hitchpedia \
  --version <v> \
  --host-targets claude-code \
  --source-repo Readysoon/hitchpedia \
  --source-commit <HEAD-SHA aus Schritt 4> \
  --source-ref refs/heads/main \
  --source-path plugin
```

## 7. App deployen — nur wenn App-Code (`app/`, `Dockerfile`, `fly.toml`) geändert wurde
```bash
fly deploy --remote-only --app hitchpedia
```

## 8. Claude-Code-Plugin
Nichts zu tun — der Marketplace *ist* das gepushte Repo (`.claude-plugin/marketplace.json`).
Test: `/plugin marketplace add Readysoon/hitchpedia` → `/plugin install hitchpedia@hitchpedia`.

---

## Verifizieren
```bash
clawhub inspect known-error-fixes-database          # Latest = <v>
clawhub package explore hitchpedia                  # Bundle Plugin = <v>
curl -s https://hitchpedia.fly.dev/ | python3 -m json.tool | grep -A3 stats
```
