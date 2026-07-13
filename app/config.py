"""Zentrale Konfiguration (via Env überschreibbar)."""
import os

# Neon in Prod (DATABASE_URL), lokal Fallback auf lokales Postgres
DB_CONNINFO = os.getenv("DATABASE_URL") or os.getenv("HP_DB", "dbname=hitchpedia")
EMBED_MODEL = os.getenv("HP_EMBED_MODEL", "nomic-ai/nomic-embed-text-v1.5")  # fastembed (in-process, kein Server/Key)
EMBED_DIM = int(os.getenv("HP_EMBED_DIM", "768"))
BASE_URL = os.getenv("HP_BASE_URL", "http://localhost:8000")

VEC_THRESHOLD = float(os.getenv("HP_VEC_THRESHOLD", "0.55"))  # min. Cosine-Ähnlichkeit (nomic trennt besser)
RRF_K = 60                                                    # Reciprocal Rank Fusion Konstante
TIER_ORDER = {"synthetic": -1, "unverified": 0, "reproduced": 1, "canonical": 2}

# Rate-Limits (In-App, Sliding Window). Format: (max_treffer, fenster_sekunden).
RL_REGISTER = (int(os.getenv("HP_RL_REGISTER_N", "5")), float(os.getenv("HP_RL_REGISTER_WIN", "3600")))       # pro IP  -> verhindert Key-Massen-Ziehen
RL_CONTRIBUTE = (int(os.getenv("HP_RL_CONTRIBUTE_N", "10")), float(os.getenv("HP_RL_CONTRIBUTE_WIN", "60")))  # pro Key -> fängt Loop-Agenten
RL_FEEDBACK = (int(os.getenv("HP_RL_FEEDBACK_N", "30")), float(os.getenv("HP_RL_FEEDBACK_WIN", "60")))        # pro IP  -> Backstop für report+flag
