"""Controller: POST /register, /contribute (5-Gate), /report, /flag."""
from fastapi import APIRouter, Header, HTTPException, Request
from ..models import entry
from ..services import gates, embeddings, ratelimit
from ..views.schemas import ContributeIn, ReportIn, FlagIn, RegisterIn
from ..config import RL_REGISTER, RL_CONTRIBUTE, RL_FEEDBACK

router = APIRouter()


def _limit(bucket: str, ident: str, cfg: tuple[int, float]):
    n, win = cfg
    if not ratelimit.allow(bucket, ident, n, win):
        raise HTTPException(status_code=429, detail=f"Rate-Limit: max {n} pro {int(win)}s. Kurz warten.")


@router.post("/register")
def register(request: Request, body: RegisterIn):
    _limit("register", ratelimit.client_ip(request), RL_REGISTER)
    return {"key": entry.create_key(body.name), "note": "für /contribute im Header: X-Key: <key>"}


@router.post("/contribute", status_code=201)
async def contribute(body: ContributeIn, x_key: str = Header(default=None)):
    if not entry.key_valid(x_key):
        raise HTTPException(status_code=401, detail="gültiger X-Key nötig (via POST /register, oder hp_test_key)")
    _limit("contribute", x_key, RL_CONTRIBUTE)
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
def report(request: Request, body: ReportIn):
    _limit("feedback", ratelimit.client_ip(request), RL_FEEDBACK)
    if body.outcome not in ("worked", "failed"):
        raise HTTPException(status_code=400, detail="outcome muss worked|failed sein")
    if not entry.report(body.id, body.outcome):
        raise HTTPException(status_code=404, detail="id nicht gefunden")
    return {"ok": True}


@router.post("/flag")
def flag(request: Request, body: FlagIn):
    _limit("feedback", ratelimit.client_ip(request), RL_FEEDBACK)
    res = entry.flag(body.id)
    if res is None:
        raise HTTPException(status_code=404, detail="id nicht gefunden")
    return {"ok": True, **res}
