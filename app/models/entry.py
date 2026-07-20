"""Model: Repository für Einträge — CRUD + Hybrid-Suche (Vektor + Keyword, RRF)."""
import secrets
from .database import pool
from ..config import VEC_THRESHOLD, RRF_K, TIER_ORDER

_FIELDS = ("id", "tool", "version", "os", "tier", "problem", "context", "solution",
           "verification", "error_signature", "contributor", "model", "model_version",
           "env", "source", "worked", "failed")


def _vec_literal(vec) -> str:
    """pgvector-Textformat '[0.1,0.2,...]' — robust ohne Vector-Klasse."""
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


def new_id() -> str:
    return "kb_" + secrets.token_hex(3)


def upsert(e: dict) -> dict:
    data = {k: e.get(k) for k in _FIELDS}
    data["tier"] = data.get("tier") or "unverified"
    data["version"] = data.get("version") or "*"
    data["worked"] = e.get("worked", 0) or 0
    data["failed"] = e.get("failed", 0) or 0
    for k in _FIELDS:
        if data[k] is None:
            data[k] = "" if k not in ("worked", "failed") else 0
    with pool.connection() as conn:
        row = conn.execute("""
          INSERT INTO entries (id,tool,version,os,tier,problem,context,solution,verification,
                               error_signature,contributor,model,model_version,env,source,worked,failed)
          VALUES (%(id)s,%(tool)s,%(version)s,%(os)s,%(tier)s,%(problem)s,%(context)s,%(solution)s,
                  %(verification)s,%(error_signature)s,%(contributor)s,%(model)s,%(model_version)s,
                  %(env)s,%(source)s,%(worked)s,%(failed)s)
          ON CONFLICT (id) DO UPDATE SET
            tool=EXCLUDED.tool, version=EXCLUDED.version, os=EXCLUDED.os, tier=EXCLUDED.tier,
            problem=EXCLUDED.problem, context=EXCLUDED.context, solution=EXCLUDED.solution,
            verification=EXCLUDED.verification, error_signature=EXCLUDED.error_signature,
            contributor=EXCLUDED.contributor, model=EXCLUDED.model, model_version=EXCLUDED.model_version,
            env=EXCLUDED.env, source=EXCLUDED.source
          RETURNING id, sequence_no
        """, data).fetchone()
        conn.commit()
    return row


def set_embedding(id: str, vec: list):
    with pool.connection() as conn:
        conn.execute("UPDATE entries SET embedding=%s::vector WHERE id=%s", (_vec_literal(vec), id))
        conn.commit()


def get_by_id(id: str):
    with pool.connection() as conn:
        return conn.execute("SELECT * FROM entries WHERE id=%s AND status='active'", (id,)).fetchone()


def db_size() -> dict:
    with pool.connection() as conn:
        r = conn.execute(
            "SELECT count(*) AS total, "
            "count(*) FILTER (WHERE origin='seed') AS seed, "
            "count(*) FILTER (WHERE origin='external') AS external "
            "FROM entries WHERE status='active'").fetchone()
    return {"entries": r["total"], "seed": r["seed"], "external": r["external"]}


def create_key(name: str) -> str:
    key = "hp_" + secrets.token_hex(12)
    with pool.connection() as conn:
        conn.execute("INSERT INTO keys (key,name) VALUES (%s,%s)", (key, name))
        conn.commit()
    return key


def key_valid(key) -> bool:
    if not key:
        return False
    with pool.connection() as conn:
        return conn.execute("SELECT 1 FROM keys WHERE key=%s", (key,)).fetchone() is not None


def report(id: str, outcome: str) -> bool:
    col = "worked" if outcome == "worked" else "failed"
    with pool.connection() as conn:
        n = conn.execute(f"UPDATE entries SET {col}={col}+1 WHERE id=%s", (id,)).rowcount
        conn.commit()
    return n > 0


def flag(id: str, quarantine_at: int = 3):
    with pool.connection() as conn:
        n = conn.execute("UPDATE entries SET flags=flags+1 WHERE id=%s", (id,)).rowcount
        if not n:
            return None
        f = conn.execute("SELECT flags FROM entries WHERE id=%s", (id,)).fetchone()["flags"]
        if f >= quarantine_at:
            conn.execute("UPDATE entries SET status='quarantined' WHERE id=%s", (id,))
        conn.commit()
    return {"flags": f, "quarantined": f >= quarantine_at}


def _tool_match(req_tool: str, entry_tool: str) -> bool:
    if not req_tool or not entry_tool:
        return False
    a, b = req_tool.lower(), entry_tool.lower()
    return a in b or b in a


def search_hybrid(qtext: str, qvec, limit: int, tried: str, min_tier: str, req_tool: str = ""):
    """Vektor (pgvector, Threshold) + Keyword (tsvector), RRF-fusioniert, plus Tool-Match-Boost."""
    with pool.connection() as conn:
        vec_ids = []
        if qvec is not None:
            lit = _vec_literal(qvec)
            rows = conn.execute(
                "SELECT id, 1 - (embedding <=> %s::vector) AS sim FROM entries "
                "WHERE status='active' AND embedding IS NOT NULL "
                "ORDER BY embedding <=> %s::vector LIMIT 20", (lit, lit)).fetchall()
            vec_ids = [r["id"] for r in rows if r["sim"] >= VEC_THRESHOLD]
        kw_rows = conn.execute(
            "SELECT id FROM entries WHERE status='active' AND search_tsv @@ plainto_tsquery('english', %s) "
            "ORDER BY ts_rank(search_tsv, plainto_tsquery('english', %s)) DESC LIMIT 20",
            (qtext, qtext)).fetchall()
        kw_ids = [r["id"] for r in kw_rows]

        rank = {}
        for i, _id in enumerate(vec_ids):
            rank[_id] = rank.get(_id, 0.0) + 1.0 / (RRF_K + i)
        for i, _id in enumerate(kw_ids):
            rank[_id] = rank.get(_id, 0.0) + 1.0 / (RRF_K + i)
        if not rank:
            return [], []

        # Kandidaten-Zeilen einmal holen, dann Tool-Boost aufs Ranking
        cand = list(rank)
        rows = conn.execute("SELECT * FROM entries WHERE id = ANY(%s)", (cand,)).fetchall()
        by_id = {r["id"]: r for r in rows}
        boost = 1.0 / RRF_K  # Tool-Match ~= eine Rangposition höher
        for _id in cand:
            r = by_id.get(_id)
            if r and _tool_match(req_tool, r["tool"]):
                rank[_id] += boost
        fused = sorted(cand, key=lambda x: -rank[x])

        excluded, picked = [], []
        for _id in fused:
            r = by_id.get(_id)
            if not r:
                continue
            if tried and r["solution"] and tried.lower() in r["solution"].lower():
                excluded.append({"id": r["id"], "was": tried, "reason": "tried="})
                continue
            if min_tier and TIER_ORDER.get(r["tier"], 0) < TIER_ORDER.get(min_tier, 0):
                continue
            picked.append(r)
            if len(picked) >= limit:
                break
        for r in picked:
            conn.execute("UPDATE entries SET retrieval_count=retrieval_count+1 WHERE id=%s", (r["id"],))
        conn.commit()
    return picked, excluded
