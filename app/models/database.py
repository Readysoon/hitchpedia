"""Model: Postgres-Verbindungspool + Schema (Postgres 17 + pgvector)."""
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
from ..config import DB_CONNINFO, EMBED_DIM


def _configure(conn):
    conn.row_factory = dict_row


# check=check_connection: jede Connection wird VOR dem Ausleihen geprüft und bei
# Bedarf ersetzt. Nötig, weil Neon (serverless) idle Verbindungen killt
# ("terminating connection due to administrator command") -> sonst 500 beim
# ersten Request nach Idle. max_idle recycelt Verbindungen, bevor Neon sie kappt.
pool = ConnectionPool(
    DB_CONNINFO, min_size=1, max_size=8, configure=_configure, open=False,
    check=ConnectionPool.check_connection, max_idle=120.0,
)

SCHEMA = f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS entries (
  id              TEXT PRIMARY KEY,
  sequence_no     BIGSERIAL,
  tool            TEXT DEFAULT '', version TEXT DEFAULT '*', os TEXT DEFAULT '',
  tier            TEXT DEFAULT 'unverified',
  status          TEXT DEFAULT 'active',                 -- active | quarantined
  problem         TEXT DEFAULT '', context TEXT DEFAULT '', solution TEXT DEFAULT '', verification TEXT DEFAULT '',
  error_signature TEXT DEFAULT '',
  contributor     TEXT DEFAULT '', model TEXT DEFAULT '', model_version TEXT DEFAULT '', env TEXT DEFAULT '', source TEXT DEFAULT '',
  worked INT DEFAULT 0, failed INT DEFAULT 0, flags INT DEFAULT 0, retrieval_count INT DEFAULT 0,
  created_at      TIMESTAMPTZ DEFAULT now(),
  embedding       vector({EMBED_DIM}),
  search_tsv      tsvector GENERATED ALWAYS AS (
    to_tsvector('english',
      coalesce(problem,'')||' '||coalesce(context,'')||' '||coalesce(solution,'')||' '||
      coalesce(error_signature,'')||' '||coalesce(tool,''))
  ) STORED
);
CREATE INDEX IF NOT EXISTS entries_tsv_idx ON entries USING gin (search_tsv);
CREATE INDEX IF NOT EXISTS entries_emb_idx ON entries USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS keys (
  key TEXT PRIMARY KEY, name TEXT DEFAULT '', created_at TIMESTAMPTZ DEFAULT now()
);
"""


def init():
    if pool.closed:
        pool.open()
    with pool.connection() as conn:
        conn.execute(SCHEMA)
        conn.commit()
