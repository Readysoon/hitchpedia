"""Batch-Seed 3: Stack-Overflow-Quelle (top-gevotete, konkrete Fehler-Fragen).
Fix extrahiert + umgeschrieben (CC-BY-SA: nicht wörtlich kopiert, Quelle zitiert)."""
import asyncio
from app.models import database, entry
from app.services import embeddings

M = {"contributor": "seed-so", "model": "claude-opus-4-8", "model_version": "2026-07-13"}

ENTRIES = [
    {**M, "id": "kb_uvicorn_import", "tool": "uvicorn", "version": "*", "os": "*",
     "problem": "uvicorn startet nicht: 'ERROR: Error loading ASGI app. Could not import module \"...\"'.",
     "context": "uvicorn app.main:app o.ä.; das Modul/die App-Variable wird nicht gefunden.",
     "solution": "Aus dem Projekt-Root starten (dort, wo das Paket 'app' liegt), Modulpfad korrekt als paket.modul:app_variable angeben (z.B. app.main:app), und __init__.py in den Paket-Ordnern sicherstellen. Aus einem Unterordner gestartet ist das Paket nicht im Import-Pfad.",
     "verification": "uvicorn startet, App lädt ohne 'Could not import'.",
     "error_signature": "uvicorn Error loading ASGI app Could not import module app.main:app path package __init__", "source": "stackoverflow: 'Error loading ASGI app' (CC-BY-SA)"},

    {**M, "id": "kb_pgvector_dim", "tool": "pgvector", "version": "*", "os": "*",
     "problem": "pgvector-Fehler 'expected N dimensions, not M' beim Insert/Query — die Embedding-Dimension passt nicht zur Spalten-Dimension vector(N).",
     "context": "Postgres + pgvector; das Embedding-Modell liefert eine andere Dimension als die Spalte vector(N) (z.B. Modellwechsel 384→768).",
     "solution": "Spalten-Dimension muss exakt zur Modell-Dimension passen. Bei Modellwechsel die Spalte neu anlegen: DROP COLUMN embedding; ADD COLUMN embedding vector(<neue_dim>); HNSW-Index neu; alle Einträge neu embedden. vector(N) ist fix und castet nicht zwischen Dimensionen.",
     "verification": "Kein 'expected N dimensions'; Insert/Query laufen; Suche liefert Treffer.",
     "error_signature": "pgvector expected N dimensions not M embedding dimension mismatch vector column model change", "source": "stackoverflow: pgvector dimension mismatch (CC-BY-SA); selbst erlebt"},

    {**M, "id": "kb_pgvector_alpine", "tool": "postgres", "version": "*", "os": "*",
     "problem": "CREATE EXTENSION vector schlägt fehl ('extension \"vector\" is not available' / control file not found) im offiziellen postgres-Image.",
     "context": "Docker mit dem offiziellen postgres(-alpine)-Image; pgvector ist dort nicht vorinstalliert. (Gleiche Ursache lokal: pgvector muss zur exakten Postgres-Major-Version gebaut sein.)",
     "solution": "Das fertige Image pgvector/pgvector:pg16 (o.ä.) verwenden — es enthält die Extension. Oder pgvector im eigenen Dockerfile bauen. Lokal via Homebrew: die Postgres-Version installieren, für die pgvector gebaut wurde (die brew-pgvector-Formel zielt auf eine bestimmte Major-Version).",
     "verification": "CREATE EXTENSION vector; läuft; SELECT extversion FROM pg_extension WHERE extname='vector' zeigt die Version.",
     "error_signature": "CREATE EXTENSION vector is not available control file not found postgres alpine docker pgvector not installed wrong major version", "source": "stackoverflow: pgvector on postgres image (CC-BY-SA); selbst erlebt"},

    {**M, "id": "kb_langchain_community", "tool": "langchain", "version": ">=0.1", "os": "*",
     "problem": "ModuleNotFoundError: No module named 'langchain_community' (oder 'langchain_openai' etc.).",
     "context": "LangChain >=0.1; Community-/Provider-Integrationen sind in separate Pakete ausgelagert.",
     "solution": "Das jeweilige Partner-Paket installieren: pip install langchain-community (bzw. langchain-openai, langchain-anthropic). Seit dem 0.1-Split sind diese Integrationen nicht mehr im Kern-langchain enthalten.",
     "verification": "Import von langchain_community.* funktioniert.",
     "error_signature": "ModuleNotFoundError No module named langchain_community langchain_openai pip install partner package split", "source": "stackoverflow: langchain_community ModuleNotFound (CC-BY-SA)"},
]


async def main():
    database.init()
    for e in ENTRIES:
        entry.upsert(e)
    for e in ENTRIES:
        vec = await embeddings.embed(embeddings.embed_text_for(e), kind="document")
        entry.set_embedding(e["id"], vec)
        print(".", end="", flush=True)
    print(f"\n+{len(ENTRIES)} Einträge. Aktiv gesamt: {entry.db_size()['entries']}")


if __name__ == "__main__":
    asyncio.run(main())
