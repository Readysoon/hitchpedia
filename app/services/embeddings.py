"""Service: Embeddings über lokales Ollama (kein API-Key, keine Cloud).

nomic-embed-text empfiehlt Task-Prefixe: 'search_query:' für Suchanfragen,
'search_document:' für gespeicherte Dokumente. Verbessert die Trennschärfe.
"""
import httpx
from ..config import OLLAMA_URL, EMBED_MODEL

_cache: dict[str, list[float]] = {}
_PREFIX = {"query": "search_query: ", "document": "search_document: "}


async def embed(text: str, kind: str = "query") -> list[float]:
    text = (text or "")[:2000]
    ck = f"{kind}|{text}"
    if ck in _cache:
        return _cache[ck]
    prompt = (_PREFIX.get(kind, "") + text) if EMBED_MODEL.startswith("nomic") else text
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": prompt})
        r.raise_for_status()
        vec = r.json()["embedding"]
    _cache[ck] = vec
    return vec


def embed_text_for(e: dict) -> str:
    """Retrieval-relevanter Text: Problem + Fehler-Signatur + Kontext (NICHT die lange Lösung)."""
    return " ".join(filter(None, [e.get("problem"), e.get("error_signature"), e.get("context")]))
