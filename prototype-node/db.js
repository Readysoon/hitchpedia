// hitchpedia v1 — lokale Datenhaltung (node:sqlite, kein npm-Install nötig)
// Beim Deploy: Postgres + pgvector. Lokal: SQLite + FTS5 (Keyword-Suche).
import { DatabaseSync } from 'node:sqlite';

const DB_PATH = new URL('./hitchpedia.db', import.meta.url).pathname;
export const db = new DatabaseSync(DB_PATH);

export function init() {
  db.exec(`
    CREATE TABLE IF NOT EXISTS entries (
      id TEXT PRIMARY KEY,
      sequence_no INTEGER,
      tool TEXT, version TEXT, os TEXT,
      tier TEXT DEFAULT 'unverified',
      status TEXT DEFAULT 'active',              -- active | quarantined
      problem TEXT, context TEXT, solution TEXT, verification TEXT,
      error_signature TEXT,
      contributor TEXT, model TEXT, model_version TEXT, env TEXT, source TEXT,
      worked INTEGER DEFAULT 0, failed INTEGER DEFAULT 0, flags INTEGER DEFAULT 0,
      retrieval_count INTEGER DEFAULT 0,
      created_at TEXT
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
      id UNINDEXED, problem, context, solution, error_signature, tool
    );
    CREATE TABLE IF NOT EXISTS keys ( key TEXT PRIMARY KEY, name TEXT, created_at TEXT );
  `);
  // embedding-Spalte nachrüsten (SQLite kennt kein "ADD COLUMN IF NOT EXISTS")
  const cols = db.prepare(`PRAGMA table_info(entries)`).all().map(c => c.name);
  if (!cols.includes('embedding')) db.exec(`ALTER TABLE entries ADD COLUMN embedding TEXT`);
}

export function setEmbedding(id, vec) {
  db.prepare(`UPDATE entries SET embedding=? WHERE id=?`).run(JSON.stringify(vec), id);
}

export function nextSeq() {
  const r = db.prepare(`SELECT COALESCE(MAX(sequence_no),0)+1 AS n FROM entries`).get();
  return r.n;
}

// Fügt einen Eintrag ein (entries + FTS-Index synchron). Gibt id + sequence_no zurück.
export function insertEntry(e) {
  const seq = e.sequence_no ?? nextSeq();
  db.prepare(`INSERT OR REPLACE INTO entries
    (id,sequence_no,tool,version,os,tier,status,problem,context,solution,verification,
     error_signature,contributor,model,model_version,env,source,
     worked,failed,flags,retrieval_count,created_at)
    VALUES (@id,@seq,@tool,@version,@os,@tier,'active',@problem,@context,@solution,@verification,
     @error_signature,@contributor,@model,@model_version,@env,@source,
     @worked,@failed,0,0,@created_at)`).run({
      id: e.id, seq,
      tool: e.tool ?? '', version: e.version ?? '*', os: e.os ?? '',
      tier: e.tier ?? 'unverified',
      problem: e.problem ?? '', context: e.context ?? '', solution: e.solution ?? '',
      verification: e.verification ?? '', error_signature: e.error_signature ?? '',
      contributor: e.contributor ?? '', model: e.model ?? '', model_version: e.model_version ?? '',
      env: e.env ?? '', source: e.source ?? '',
      worked: e.worked ?? 0, failed: e.failed ?? 0,
      created_at: e.created_at ?? new Date().toISOString()
    });
  db.prepare(`DELETE FROM entries_fts WHERE id=?`).run(e.id);
  db.prepare(`INSERT INTO entries_fts (id,problem,context,solution,error_signature,tool)
              VALUES (?,?,?,?,?,?)`).run(
    e.id, e.problem ?? '', e.context ?? '', e.solution ?? '', e.error_signature ?? '', e.tool ?? '');
  return { id: e.id, sequence_no: seq };
}

// ── Seed: der erste echte Eintrag (SPBView .NET-Pfad-Bug, generalisiert + anonymisiert) ──
export const SEED = [{
  id: 'kb_0a41',
  tool: '.NET Framework', version: '4.x', os: 'windows',
  tier: 'unverified', worked: 1, failed: 0,
  problem: '.NET-Framework-App crasht beim Start mit System.TypeInitializationException -> innere System.IO.DirectoryNotFoundException; im gesuchten Pfad steht %20. Die App findet ihre eigene Konfig-/Ressourcendatei nicht, obwohl sie korrekt neben der .exe liegt. Crash in der statischen Initialisierung, bevor die GUI erscheint.',
  context: '.NET Framework 4.x (nicht .NET Core), Windows. Ein Ordner OBERHALB der .exe enthaelt ein Leerzeichen (z.B. "NEW APP"). Dieselbe .exe laeuft von Pfaden ohne Leerzeichen problemlos.',
  solution: 'SOFORT-FIX (verifiziert, ohne Code-Aenderung): den Ordner mit Leerzeichen umbenennen, z.B. Rename-Item "D:\\...\\NEW APP" "NEW_APP". Regel: kein Leerzeichen in irgendeiner Pfadkomponente oberhalb der .exe. — URSACHE/CODE-FIX (aus Stacktrace erschlossen, NICHT quellcode-verifiziert): die App bestimmt ihr eigenes Verzeichnis ueber eine file://-URI (Assembly.CodeBase) und nutzt den String UNDEKODIERT als Dateisystempfad -> "NEW APP" wird zu "NEW%20APP". Sauber: Assembly.Location bzw. new Uri(codeBase).LocalPath (dekodiert) verwenden.',
  verification: 'Vorher: sofortiger Crash, keine GUI. Nachher: App startet, GUI oeffnet, Log zeigt den Pfad ohne %20 (...\\NEW_APP\\...), Datei laedt normal.',
  error_signature: 'System.TypeInitializationException -> System.IO.DirectoryNotFoundException %20 im Pfad static init File.ReadLines StreamReader',
  contributor: 'seed', model: 'claude-opus-4-8', model_version: '2026-07-11',
  env: 'Windows 11 (de), .NET Framework 4.x',
  source: 'SPBView (github.com/ElsevierSoftwareX/SOFTX-D-24-00417), GUI v0.1.0 / Build v0.2.1_051325'
}];

export function seed() {
  init();
  for (const e of SEED) insertEntry(e);
  // Test-API-Key fuer /contribute
  db.prepare(`INSERT OR IGNORE INTO keys (key,name,created_at) VALUES (?,?,?)`)
    .run('hp_test_key', 'local-dev', new Date().toISOString());
  const n = db.prepare(`SELECT COUNT(*) c FROM entries`).get().c;
  console.log(`Seed fertig: ${n} Eintrag/Einträge. Test-Key: hp_test_key`);
}

// direkt ausführbar: node db.js  → (re)seed
if (import.meta.url === `file://${process.argv[1]}`) seed();
