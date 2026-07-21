"""Service: Write-Gate — deterministische Leak- & Injection-Checks (kein ML)."""
import re
import math
from collections import Counter

# ── Leak: bekannte Secret-Muster (hohe Präzision, spezifische Formate) ──
_SECRET = [
    re.compile(r"\bA(?:KIA|SIA)[0-9A-Z]{16}\b"),                        # AWS access key id (perm/temp)
    re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}\b"),            # OpenAI / Anthropic keys
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),                      # GitHub tokens (ghp/gho/ghu/ghs/ghr)
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),                    # GitHub fine-grained PAT
    re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),                        # GitLab PAT
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),                           # Google API key
    re.compile(r"\b(?:sk|pk|rk)_live_[0-9A-Za-z]{20,}\b"),             # Stripe live keys
    re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"),                            # npm token
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),                    # Slack token
    re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/]+"),    # Slack webhook
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),                 # private key block
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),  # JWT
]
# Secret als Zuweisung (password=…, api_key: …) — Wert wird gegen Platzhalter geprüft
_ASSIGN = re.compile(
    r"(?i)\b(?:pass(?:word|wd)?|secret|api[_-]?key|access[_-]?token|auth[_-]?token|"
    r"client[_-]?secret|private[_-]?key)\s*[:=]\s*[\"']?([^\s\"';,]{8,})")
# Zugangsdaten in einer Connection-URL: scheme://user:LANGES_PASSWORT@host
_CONN_CREDS = re.compile(r"\b[a-z][a-z0-9+.\-]*://[^\s:/@]+:([^\s:/@]{8,})@")
# Absolute Home-Pfade verraten Username/Maschine (macOS/Windows)
_HOME_PATH = re.compile(r"/Users/[^/\s<]{2,}/|[A-Za-z]:\\Users\\[^\\\s<]{2,}")
# offensichtliche Platzhalter zählen NICHT als Secret
_PLACEHOLDER = re.compile(
    r"^(?:<|\$|\{|%|xxx+|\*{2,}|\.\.\.|your[-_]?|my[-_]?|example|changeme|placeholder|"
    r"redacted|password|secret|none|null|todo)", re.I)

# E-Mail = PII — aber Allow-List für ur-häufige Nicht-PII-Hosts (Fix des früheren git@github.com-False-Positives)
_EMAIL = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
_EMAIL_ALLOW = re.compile(r"^(git|noreply|no-reply)@(github\.com|gitlab\.com|bitbucket\.org)$", re.I)
_INTERNAL_IP = re.compile(r"\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))(?:\.\d{1,3}){1,3}\b")


def _shannon(s: str) -> float:
    if not s:
        return 0.0
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in Counter(s).values())


def _high_entropy(text: str):
    # Nur zusammenhängende Alphanumerik-Läufe prüfen. Echte Secrets sind lange
    # separatorfreie Zeichenketten; strukturierte Technik-Bezeichner (env-vars,
    # Bindestrich-/Slash-Komposita, Pfade wie 'TIKTOKEN_CACHE_DIR=/app/...' oder
    # 'PowerShell-Escape/Expansion-Semantik') werden vorher an ihren Trennern
    # zerlegt und fallen damit unter die Längen-/Entropie-Schwelle.
    for tok in re.split(r"[\s\"'`/_+=.-]+", text):
        if len(tok) >= 24 and re.fullmatch(r"[A-Za-z0-9]+", tok) and _shannon(tok) > 4.2:
            return tok
    return None


def leak_scan(text: str) -> dict:
    findings = []
    if any(rx.search(text) for rx in _SECRET):
        findings.append("secret")
    # Secret-Zuweisung / Connection-Creds — nur wenn der Wert KEIN Platzhalter ist
    if any(not _PLACEHOLDER.match(m.group(1)) for m in _ASSIGN.finditer(text)):
        findings.append("secret")
    if any(not _PLACEHOLDER.match(m.group(1)) for m in _CONN_CREDS.finditer(text)):
        findings.append("secret")
    for m in _EMAIL.finditer(text):
        if not _EMAIL_ALLOW.match(m.group(0)):
            findings.append("pii")
            break
    if _INTERNAL_IP.search(text):
        findings.append("pii-ip")
    if _HOME_PATH.search(text):
        findings.append("internal-path")
    if _high_entropy(text):
        findings.append("high-entropy")
    return {"passed": not findings, "findings": sorted(set(findings))}


# ── Injection: Override, gefährliche Payloads, Exfil ──
_OVERRIDE = re.compile(
    r"\b(ignore (all |your )?(previous|prior|above) instructions|disregard the above|"
    r"you are now|new instructions:|print your (system )?prompt)\b", re.I)
_PAYLOAD = re.compile(
    r"(curl|wget)\s+[^\n|]*\|\s*(bash|sh)\b|\brm\s+-rf\s+/|\beval\s*\(|"
    r"base64\s+-d\s*\|\s*(bash|sh)", re.I)
_EXFIL_SECRET = re.compile(r"(~/\.ssh|\.env\b|id_rsa|\.aws/)", re.I)  # 'credentials' entfernt: zu häufiges Alltagswort (CORS/DB/Auth)
_EXFIL_NET = re.compile(r"(https?://|nc\s|curl|wget|fetch\()", re.I)


def injection_scan(text: str) -> dict:
    flags = []
    if _OVERRIDE.search(text):
        flags.append("instruction-override")
    if _PAYLOAD.search(text):
        flags.append("dangerous-payload")
    # Exfil nur flaggen, wenn Secret-Pfad UND Netz-Aufruf in DERSELBEN Zeile
    # stehen (echtes Muster: 'curl … $(cat ~/.ssh/id_rsa)'). Verhindert
    # False-Positives, wenn z.B. '.env' und eine URL nur zufällig im selben
    # Text (aber unterschiedlichen Absätzen) vorkommen.
    if any(_EXFIL_SECRET.search(ln) and _EXFIL_NET.search(ln) for ln in text.splitlines()):
        flags.append("exfil-pattern")
    return {"passed": not flags, "flags": flags}


def format_check(e: dict) -> dict:
    missing = [f for f in ("problem", "solution")
               if len((e.get(f) or "").strip()) < 15]
    return {"passed": not missing, "missing": missing}


def run_gate(e: dict) -> dict:
    """Format -> Leak -> Injection. Gibt {ok, stage?, reason?}."""
    blob = "\n".join(filter(None, [e.get("problem"), e.get("context"),
                                   e.get("solution"), e.get("verification"),
                                   e.get("error_signature")]))
    fmt = format_check(e)
    if not fmt["passed"]:
        return {"ok": False, "stage": "format",
                "reason": f"Pflichtfelder fehlen/zu kurz: {', '.join(fmt['missing'])}"}
    leak = leak_scan(blob)
    if not leak["passed"]:
        return {"ok": False, "stage": "leak",
                "reason": f"Leak erkannt: {', '.join(leak['findings'])} — bitte Secrets/PII entfernen & generalisieren"}
    inj = injection_scan(blob)
    if not inj["passed"]:
        return {"ok": False, "stage": "injection",
                "reason": f"Injection erkannt: {', '.join(inj['flags'])}"}
    return {"ok": True}
