"""Service: Write-Gate — deterministische Leak- & Injection-Checks (kein ML)."""
import re
import math
from collections import Counter

# ── Leak: bekannte Secret-Muster ──
_SECRET = [
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-ant-[a-zA-Z0-9_-]{20,}\b"),
    re.compile(r"\bsk-[a-zA-Z0-9]{20,}\b"),
    re.compile(r"\bghp_[a-zA-Z0-9]{30,}\b"),
    re.compile(r"\bxox[baprs]-[a-zA-Z0-9-]{10,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\beyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b"),
]
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
    for tok in re.split(r"[\s\"'`]+", text):
        if len(tok) >= 24 and re.fullmatch(r"[A-Za-z0-9+/_=-]+", tok) and _shannon(tok) > 4.2:
            return tok
    return None


def leak_scan(text: str) -> dict:
    findings = []
    if any(rx.search(text) for rx in _SECRET):
        findings.append("secret")
    for m in _EMAIL.finditer(text):
        if not _EMAIL_ALLOW.match(m.group(0)):
            findings.append("pii")
            break
    if _INTERNAL_IP.search(text):
        findings.append("pii-ip")
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
_EXFIL_SECRET = re.compile(r"(~/\.ssh|\.env\b|id_rsa|credentials|\.aws/)", re.I)
_EXFIL_NET = re.compile(r"(https?://|nc\s|curl|wget|fetch\()", re.I)


def injection_scan(text: str) -> dict:
    flags = []
    if _OVERRIDE.search(text):
        flags.append("instruction-override")
    if _PAYLOAD.search(text):
        flags.append("dangerous-payload")
    if _EXFIL_SECRET.search(text) and _EXFIL_NET.search(text):
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
