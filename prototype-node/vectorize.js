// Embeddet alle Einträge, die noch kein Embedding haben. Idempotent.
import { init, db, setEmbedding } from './db.js';
import { embed } from './embed.js';
init();

const rows = db.prepare(
  `SELECT id, problem, context, solution, error_signature FROM entries
   WHERE status='active' AND (embedding IS NULL OR embedding='')`).all();

console.log(`embedde ${rows.length} Eintrag/Einträge…`);
for (const r of rows) {
  // retrieval-relevant: Problem + Fehler-Signatur + Kontext (NICHT die lange Lösung)
  const text = [r.problem, r.error_signature, r.context].filter(Boolean).join(' ');
  const v = await embed(text);
  setEmbedding(r.id, v);
  process.stdout.write('.');
}
const total = db.prepare(`SELECT COUNT(*) c FROM entries WHERE embedding IS NOT NULL AND embedding!=''`).get().c;
console.log(`\nfertig — ${total} Einträge haben jetzt ein Embedding.`);
