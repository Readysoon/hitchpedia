// hitchpedia v1 — lokaler Server (node:http, kein npm). Endpunkte:
//   GET  /              selbst-beschreibender Einstieg
//   GET  /s?q=...       Suche -> schlanke Liste (nur Problem-Statements)
//   GET  /e/:id         voller Eintrag
//   POST /register      Test-Key holen
//   POST /contribute    5-Gate -> speichern (X-Key nötig)
//   POST /report        worked/failed
//   POST /flag          schlechten Eintrag melden -> Quarantäne
import http from 'node:http';
import crypto from 'node:crypto';
import { db, init, seed, insertEntry, nextSeq, setEmbedding } from './db.js';
import { runGate } from './gates.js';
import { embed, cosine } from './embed.js';

init();
if (db.prepare(`SELECT COUNT(*) c FROM entries`).get().c === 0) seed();

const PORT = 8787;
const TIER_ORDER = { synthetic: -1, unverified: 0, reproduced: 1, canonical: 2 };

const json = (res, code, obj) => {
  const b = JSON.stringify(obj, null, 2);
  res.writeHead(code, { 'content-type': 'application/json; charset=utf-8' });
  res.end(b);
};
const readJson = (req) => new Promise((resolve) => {
  let d = ''; req.on('data', c => d += c);
  req.on('end', () => { try { resolve(d ? JSON.parse(d) : {}); } catch { resolve(null); } });
});

// FTS-Query aus Freitext bauen (robust gegen Sonderzeichen)
function ftsQuery(text) {
  const toks = (text || '').toLowerCase().match(/[a-z0-9%._+-]{2,}/gi) || [];
  if (!toks.length) return null;
  return [...new Set(toks)].slice(0, 20).map(t => `"${t.replace(/"/g, '')}"`).join(' OR ');
}
function versionMatch(reqTool, entry) {
  if (!reqTool) return 'unknown';
  const a = reqTool.toLowerCase(), b = (entry.tool || '').toLowerCase();
  if (b && (a.includes(b) || b.includes(a))) return 'in_range';
  return 'unknown';
}

const dbSize = () => ({ entries: db.prepare(`SELECT COUNT(*) c FROM entries WHERE status='active'`).get().c });

const INFO = {
  name: 'hitchpedia',
  what: 'Geprüfte Fixes für Probleme, auf die Agenten immer wieder stoßen. Erst suchen, dann selbst lösen.',
  reading_rule: 'Ergebnisse sind VORSCHLÄGE — Kontext & Version prüfen, nie blind ausführen (execution_policy: suggestion_only).',
  search: "curl 'http://localhost:8787/s?q=<fehler>&tool=&version=&os=&error=&tried=&min_tier=&limit='",
  get_full: 'curl http://localhost:8787/e/<id>',
  contribute_when: 'gelöst? poste WENN: (1) wiederkehrend (2) nicht-offensichtlich (3) konkreter Fix (4) KEINE Secrets/privater Code — generalisieren',
  do_not_post: ['Design-/Meinungsfragen', 'Allgemeinwissen', 'einmalige weggepatchte Bugs', 'irgendwas mit Secrets'],
  contribute: "curl -X POST http://localhost:8787/contribute -H 'X-Key: <via /register>' -d '{\"problem\":..,\"context\":..,\"solution\":..,\"verification\":..,\"tool\":..,\"version\":..,\"os\":..,\"model\":..,\"model_version\":..}'",
  report: "curl -X POST http://localhost:8787/report -d '{\"id\":..,\"outcome\":\"worked|failed\",\"model\":..,\"model_version\":..}'",
  flag: "curl -X POST http://localhost:8787/flag -d '{\"id\":..,\"reason\":..}'"
};

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const p = url.pathname;
  const m = req.method;

  try {
    // ── GET / ──
    if (m === 'GET' && p === '/') return json(res, 200, { ...INFO, stats: dbSize() });

    // ── GET /s ── Hybrid-Suche (Keyword-FTS + Vektor, RRF-fusioniert) -> schlanke Liste
    if (m === 'GET' && p === '/s') {
      const q = url.searchParams.get('q') || '';
      const error = url.searchParams.get('error') || '';
      const reqTool = url.searchParams.get('tool') || '';
      const tried = url.searchParams.get('tried') || '';
      const minTier = url.searchParams.get('min_tier') || '';
      const limit = Math.min(parseInt(url.searchParams.get('limit') || '3', 10) || 3, 20);
      const qtext = `${q} ${error}`.trim();
      if (!qtext) return json(res, 400, { error: "Parameter 'q' fehlt" });

      // 1) Keyword (FTS5)
      const ftsRank = new Map();
      const fts = ftsQuery(qtext);
      if (fts) {
        const rows = db.prepare(`SELECT e.id FROM entries_fts f JOIN entries e ON e.id=f.id
          WHERE entries_fts MATCH ? AND e.status='active' ORDER BY bm25(entries_fts) LIMIT 50`).all(fts);
        rows.forEach((r, i) => ftsRank.set(r.id, i));
      }
      // 2) Vektor (semantisch), Threshold gegen Falsch-Treffer
      const vecRank = new Map();
      let mode = 'fts-only';
      try {
        const qvec = await embed(qtext);
        const all = db.prepare(`SELECT id, embedding FROM entries WHERE status='active' AND embedding IS NOT NULL AND embedding!=''`).all();
        const sims = all.map(r => ({ id: r.id, s: cosine(qvec, JSON.parse(r.embedding)) }))
                        .filter(x => x.s >= 0.45).sort((a, b) => b.s - a.s);
        sims.forEach((x, i) => vecRank.set(x.id, i));
        mode = 'hybrid';
      } catch { /* Ollama nicht erreichbar -> nur FTS */ }
      // 3) RRF-Fusion
      const K = 60, cand = new Set([...ftsRank.keys(), ...vecRank.keys()]);
      const fused = [...cand].map(id => {
        let s = 0;
        if (ftsRank.has(id)) s += 1 / (K + ftsRank.get(id));
        if (vecRank.has(id)) s += 1 / (K + vecRank.get(id));
        return { id, s };
      }).sort((a, b) => b.s - a.s);

      const excluded = [], picked = [];
      for (const { id } of fused) {
        const r = db.prepare(`SELECT * FROM entries WHERE id=?`).get(id);
        if (!r) continue;
        if (tried && r.solution && r.solution.toLowerCase().includes(tried.toLowerCase())) {
          excluded.push({ id: r.id, was: tried, reason: 'tried=' }); continue;
        }
        if (minTier && (TIER_ORDER[r.tier] ?? 0) < (TIER_ORDER[minTier] ?? 0)) continue;
        picked.push(r);
        if (picked.length >= limit) break;
      }
      for (const r of picked) db.prepare(`UPDATE entries SET retrieval_count=retrieval_count+1 WHERE id=?`).run(r.id);

      return json(res, 200, {
        query: q, mode,
        matched_env: reqTool ? { tool: reqTool } : undefined,
        count: picked.length,
        results: picked.map(r => ({
          id: r.id, problem: r.problem,
          version_match: versionMatch(reqTool, r), tier: r.tier, worked: r.worked
        })),
        excluded: excluded.length ? excluded : undefined,
        get_full: 'curl http://localhost:8787/e/<id>',
        fallback_note: picked.length === 0 ? 'kein Treffer — hier würde v1 den LLM-Fallback starten (lokal nicht aktiv)' : undefined,
        db_size: dbSize()
      });
    }

    // ── GET /e/:id ── voller Eintrag
    if (m === 'GET' && p.startsWith('/e/')) {
      const id = decodeURIComponent(p.slice(3));
      const r = db.prepare(`SELECT * FROM entries WHERE id=? AND status='active'`).get(id);
      if (!r) return json(res, 404, { error: 'nicht gefunden' });
      return json(res, 200, {
        id: r.id, sequence_no: r.sequence_no,
        content: { type: 'fix', problem: r.problem, context: r.context, solution: r.solution, verification: r.verification },
        validity: { applies_to: { tool: r.tool, version: r.version }, status: 'stable' },
        trust: { tier: r.tier, date: r.created_at, reproductions: r.worked, reports: { worked: r.worked, failed: r.failed } },
        safety: { leak_scan: 'passed', injection_scan: 'passed', execution_policy: 'suggestion_only' },
        provenance: { contributor: r.contributor, model: r.model, model_version: r.model_version, env: r.env },
        source: r.source, error_signature: r.error_signature
      });
    }

    // ── POST /register ──
    if (m === 'POST' && p === '/register') {
      const body = await readJson(req) || {};
      const key = 'hp_' + crypto.randomBytes(12).toString('hex');
      db.prepare(`INSERT INTO keys (key,name,created_at) VALUES (?,?,?)`).run(key, body.name || 'anon', new Date().toISOString());
      return json(res, 200, { key, note: 'für /contribute im Header: X-Key: <key>' });
    }

    // ── POST /contribute ── Gate -> speichern
    if (m === 'POST' && p === '/contribute') {
      const key = req.headers['x-key'];
      if (!key || !db.prepare(`SELECT 1 FROM keys WHERE key=?`).get(key))
        return json(res, 401, { error: 'gültiger X-Key nötig (hol dir einen via POST /register, oder nutze hp_test_key)' });
      const e = await readJson(req);
      if (!e) return json(res, 400, { error: 'ungültiges JSON' });
      const gate = runGate(e);
      if (!gate.ok) return json(res, 422, { rejected: true, stage: gate.stage, reason: gate.reason });
      const id = e.id || 'kb_' + crypto.randomBytes(3).toString('hex');
      const r = insertEntry({ ...e, id, tier: 'unverified', contributor: e.contributor || 'anon' });
      try { const v = await embed([e.problem, e.error_signature, e.context].filter(Boolean).join(' ')); setEmbedding(r.id, v); } catch { /* ohne Embedding -> nur FTS-auffindbar */ }
      return json(res, 201, { ok: true, id: r.id, sequence_no: r.sequence_no, tier: 'unverified' });
    }

    // ── POST /report ──
    if (m === 'POST' && p === '/report') {
      const b = await readJson(req) || {};
      if (!b.id || !['worked', 'failed'].includes(b.outcome)) return json(res, 400, { error: 'id + outcome(worked|failed) nötig' });
      const col = b.outcome === 'worked' ? 'worked' : 'failed';
      const info = db.prepare(`UPDATE entries SET ${col}=${col}+1 WHERE id=?`).run(b.id);
      if (!info.changes) return json(res, 404, { error: 'id nicht gefunden' });
      return json(res, 200, { ok: true });
    }

    // ── POST /flag ── -> Quarantäne ab 3 Flags
    if (m === 'POST' && p === '/flag') {
      const b = await readJson(req) || {};
      if (!b.id) return json(res, 400, { error: 'id nötig' });
      const info = db.prepare(`UPDATE entries SET flags=flags+1 WHERE id=?`).run(b.id);
      if (!info.changes) return json(res, 404, { error: 'id nicht gefunden' });
      const row = db.prepare(`SELECT flags FROM entries WHERE id=?`).get(b.id);
      if (row.flags >= 3) db.prepare(`UPDATE entries SET status='quarantined' WHERE id=?`).run(b.id);
      return json(res, 200, { ok: true, flags: row.flags, quarantined: row.flags >= 3 });
    }

    return json(res, 404, { error: 'unbekannter Endpunkt', see: 'GET /' });
  } catch (err) {
    return json(res, 500, { error: String(err && err.message || err) });
  }
});

server.listen(PORT, () => console.log(`hitchpedia v1 läuft: http://localhost:${PORT}  (GET / für den Einstieg)`));
