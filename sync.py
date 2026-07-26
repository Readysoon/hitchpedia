#!/usr/bin/env python3
"""SSOT-Sync — gegen Redundanz.

Kanonisch (Single Source of Truth) sind AUSSCHLIESSLICH im Repo-Root:
    SKILL.md · SKILL.de.md · skill.json

Alles andere ist eine *generierte* Kopie und darf NIE von Hand gepflegt werden.
Dieses Script schreibt die kanonischen Dateien in alle Ziele und stempelt die
skill.json-Version in die Plugin-Manifeste — so gibt es die Beschreibung, die
Skill-Texte und die Versionsnummer an genau einer Stelle zum Bearbeiten.

Ziele:
  - clawhub-skill/                      (ClawHub-Skill-Publish:  clawhub publish clawhub-skill)
  - ~/Desktop/hitchpedia-upload/...     (Web-UI-Upload)
  - plugin/skills/hitchpedia/           (Claude-Code-/OpenClaw-Plugin, Skill-Inhalt)
  - plugin/.claude-plugin/plugin.json   (nur Version gestempelt)
  - .claude-plugin/marketplace.json     (nur Version gestempelt)

Die laufende API (app/controllers/info.py) liest die Root-Dateien ohnehin direkt
und braucht keinen Sync.

Aufruf:  python3 sync.py
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILL_FILES = ["SKILL.md", "SKILL.de.md"]

VERSION = json.loads((ROOT / "skill.json").read_text(encoding="utf-8"))["version"]

# Ziele, die SKILL-Dateien + skill.json bekommen
FULL_TARGETS = [
    ROOT / "clawhub-skill",
    Path.home() / "Desktop" / "hitchpedia-upload" / "hitchpedia",
]
# Ziele, die nur die SKILL-Dateien bekommen (Plugin nutzt plugin.json statt skill.json)
SKILL_ONLY_TARGETS = [
    ROOT / "plugin" / "skills" / "hitchpedia",
]


def _copy(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def sync_files():
    n = 0
    for d in FULL_TARGETS + SKILL_ONLY_TARGETS:
        for f in SKILL_FILES:
            _copy(ROOT / f, d / f)
            n += 1
    for d in FULL_TARGETS:
        _copy(ROOT / "skill.json", d / "skill.json")
        n += 1
    return n


def stamp_version():
    """Version aus skill.json in plugin.json + marketplace.json spiegeln."""
    pj = ROOT / "plugin" / ".claude-plugin" / "plugin.json"
    data = json.loads(pj.read_text(encoding="utf-8"))
    data["version"] = VERSION
    pj.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    mp = ROOT / ".claude-plugin" / "marketplace.json"
    data = json.loads(mp.read_text(encoding="utf-8"))
    for pl in data.get("plugins", []):
        if pl.get("name") == "hitchpedia":
            pl["version"] = VERSION
    mp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # OpenClaw-Manifest (fürs ClawHub-bundle-plugin-Publish)
    oc = ROOT / "plugin" / "openclaw.plugin.json"
    data = json.loads(oc.read_text(encoding="utf-8"))
    data["version"] = VERSION
    oc.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    written = sync_files()
    stamp_version()
    print(f"synced @ v{VERSION}: {written} Datei-Kopien; Version in plugin.json + marketplace.json gestempelt.")
