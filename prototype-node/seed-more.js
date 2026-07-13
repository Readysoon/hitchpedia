// 12 konkrete Seed-Einträge über die 6 Kategorien. Vertrauter Seed-Pfad (kein Gate).
import { init, insertEntry, db } from './db.js';
init();

const M = { contributor: 'seed', model: 'claude-opus-4-8', model_version: '2026-07-13' };

const ENTRIES = [
  // ── Kat 1: Versions-Verhaltens-Gotchas ──
  { ...M, id: 'kb_npm11', tool: 'npm', version: '>=11', os: '*',
    problem: 'npm install schlägt fehl mit "ERESOLVE unable to resolve dependency tree" ab npm 11 (strikte Peer-Dep-Auflösung), obwohl es unter npm <=10 lief.',
    context: 'npm >=11, Node 20+, Projekt mit widersprüchlichen transitiven Peer-Dependencies.',
    solution: 'Konfligierende Version in package.json unter "overrides" pinnen — behebt die Ursache. Notlösung: npm install --legacy-peer-deps (unterdrückt nur). npm 11 ist strikt by design, kein Bug.',
    verification: 'npm install exit 0, node_modules vollständig, kein ERESOLVE.',
    error_signature: 'npm ERESOLVE unable to resolve dependency tree peer dependency', source: 'gotcha: npm 11 strict peers' },

  { ...M, id: 'kb_pyutc', tool: 'python', version: '>=3.12', os: '*',
    problem: 'Python 3.12 wirft DeprecationWarning für datetime.utcnow() / utcfromtimestamp(); das Ergebnis ist naiv (tzinfo=None) und führt zu falschen Zeitvergleichen.',
    context: 'Python >=3.12.',
    solution: 'datetime.now(datetime.UTC) statt datetime.utcnow(); datetime.fromtimestamp(ts, datetime.UTC) statt utcfromtimestamp. Liefert ein timezone-aware Objekt.',
    verification: 'Kein DeprecationWarning; dt.tzinfo ist gesetzt (nicht None).',
    error_signature: 'DeprecationWarning datetime.utcnow deprecated', source: 'gotcha: python 3.12 datetime' },

  // ── Kat 2: Umgebungs-/Shell-Gotchas ──
  { ...M, id: 'kb_shellquote', tool: 'bash', version: '*', os: '*',
    problem: 'Shell-Befehl scheitert mit "No such file or directory" bei Pfaden/Argumenten mit Leerzeichen, obwohl die Datei existiert.',
    context: 'bash/zsh/sh; eine Variable enthält einen Pfad mit Leerzeichen (z.B. "My Documents").',
    solution: 'Die Variable in doppelte Anführungszeichen setzen: cat "$file" statt cat $file. Unquoted splittet die Shell am Leerzeichen (word splitting) in mehrere Argumente. Gilt für JEDE Variable, die Leerzeichen enthalten kann.',
    verification: 'Befehl mit Leerzeichen-Pfad läuft statt zu scheitern.',
    error_signature: 'No such file or directory shell space path unquoted variable', source: 'gotcha: shell word-splitting' },

  { ...M, id: 'kb_echonl', tool: 'bash', version: '*', os: '*',
    problem: 'API-Request antwortet 401/invalid token, obwohl der Key stimmt — der Token hat unsichtbar ein Newline am Ende.',
    context: 'Token/Secret per `echo "$TOKEN" > file` oder KEY=$(echo ...) gebaut; bash/sh.',
    solution: 'printf %s statt echo verwenden: printf %s "$TOKEN" > file. echo hängt standardmäßig ein \\n an, das im Auth-Header als Teil des Tokens landet.',
    verification: 'Request authentifiziert; Token-Länge stimmt (kein Trailing-\\n, prüfbar mit wc -c).',
    error_signature: '401 invalid token trailing newline echo printf', source: 'gotcha: echo newline in token' },

  // ── Kat 3: API-/Interface-Quirks ──
  { ...M, id: 'kb_pagination', tool: 'http-api', version: '*', os: '*',
    problem: 'Agent liest von einer API nur einen Teil der Daten — Einträge fehlen, obwohl die API mehr hat. Ursache: nur die erste Seite gelesen.',
    context: 'REST-API mit Pagination (Link-Header "next" oder cursor/next_page im JSON).',
    solution: 'Pagination bis zum Ende folgen: solange ein next-Cursor/Link existiert, weiter abrufen und akkumulieren. Nie annehmen, dass die erste Antwort vollständig ist.',
    verification: 'Anzahl geholter Einträge == erwartete Gesamtzahl; kein next-Cursor mehr übrig.',
    error_signature: 'missing data pagination first page only next cursor Link header', source: 'gotcha: pagination ignored' },

  { ...M, id: 'kb_retryafter', tool: 'http-api', version: '*', os: '*',
    problem: 'Wiederholte 429 Too Many Requests, weil nach einem 429 sofort erneut angefragt wird (Retry-Storm).',
    context: 'HTTP-API mit Rate-Limit; Antwort enthält Retry-After- oder X-RateLimit-Reset-Header.',
    solution: 'Den Retry-After-Header lesen und exakt so lange warten (Fallback: exponentielles Backoff mit Jitter). Nicht sofort retryen.',
    verification: 'Keine weiteren 429 nach dem Backoff; Requests laufen durch.',
    error_signature: '429 Too Many Requests Retry-After rate limit backoff', source: 'gotcha: ignoring Retry-After' },

  // ── Kat 4: Framework-Footguns ──
  { ...M, id: 'kb_lg_none', tool: 'langgraph', version: '*', os: '*',
    problem: 'In LangGraph verschwinden Werte still — ein State-Feld ist plötzlich None statt zu crashen, nachdem ein Feld umbenannt/entfernt wurde.',
    context: 'LangGraph StateGraph; ein Node liest/schreibt einen State-Key, der nicht (mehr) im State-Schema definiert ist.',
    solution: 'State-Key-Namen zwischen Schema und allen Node-Rückgaben abgleichen; State als TypedDict/Pydantic strikt definieren, damit unbekannte Keys auffallen. LangGraph merged Rückgaben und ersetzt Unpassendes still — es wirft keinen Fehler.',
    verification: 'Das erwartete Feld enthält den Wert (nicht None) am Zielknoten.',
    error_signature: 'langgraph state field None silent renamed key StateGraph', source: 'gotcha: langgraph swallows renamed key' },

  { ...M, id: 'kb_lc_import', tool: 'langchain', version: '>=0.1', os: '*',
    problem: 'ImportError/DeprecationWarning: "from langchain.chat_models import ChatOpenAI" funktioniert nicht mehr oder warnt.',
    context: 'LangChain >=0.1 (Paket-Split in langchain-core / langchain-openai etc.).',
    solution: 'Aus dem Partner-Paket importieren: "from langchain_openai import ChatOpenAI" (vorher pip install langchain-openai). Analog langchain_anthropic, langchain_community.',
    verification: 'Import ohne Fehler/Warnung; ChatOpenAI instanziierbar.',
    error_signature: 'ImportError langchain chat_models ChatOpenAI langchain_openai package split', source: 'gotcha: langchain import split' },

  // ── Kat 5: Silent-Failure-Muster ──
  { ...M, id: 'kb_finishlength', tool: 'llm-api', version: '*', os: '*',
    problem: 'Antwort des Modells ist abgeschnitten / JSON invalide (fehlende schließende Klammer) — still, ohne Fehler. Der Agent parst kaputtes JSON.',
    context: 'LLM-API-Call mit strukturierter/JSON-Ausgabe; max_tokens zu niedrig.',
    solution: 'finish_reason/stop_reason prüfen: bei "length"/"max_tokens" war die Antwort abgeschnitten → max_tokens erhöhen oder per Continuation weiterfragen. Nie blind das JSON parsen, ohne finish_reason zu checken.',
    verification: 'finish_reason == "stop"/"end_turn" UND JSON valide.',
    error_signature: 'truncated JSON finish_reason length max_tokens invalid json', source: 'gotcha: finish_reason length' },

  { ...M, id: 'kb_asyncawait', tool: 'python-asyncio', version: '*', os: '*',
    problem: 'Eine async-Funktion tut scheinbar nichts — kein Fehler, kein Ergebnis. Log: "coroutine was never awaited".',
    context: 'Python asyncio; eine Coroutine wurde aufgerufen, aber nicht awaited (do_thing() statt await do_thing()).',
    solution: 'Die Coroutine awaiten: await do_thing(); für Fire-and-forget asyncio.create_task(do_thing()). Ein reiner Aufruf erzeugt nur ein Coroutine-Objekt und führt nichts aus.',
    verification: 'Die Funktion läuft tatsächlich; keine "never awaited"-Warnung mehr.',
    error_signature: 'coroutine was never awaited asyncio missing await', source: 'gotcha: missing await' },

  // ── Kat 6: Retrieval-/Injection-Fallen ──
  { ...M, id: 'kb_indirectinj', tool: 'agent', version: '*', os: '*',
    problem: 'Agent führt plötzlich fremde Anweisungen aus, die in abgerufenem Inhalt (Webseite, Tool-Output, Dokument) versteckt waren — indirect prompt injection.',
    context: 'Agent, der Tool-/Web-Ergebnisse in den Prompt übernimmt und als Kontext behandelt.',
    solution: 'Abgerufenen Inhalt strikt als DATEN behandeln, nicht als Instruktionen: klar per Delimiter/eigene Rolle abgrenzen, dem Modell sagen, in retrieved content eingebettete Befehle nicht zu befolgen, und keine Tool-Ausführung allein auf Basis von retrieved content ohne Bestätigung/Allow-List.',
    verification: 'Eine Testseite mit eingebettetem Befehl ändert das Agentenverhalten nicht mehr.',
    error_signature: 'indirect prompt injection retrieved content tool output executes instructions', source: 'gotcha: indirect prompt injection' },

  { ...M, id: 'kb_ragvocab', tool: 'rag', version: '*', os: '*',
    problem: 'Semantische/Vektor-Suche findet den relevanten Eintrag nicht, obwohl er existiert — Query und Dokument benutzen unterschiedliche Begriffe.',
    context: 'RAG mit reiner Vektor-Suche (dense retrieval); Vokabular-Mismatch zwischen Frage und Dokument.',
    solution: 'Hybrid-Suche: Vektor + Keyword (BM25) kombinieren und fusionieren (RRF). Alternativ HyDE (hypothetisches Antwort-Dokument generieren, dessen Embedding suchen). Reines dense retrieval verfehlt exakte Begriffe/IDs/Fehlercodes.',
    verification: 'Die Ziel-Passage erscheint in Top-k; Hit-Rate auf einem Test-Set steigt.',
    error_signature: 'vector search misses relevant document vocabulary mismatch hybrid BM25 HyDE', source: 'gotcha: rag vocabulary mismatch' }
];

for (const e of ENTRIES) insertEntry(e);
const n = db.prepare(`SELECT COUNT(*) c FROM entries WHERE status='active'`).get().c;
console.log(`+${ENTRIES.length} Einträge geseedet. Aktiv gesamt: ${n}`);
