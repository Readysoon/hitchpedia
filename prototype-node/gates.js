// hitchpedia v1 — Write-Gate: deterministische Leak- & Injection-Checks (kein ML).
// Fängt das Offensichtliche; das eigentliche Netz ist "suggestion_only" beim Lesen.

// ── Leak-Scan: bekannte Secret-Muster + Entropie + PII ──
const SECRET_PATTERNS = [
  /\bAKIA[0-9A-Z]{16}\b/,                         // AWS Access Key
  /\bsk-ant-[a-zA-Z0-9_-]{20,}\b/,                // Anthropic
  /\bsk-[a-zA-Z0-9]{20,}\b/,                      // OpenAI-artig
  /\bghp_[a-zA-Z0-9]{30,}\b/,                     // GitHub PAT
  /\bxox[baprs]-[a-zA-Z0-9-]{10,}\b/,             // Slack
  /-----BEGIN [A-Z ]*PRIVATE KEY-----/,           // Private Key
  /\beyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b/, // JWT
];
const PII_PATTERNS = [
  /\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b/,     // E-Mail
  /\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))(?:\.\d{1,3}){1,3}\b/, // interne IP
];

function shannon(s) {
  const f = {}; for (const c of s) f[c] = (f[c] || 0) + 1;
  let h = 0; const n = s.length;
  for (const k in f) { const p = f[k] / n; h -= p * Math.log2(p); }
  return h;
}
function highEntropyToken(text) {
  for (const tok of text.split(/[\s"'`]+/)) {
    if (tok.length >= 24 && /^[A-Za-z0-9+/_=-]+$/.test(tok) && shannon(tok) > 4.2) return tok;
  }
  return null;
}

export function leakScan(text) {
  const findings = [];
  for (const re of SECRET_PATTERNS) if (re.test(text)) findings.push('secret');
  for (const re of PII_PATTERNS) if (re.test(text)) findings.push('pii');
  const ent = highEntropyToken(text);
  if (ent) findings.push('high-entropy');
  return { passed: findings.length === 0, findings };
}

// ── Injection-Scan: Anweisungs-Override, gefährliche Payloads, Exfil ──
const OVERRIDE = /\b(ignore (all |your )?(previous|prior|above) instructions|disregard the above|you are now|new instructions:|system:\s|print your (system )?prompt)\b/i;
const PAYLOAD  = /(curl|wget)\s+[^\n|]*\|\s*(bash|sh)\b|\brm\s+-rf\s+\/|\beval\s*\(|base64\s+-d\s*\|\s*(bash|sh)/i;
const EXFIL_SECRET = /(~\/\.ssh|\.env\b|id_rsa|credentials|\.aws\/)/i;
const EXFIL_NET    = /(https?:\/\/|nc\s|curl|wget|fetch\()/i;

export function injectionScan(text) {
  const flags = [];
  if (OVERRIDE.test(text)) flags.push('instruction-override');
  if (PAYLOAD.test(text))  flags.push('dangerous-payload');
  if (EXFIL_SECRET.test(text) && EXFIL_NET.test(text)) flags.push('exfil-pattern');
  // hart blocken bei Override / Payload+Exfil; einzelnes curl -> quarantäne
  let action = 'pass';
  if (flags.includes('instruction-override') || flags.includes('exfil-pattern')
      || flags.includes('dangerous-payload')) action = 'block';
  return { passed: action === 'pass', action, flags };
}

// ── Format-Check: strukturiert, nicht Freitext ──
export function formatCheck(e) {
  const bad = [];
  for (const f of ['problem', 'solution']) {
    if (!e[f] || String(e[f]).trim().length < 15) bad.push(f);
  }
  return { passed: bad.length === 0, missing: bad };
}

// Läuft die ganze Pipeline. Gibt {ok, reason} zurück.
export function runGate(e) {
  const blob = [e.problem, e.context, e.solution, e.verification, e.error_signature]
    .filter(Boolean).join('\n');
  const fmt = formatCheck(e);
  if (!fmt.passed) return { ok: false, stage: 'format', reason: `Pflichtfelder fehlen/zu kurz: ${fmt.missing.join(', ')}` };
  const leak = leakScan(blob);
  if (!leak.passed) return { ok: false, stage: 'leak', reason: `Leak erkannt: ${leak.findings.join(', ')} — bitte Secrets/PII entfernen & generalisieren` };
  const inj = injectionScan(blob);
  if (!inj.passed) return { ok: false, stage: 'injection', reason: `Injection erkannt: ${inj.flags.join(', ')}` };
  return { ok: true };
}
