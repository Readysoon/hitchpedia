"""Batch-Seed: 10 konkrete Gotchas aus GitHub-Issues (verifizierter Verlauf) + kanonischem Wissen.
Ausführen:  ./.venv/bin/python seed_batch.py
"""
import asyncio
from app.models import database, entry
from app.services import embeddings

M = {"contributor": "seed-github", "model": "claude-opus-4-8", "model_version": "2026-07-13"}

ENTRIES = [
    {**M, "id": "kb_mcp_stdio", "tool": "mcp", "version": "*", "os": "*",
     "problem": "MCP-stdio-Server funktioniert nicht / der Client bricht mit JSON-Parse-Fehler ab, obwohl der Server läuft.",
     "context": "MCP-Server über stdio-Transport (stdin/stdout ist der JSON-RPC-Kanal); der Server nutzt print()/console.log() fürs Logging.",
     "solution": "Bei stdio ist stdout AUSSCHLIESSLICH der JSON-RPC-Kanal. Jede Log-/Debug-Ausgabe muss nach stderr: in Python print(..., file=sys.stderr) bzw. logging auf stderr; in Node console.error(...). Ein einziges print()/console.log() nach stdout korrumpiert die Protokoll-Nachrichten.",
     "verification": "Client verbindet, Tools werden gelistet, keine JSON-Parse-Fehler; Logs erscheinen auf stderr.",
     "error_signature": "MCP stdio server broken JSON parse error stdout logging console.log print protocol corrupt", "source": "gotcha: MCP stdio stdout-vs-stderr (MCP-Doku)"},

    {**M, "id": "kb_npm_catalog", "tool": "npm", "version": "*", "os": "*",
     "problem": "npm install bricht sofort ab mit 'Unsupported URL Type \"catalog:\"' beim Klonen eines Repos.",
     "context": "Das Repo nutzt pnpm-Workspaces mit dem 'catalog:'-Protokoll (pnpm catalogs); npm/yarn verstehen das nicht.",
     "solution": "pnpm statt npm verwenden: corepack enable, dann pnpm install. 'catalog:' ist ein pnpm-spezifisches Feature. Das Repo pinnt die Version meist in package.json 'packageManager'.",
     "verification": "pnpm install läuft durch; kein 'Unsupported URL Type'.",
     "error_signature": "npm install Unsupported URL Type catalog: pnpm workspaces catalogs corepack", "source": "github: modelcontextprotocol/typescript-sdk#1880"},

    {**M, "id": "kb_node_exports", "tool": "node", "version": "*", "os": "*",
     "problem": "Import aus einem npm-Paket scheitert mit ERR_PACKAGE_PATH_NOT_EXPORTED, obwohl der Pfad zu existieren scheint.",
     "context": "Node.js; das Paket nutzt das package.json 'exports'-Feld (subpath exports). Häufig ist die laufende Node-Version zu alt für dessen Auflösung.",
     "solution": "Node auf aktuelle LTS aktualisieren — ältere Versionen lösen moderne 'exports'-Maps nicht auf. Und nur die im 'exports' deklarierten Subpaths importieren, nicht interne Dateien (z.B. '.../server' statt '.../dist/server/index.js').",
     "verification": "Import löst ohne ERR_PACKAGE_PATH_NOT_EXPORTED auf.",
     "error_signature": "ERR_PACKAGE_PATH_NOT_EXPORTED import resolution exports field old node version subpath", "source": "github: modelcontextprotocol/typescript-sdk#99"},

    {**M, "id": "kb_lg_state_optional", "tool": "langgraph", "version": "*", "os": "*",
     "problem": "LangGraph wirft ValidationError für den State ('validation error for State ... Before task with name'), sobald ein Knoten läuft.",
     "context": "LangGraph StateGraph mit Pydantic-State; Pflichtfelder, die zu Beginn/in Zwischenschritten noch nicht gesetzt sind. LangGraph validiert den State bei JEDEM Schritt.",
     "solution": "Alle State-Felder optional machen (Optional[...] mit Default, bzw. TypedDict mit total=False). Felder, die erst später befüllt werden, dürfen keine Pflichtfelder sein — sonst schlägt die Validierung im Zwischenschritt fehl.",
     "verification": "Graph läuft ohne ValidationError; Felder werden schrittweise befüllt.",
     "error_signature": "langgraph ValidationError validation error for State required field pydantic optional each step", "source": "github: langchain-ai/langgraph#5659"},

    {**M, "id": "kb_node_esm", "tool": "node", "version": "*", "os": "*",
     "problem": "Node bricht ab mit 'Cannot use import statement outside a module' oder 'require() of ES Module ... not supported' (ERR_REQUIRE_ESM).",
     "context": "Node.js; Mischung aus ESM (import/export) und CommonJS (require).",
     "solution": "Für ESM: in package.json \"type\": \"module\" setzen (oder Datei .mjs). Um ein ESM-only-Paket aus CommonJS zu nutzen: dynamisches await import() statt require(). Nie require() auf ein ESM-Paket.",
     "verification": "Datei läuft ohne 'import outside a module' / 'require of ES Module'.",
     "error_signature": "Cannot use import statement outside a module require of ES Module not supported ERR_REQUIRE_ESM type module mjs", "source": "gotcha: Node ESM/CJS (Node-Doku)"},

    {**M, "id": "kb_pip_env", "tool": "python", "version": "*", "os": "*",
     "problem": "ModuleNotFoundError für ein Paket, das man gerade mit pip install installiert hat.",
     "context": "Python; pip und der laufende python zeigen auf verschiedene Umgebungen (System-pip vs venv, oder mehrere Python-Versionen).",
     "solution": "Immer python -m pip install <paket> statt bloß pip install — dann wird garantiert die pip des laufenden Interpreters benutzt. In einer venv installieren UND ausführen. Prüfen mit python -m pip show <paket> und which python.",
     "verification": "import <paket> funktioniert; python -m pip show zeigt das Paket im aktiven Interpreter.",
     "error_signature": "ModuleNotFoundError after pip install package not found wrong environment venv python -m pip", "source": "gotcha: pip/python env mismatch"},

    {**M, "id": "kb_pgvector_opclass", "tool": "pgvector", "version": "*", "os": "*",
     "problem": "pgvector-Suche ist langsam / der HNSW- (oder IVFFlat-) Index wird nicht genutzt (EXPLAIN zeigt Seq Scan).",
     "context": "Postgres + pgvector; ein Index existiert, wird aber ignoriert. Häufigste Ursache: die Operator-Klasse des Index passt nicht zum Distanz-Operator der Query.",
     "solution": "Operator-Klasse und Query-Operator müssen zusammenpassen: vector_cosine_ops ↔ <=> (Cosine), vector_l2_ops ↔ <-> (L2), vector_ip_ops ↔ <#>. Beispiel: Index mit vector_cosine_ops → Query 'ORDER BY embedding <=> $1' (nicht <->). EXPLAIN muss danach einen Index-Scan zeigen.",
     "verification": "EXPLAIN zeigt Index-Scan statt Seq Scan; Query ist schnell.",
     "error_signature": "pgvector HNSW index not used seq scan slow operator class vector_cosine_ops distance operator mismatch", "source": "gotcha: pgvector operator class (pgvector-Doku)"},

    {**M, "id": "kb_asyncio_nested", "tool": "python-asyncio", "version": "*", "os": "*",
     "problem": "asyncio.run(...) wirft 'RuntimeError: asyncio.run() cannot be called from a running event loop' (z.B. in Jupyter).",
     "context": "Python asyncio in einer Umgebung mit bereits laufendem Event-Loop (Jupyter/IPython, manche Frameworks).",
     "solution": "Kein asyncio.run in einem laufenden Loop: stattdessen die Coroutine direkt awaiten (Jupyter erlaubt top-level await), oder in Skripten den Loop selbst managen. Notlösung in Jupyter: import nest_asyncio; nest_asyncio.apply().",
     "verification": "Coroutine läuft ohne 'cannot be called from a running event loop'.",
     "error_signature": "RuntimeError asyncio.run cannot be called from a running event loop jupyter nest_asyncio", "source": "gotcha: asyncio nested loop"},

    {**M, "id": "kb_dockerarch", "tool": "docker", "version": "*", "os": "darwin",
     "problem": "Docker-Container startet nicht auf Apple Silicon (arm64) mit 'exec format error' — das Image ist nur für amd64 gebaut.",
     "context": "Docker auf Apple Silicon (M-Serie, arm64); Image ohne arm64-Variante.",
     "solution": "Image mit --platform=linux/amd64 starten (Emulation), oder ein multi-arch Base-Image nutzen. Beim Build: docker buildx build --platform linux/amd64,linux/arm64 ...",
     "verification": "Container startet ohne 'exec format error'.",
     "error_signature": "docker exec format error apple silicon arm64 platform amd64 image mismatch", "source": "gotcha: docker arch mismatch"},

    {**M, "id": "kb_lg_streammodes", "tool": "langgraph", "version": "*", "os": "*",
     "problem": "Beim Streamen in LangGraph kommen sowohl token-by-token-Chunks ALS AUCH die volle Nachricht am Ende — Inhalt scheint doppelt.",
     "context": "LangGraph .stream/.astream; mehrere stream-Modi aktiv oder falscher Modus erwartet.",
     "solution": "Den passenden stream_mode wählen und danach filtern: 'messages' liefert Token-Chunks, 'values'/'updates' den (vollen) State. Nicht mehrere Modi vermischen und alles rendern. Die 'volle' Nachricht am Ende ist der State-Emit, kein Duplikat des Token-Streams.",
     "verification": "Nur die erwartete Stream-Form kommt an (Tokens ODER finaler Wert), kein doppelter Inhalt.",
     "error_signature": "langgraph streaming token by token and full message at end duplicate stream_mode messages values", "source": "github: langchain-ai/langgraph#6153"},
]


async def main():
    database.init()
    for e in ENTRIES:
        gate_ok = True  # Seeds gehen über den vertrauten Pfad; Gate wird beim Contribute geprüft
        entry.upsert(e)
    for e in ENTRIES:
        vec = await embeddings.embed(embeddings.embed_text_for(e), kind="document")
        entry.set_embedding(e["id"], vec)
        print(".", end="", flush=True)
    total = entry.db_size()["entries"]
    print(f"\n+{len(ENTRIES)} Einträge geseedet + embeddet. Aktiv gesamt: {total}")


if __name__ == "__main__":
    asyncio.run(main())
