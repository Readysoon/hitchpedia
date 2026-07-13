"""Batch-Seed 2: weitere GitHub-Repos (openclaw/ollama/fastapi/pydantic/psycopg) + kanonisch.
Mehrere davon in diesem Projekt selbst erlebt."""
import asyncio
from app.models import database, entry
from app.services import embeddings

M = {"contributor": "seed-github", "model": "claude-opus-4-8", "model_version": "2026-07-13"}

ENTRIES = [
    {**M, "id": "kb_pydantic_v2", "tool": "pydantic", "version": ">=2", "os": "*",
     "problem": "Nach Upgrade auf Pydantic v2 brechen Modelle: AttributeError/DeprecationWarning bei .dict(), @validator, class Config, parse_obj.",
     "context": "Pydantic v2, aus v1 migrierter Code.",
     "solution": ".dict()→.model_dump(); .json()→.model_dump_json(); @validator→@field_validator (+@classmethod); @root_validator→@model_validator; class Config→model_config=ConfigDict(...); parse_obj→model_validate; parse_raw→model_validate_json. Die v1-Namen sind deprecated/entfernt.",
     "verification": "Kein DeprecationWarning/AttributeError; Modelle validieren/serialisieren wie erwartet.",
     "error_signature": "pydantic v2 migration .dict model_dump validator field_validator class Config model_config parse_obj deprecated AttributeError", "source": "pydantic v2 Migration-Guide"},

    {**M, "id": "kb_pgbouncer_prepared", "tool": "postgres", "version": "*", "os": "*",
     "problem": "Postgres-Fehler 'prepared statement \"...\" already exists' bzw. 'does not exist' hinter PgBouncer.",
     "context": "psycopg3 / asyncpg / SQLAlchemy gegen PgBouncer im transaction- oder statement-pooling-Modus. Die Treiber nutzen server-side prepared statements, PgBouncer teilt Server-Verbindungen aber pro Transaktion neu zu.",
     "solution": "Server-side prepared statements deaktivieren: psycopg3 prepare_threshold=None; asyncpg statement_cache_size=0; SQLAlchemy/asyncpg-URL mit prepared_statement_cache_size=0. Alternativ PgBouncer auf session-pooling stellen.",
     "verification": "Keine 'prepared statement already exists/does not exist'-Fehler mehr unter Last.",
     "error_signature": "prepared statement already exists does not exist pgbouncer psycopg asyncpg transaction pooling prepare_threshold statement_cache_size", "source": "github: psycopg/psycopg#589; PgBouncer-Doku"},

    {**M, "id": "kb_fastapi_blocking", "tool": "fastapi", "version": "*", "os": "*",
     "problem": "FastAPI-App wird unter Last extrem langsam / blockiert — ein 'async def'-Endpoint ruft eine blockierende (synchrone) Funktion auf.",
     "context": "FastAPI/Starlette; ein 'async def'-Endpoint macht synchrone I/O (DB, requests, time.sleep) direkt, ohne await/Threadpool.",
     "solution": "Entweder den Endpoint als normales 'def' deklarieren (FastAPI führt ihn dann im Threadpool aus), ODER echte async-Libs benutzen (httpx statt requests, async DB-Treiber), ODER blockierende Aufrufe in 'await run_in_threadpool(...)' wrappen. Ein blockierender Call in 'async def' blockiert den ganzen Event-Loop.",
     "verification": "Unter parallelen Requests bleibt die App responsiv; kein Blockieren.",
     "error_signature": "fastapi slow blocking event loop async def sync call run_in_threadpool starlette concurrency", "source": "gotcha: FastAPI blocking async endpoint (FastAPI-Doku)"},

    {**M, "id": "kb_fastapi_422", "tool": "fastapi", "version": "*", "os": "*",
     "problem": "FastAPI antwortet 422 Unprocessable Entity / 'Input should be a valid dictionary' bei einem POST, obwohl der JSON-Body korrekt aussieht.",
     "context": "curl/Client schickt JSON per -d, aber OHNE Header Content-Type: application/json. FastAPI parst den Body dann nicht als JSON.",
     "solution": "Bei POST mit JSON-Body den Header setzen: -H 'Content-Type: application/json'. curl -d setzt sonst application/x-www-form-urlencoded, und der Pydantic-Body-Parser lehnt ab.",
     "verification": "Request wird akzeptiert; kein 422 mehr.",
     "error_signature": "fastapi 422 Unprocessable Entity Input should be a valid dictionary curl -d Content-Type application/json missing", "source": "gotcha: FastAPI JSON body Content-Type"},

    {**M, "id": "kb_fastapi_opid", "tool": "fastapi", "version": "*", "os": "*",
     "problem": "FastAPI/OpenAPI erzeugt doppelte operationId, wenn eine Route mit mehreren Methoden registriert wird — Client-Generatoren kollidieren.",
     "context": "FastAPI-Route mit methods=['GET','POST'] o.ä.; OpenAPI generiert kollidierende operationIds.",
     "solution": "Pro Methode eine eigene Route/Funktion (getrennte @app.get/@app.post) statt einer Funktion mit mehreren methods; oder operation_id explizit setzen. Dann sind die operationIds eindeutig.",
     "verification": "OpenAPI hat eindeutige operationIds; Client-Generierung ohne Kollision.",
     "error_signature": "fastapi duplicated operationId multiple methods openapi client generator", "source": "github: fastapi/fastapi#13175"},

    {**M, "id": "kb_ollama_ctx", "tool": "ollama", "version": "*", "os": "*",
     "problem": "Ollama (Embedding oder Generate) gibt HTTP 500 'input length exceeds the context length'.",
     "context": "Der Prompt/Text ist länger als das Kontextfenster des Modells (z.B. all-minilm ~256 Token).",
     "solution": "Text vor dem Embedden auf die Kontextlänge des Modells kappen, oder ein Modell mit größerem Kontext nutzen (z.B. nomic-embed-text, 8192 Token). Bei Generate num_ctx passend setzen. Das Limit ist modellabhängig.",
     "verification": "Kein 500 'input length exceeds context'; Embedding/Antwort kommt zurück.",
     "error_signature": "ollama 500 input length exceeds the context length embedding truncate num_ctx model context window", "source": "gotcha: Ollama context length (selbst erlebt)"},
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
