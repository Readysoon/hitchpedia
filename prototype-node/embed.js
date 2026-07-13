// Embeddings über lokales Ollama (all-minilm, 384-dim, kein API-Key).
// Produktion später: pgvector + ein Embedding-Dienst; hier: brute-force Cosine in JS (bei wenigen Einträgen völlig ok).
const OLLAMA = 'http://localhost:11434/api/embeddings';
const MODEL = process.env.HP_EMBED_MODEL || 'all-minilm';
const cache = new Map();

export async function embed(text) {
  const key = (text || '').slice(0, 400);
  if (cache.has(key)) return cache.get(key);
  const res = await fetch(OLLAMA, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ model: MODEL, prompt: (text || '').slice(0, 800) }) // all-minilm: ~256 Token Kontext
  });
  if (!res.ok) throw new Error('embed failed: ' + res.status);
  const d = await res.json();
  cache.set(key, d.embedding);
  return d.embedding;
}

export function cosine(a, b) {
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) { dot += a[i] * b[i]; na += a[i] * a[i]; nb += b[i] * b[i]; }
  return dot / (Math.sqrt(na) * Math.sqrt(nb) || 1);
}
