"""Service: In-Memory Rate-Limit (Sliding Window).

Bewusst simpel für die Single-Machine-Deployment (min_machines_running=1).
Bei Scale-out (mehrere Maschinen) müsste der State geteilt werden (Redis o.ä.);
für den 0-100-Agenten-Bereich reicht das und braucht keine Infra.
"""
import time
import threading
from collections import defaultdict
from fastapi import Request

_hits: dict[str, list[float]] = defaultdict(list)
_lock = threading.Lock()


def allow(bucket: str, ident: str, limit: int, window: float) -> bool:
    """False, wenn im Zeitfenster `window` bereits `limit` Treffer für
    (bucket, ident) vorliegen. Sonst True und der Treffer wird gezählt."""
    k = f"{bucket}:{ident}"
    now = time.time()
    cutoff = now - window
    with _lock:
        slot = _hits[k]
        slot[:] = [t for t in slot if t > cutoff]  # alte Treffer verwerfen
        if len(slot) >= limit:
            return False
        slot.append(now)
        return True


def client_ip(request: Request) -> str:
    """Echte Client-IP hinter fly-proxy: Fly-Client-IP zuerst (request.client
    wäre nur der Proxy), dann X-Forwarded-For, dann Peer-IP."""
    return (
        request.headers.get("fly-client-ip")
        or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
