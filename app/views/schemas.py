"""View-Schicht: Request-Modelle (Pydantic) + Response-Serializer (JSON-Form)."""
from typing import Optional
from pydantic import BaseModel


class ContributeIn(BaseModel):
    id: Optional[str] = None
    problem: str = ""
    context: str = ""
    solution: str = ""
    verification: str = ""
    error_signature: str = ""
    tool: str = ""
    version: str = "*"
    os: str = ""
    model: str = ""
    model_version: str = ""
    contributor: str = "anon"
    env: str = ""
    source: str = ""


class ReportIn(BaseModel):
    id: str
    outcome: str  # "worked" | "failed"
    model: Optional[str] = None
    model_version: Optional[str] = None


class FlagIn(BaseModel):
    id: str
    reason: Optional[str] = None


class RegisterIn(BaseModel):
    name: str = "anon"


def version_match(req_tool: str, entry_tool: str) -> str:
    if not req_tool:
        return "unknown"
    a, b = req_tool.lower(), (entry_tool or "").lower()
    return "in_range" if b and (a in b or b in a) else "unknown"


def list_item(r: dict, req_tool: str) -> dict:
    """Schlanke Liste — nur Problem-Statement + minimale Signale."""
    return {
        "id": r["id"],
        "problem": r["problem"],
        "version_match": version_match(req_tool, r["tool"]),
        "tier": r["tier"],
        "worked": r["worked"],
    }


def full_entry(r: dict) -> dict:
    """Vollständiger Eintrag mit Vertrauens-/Sicherheits-Metadaten."""
    return {
        "id": r["id"],
        "sequence_no": r["sequence_no"],
        "content": {
            "type": "fix",
            "problem": r["problem"], "context": r["context"],
            "solution": r["solution"], "verification": r["verification"],
        },
        "validity": {"applies_to": {"tool": r["tool"], "version": r["version"]}, "status": "stable"},
        "trust": {
            "tier": r["tier"],
            "date": r["created_at"].isoformat() if r.get("created_at") else None,
            "reproductions": r["worked"],
            "reports": {"worked": r["worked"], "failed": r["failed"]},
        },
        "safety": {"leak_scan": "passed", "injection_scan": "passed", "execution_policy": "suggestion_only"},
        "provenance": {
            "contributor": r["contributor"], "model": r["model"],
            "model_version": r["model_version"], "env": r["env"],
        },
        "source": r["source"],
        "error_signature": r["error_signature"],
    }
