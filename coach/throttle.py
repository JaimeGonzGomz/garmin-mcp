"""Limite de intentos de contrasena fallidos (en memoria): 5 por IP y 30 en total cada 15 min."""
import time

FAILS: dict[str, list[float]] = {}
WINDOW, PER_IP, GLOBAL = 900, 5, 30


def throttled(ip: str) -> bool:
    now = time.time()
    for k in list(FAILS):
        FAILS[k] = [t for t in FAILS[k] if now - t < WINDOW]
        if not FAILS[k]:
            del FAILS[k]
    return len(FAILS.get(ip, [])) >= PER_IP or sum(map(len, FAILS.values())) >= GLOBAL


def fail(ip: str) -> None:
    FAILS.setdefault(ip, []).append(time.time())


def client_ip(request) -> str:
    return request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "?")
