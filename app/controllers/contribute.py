"""Controller: POST /register, /contribute (5-Gate), /report, /flag."""
from fastapi import APIRouter, Header, HTTPException
from ..models import entry
from ..services import gates, embeddings
from ..views.schemas import ContributeIn, ReportIn, FlagIn, RegisterIn

router = APIRouter()


@router.post("/register")
def register(body: RegisterIn):
    return {"key": entry.create_key(body.name), "note": "für /contribute im Header: X-Key: <key>"}


@router.post("/contribute", status_code=201)
async def contribute(body: ContributeIn, x_key: str = Header(default=None)):
    if not entry.key_valid(x_key):
        raise HTTPException(status_code=401, detail="gültiger X-Key nötig (via POST /register, oder hp_test_key)")
    e = body.model_dump()
    gate = gates.run_gate(e)
    if not gate["ok"]:
        raise HTTPException(status_code=422, detail={"rejected": True, "stage": gate["stage"], "reason": gate["reason"]})
    e["id"] = e.get("id") or entry.new_id()
    e["tier"] = "unverified"
    row = entry.upsert(e)
    try:  # Embedding als Nebenprodukt; scheitert es, bleibt der Eintrag FTS-auffindbar
        vec = await embeddings.embed(embeddings.embed_text_for(e), kind="document")
        entry.set_embedding(row["id"], vec)
    except Exception:
        pass
    return {"ok": True, "id": row["id"], "sequence_no": row["sequence_no"], "tier": "unverified"}


@router.post("/report")
def report(body: ReportIn):
    if body.outcome not in ("worked", "failed"):
        raise HTTPException(status_code=400, detail="outcome muss worked|failed sein")
    if not entry.report(body.id, body.outcome):
        raise HTTPException(status_code=404, detail="id nicht gefunden")
    return {"ok": True}


@router.post("/flag")
def flag(body: FlagIn):
    res = entry.flag(body.id)
    if res is None:
        raise HTTPException(status_code=404, detail="id nicht gefunden")
    return {"ok": True, **res}
