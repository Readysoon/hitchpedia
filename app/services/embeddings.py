"""Service: Embeddings in-process via fastembed (ONNX, kein Server, kein API-Key).

nomic-embed-text-v1.5 nutzt Task-Prefixe: 'search_query:' für Suchanfragen,
'search_document:' für gespeicherte Dokumente.
"""
import asyncio
import threading
from ..config import EMBED_MODEL

_PREFIX = {"query": "search_query: ", "document": "search_document: "}
_model = None
_model_lock = threading.Lock()


def _get_model():
    # fastembed/onnxruntime wird LAZY importiert: der Import allein dauert ~15s
    # und würde sonst das Binden von uvicorn verzögern -> fly-proxy gibt beim
    # Cold-Start-Wake auf (~8s Geduld). So bindet die App in ~2-3s; der teure
    # Import + Modell-Load läuft im Hintergrund-Warmup bzw. beim ersten Search.
    # Double-checked Locking verhindert Doppel-Load (RAM-Peak -> OOM-Risiko).
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from fastembed import TextEmbedding
                _model = TextEmbedding(model_name=EMBED_MODEL)
    return _model


def _embed_sync(text: str, kind: str) -> list[float]:
    prompt = (_PREFIX.get(kind, "") + (text or ""))[:2000]
    vec = next(iter(_get_model().embed([prompt])))
    return [float(x) for x in vec]


async def embed(text: str, kind: str = "query") -> list[float]:
    # CPU-gebunden -> in Threadpool, damit der Event-Loop nicht blockiert
    return await asyncio.to_thread(_embed_sync, text, kind)


def embed_sync(text: str, kind: str = "document") -> list[float]:
    return _embed_sync(text, kind)


def embed_text_for(e: dict) -> str:
    """Retrieval-relevanter Text: Problem + Fehler-Signatur + Kontext (NICHT die lange Lösung)."""
    return " ".join(filter(None, [e.get("problem"), e.get("error_signature"), e.get("context")]))


def warmup():
    """Modell beim Start laden, damit der erste Request nicht langsam ist."""
    _get_model()
