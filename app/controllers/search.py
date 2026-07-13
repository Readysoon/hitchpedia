"""Controller: GET /s (Hybrid-Suche -> schlanke Liste) und GET /e/{id} (voller Eintrag)."""
from fastapi import APIRouter, HTTPException
from ..models import entry
from ..services import embeddings
from ..views import schemas
from ..config import BASE_URL

router = APIRouter()


@router.get("/s")
async def search(q: str = "", tool: str = "", version: str = "", os: str = "",
                 error: str = "", tried: str = "", min_tier: str = "", limit: int = 3):
    qtext = f"{q} {error}".strip()
    if not qtext:
        raise HTTPException(status_code=400, detail="Parameter 'q' fehlt")
    limit = min(max(limit, 1), 20)

    qvec, mode = None, "fts-only"
    try:
        qvec = await embeddings.embed(qtext, kind="query")
        mode = "hybrid"
    except Exception:
        pass  # Ollama nicht erreichbar -> nur Keyword

    picked, excluded = entry.search_hybrid(qtext, qvec, limit, tried, min_tier, req_tool=tool)
    body = {
        "query": q,
        "mode": mode,
        "matched_env": {"tool": tool} if tool else None,
        "count": len(picked),
        "results": [schemas.list_item(r, tool) for r in picked],
        "excluded": excluded or None,
        "get_full": f"curl {BASE_URL}/e/<id>",
        "fallback_note": None if picked else "kein Treffer — hier würde v1 den LLM-Fallback starten (lokal nicht aktiv)",
        "db_size": entry.db_size(),
    }
    return {k: v for k, v in body.items() if v is not None}


@router.get("/e/{id}")
def get_entry(id: str):
    r = entry.get_by_id(id)
    if not r:
        raise HTTPException(status_code=404, detail="nicht gefunden")
    return schemas.full_entry(r)
