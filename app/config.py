"""Zentrale Konfiguration (via Env überschreibbar)."""
import os

DB_CONNINFO = os.getenv("HP_DB", "dbname=hitchpedia")
OLLAMA_URL = os.getenv("HP_OLLAMA_URL", "http://localhost:11434/api/embeddings")
EMBED_MODEL = os.getenv("HP_EMBED_MODEL", "nomic-embed-text")
EMBED_DIM = int(os.getenv("HP_EMBED_DIM", "768"))
BASE_URL = os.getenv("HP_BASE_URL", "http://localhost:8000")

VEC_THRESHOLD = float(os.getenv("HP_VEC_THRESHOLD", "0.55"))  # min. Cosine-Ähnlichkeit (nomic trennt besser)
RRF_K = 60                                                    # Reciprocal Rank Fusion Konstante
TIER_ORDER = {"synthetic": -1, "unverified": 0, "reproduced": 1, "canonical": 2}
