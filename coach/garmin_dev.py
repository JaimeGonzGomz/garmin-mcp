"""Receptor para el programa Garmin Connect Developer (prueba con tu propia cuenta).

- GET  /garmin/callback        : destino de la redireccion OAuth; guarda code/state para el intercambio.
- POST /garmin/push/{token}    : Garmin envia aqui los datos (push). Se guarda cada cuerpo tal cual.
- GET  /logo.png               : imagen de marca (300x300) que pide el formulario de la app.

Los pushes se guardan en data/garmin_push/ (no se interpretan). summarize() lista solo tipos y nombres de
campo, nunca valores.
"""
import hmac
import json
import os
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from coach.db import DATA

router = APIRouter()
MAX_BODY = 2_000_000
DIR = DATA / "garmin_push"
LOGO = Path(__file__).resolve().parent / "assets" / "logo.png"


@router.get("/logo.png")
def logo():
    return FileResponse(LOGO, media_type="image/png")


@router.get("/garmin/callback", response_class=HTMLResponse)
def callback(request: Request):
    DIR.mkdir(parents=True, exist_ok=True)
    q = dict(request.query_params)
    (DIR / f"oauth-{int(time.time())}.json").write_text(json.dumps(q), encoding="utf-8")
    return "<!doctype html><meta charset=utf-8><title>Garmin</title><p>Conexion recibida. Puedes cerrar esta pestana.</p>"


@router.post("/garmin/push/{token}")
@router.post("/garmin/push/{token}/{kind}")
async def push(token: str, request: Request, kind: str = "x"):
    kind = "".join(c for c in kind if c.isalnum() or c in "-_")[:40] or "x"
    expected = os.environ.get("GARMIN_PUSH_TOKEN", "")
    if not expected or not hmac.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(404)
    body = await request.body()
    if len(body) > MAX_BODY:
        raise HTTPException(413)
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / f"push-{kind}-{time.time_ns()}.json").write_bytes(body)
    return {}


def summarize() -> dict:
    """Para cada fichero de push: claves de primer nivel y nombres de campo de sus elementos, sin valores."""
    out: dict = {}
    for p in sorted(DIR.glob("push-*.json")) if DIR.exists() else []:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            out.setdefault("(no json)", []).append(p.name)
            continue
        if isinstance(data, dict):
            for k, v in data.items():
                items = v if isinstance(v, list) else [v]
                fields = sorted({f for i in items if isinstance(i, dict) for f in i})
                o = out.setdefault(k, {"n": 0, "fields": set(), "_users": set(), "_t": [], "_recv": []})
                o["n"] += len(items)
                o["fields"].update(fields)
                o["_users"].update(str(i["userId"]) for i in items if isinstance(i, dict) and "userId" in i)
                o["_t"] += [i["startTimeInSeconds"] for i in items
                            if isinstance(i, dict) and isinstance(i.get("startTimeInSeconds"), int)]
                o["_recv"].append(int(p.stem.rsplit("-", 1)[-1]) / 1e9)
    from datetime import datetime, timezone
    day = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")
    for v in out.values():
        if isinstance(v, dict):
            v["fields"] = sorted(v["fields"])
            v["usuarios_distintos"] = len(v.pop("_users"))
            t, r = v.pop("_t"), v.pop("_recv")
            v["datos_desde_hasta"] = [day(min(t)), day(max(t))] if t else None
            v["recibido_desde_hasta"] = [day(min(r)), day(max(r))]
    return out


if __name__ == "__main__":
    import sys
    res = summarize()
    if "--brief" in sys.argv:
        for v in res.values():
            if isinstance(v, dict):
                v.pop("fields")
    print(json.dumps(res, indent=2, ensure_ascii=False))
