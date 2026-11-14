"""Web del coach (FastAPI). Un usuario, contrasena en COACH_PASSWORD."""
import hmac
import json
import os
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from coach import garmin_dev, legal, oauth
from coach.mcp_app import mcp
from coach.snapshot import build_snapshot
from coach.throttle import client_ip, fail, throttled
from coach.db import DATA, conn, get_extra, get_settings
from coach.estado import calcular
from coach.digest import activity_digest, calendar_digest, day_digest, plan_info, plan_tasks, weekly_volume

@asynccontextmanager
async def lifespan(_app):
    async with mcp.session_manager.run():
        yield


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)  # no publicar el mapa de la API


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.update({
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
                                   "img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        "Strict-Transport-Security": "max-age=31536000",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Cache-Control": resp.headers.get("Cache-Control", "no-store"),
    })
    return resp


app.add_middleware(SessionMiddleware, secret_key=os.environ["SESSION_SECRET"], max_age=60 * 60 * 24 * 30,
                   https_only=os.getenv("COACH_INSECURE_COOKIES") != "1")
app.include_router(legal.router)
app.include_router(oauth.router)
app.include_router(garmin_dev.router)
# Conector MCP remoto: /mcp (protegido con OAuth) y los endpoints OAuth (/authorize, /token, /register, /.well-known/...)
_mcp = mcp.streamable_http_app()
app.router.routes.extend(_mcp.routes)
for _m in reversed(_mcp.user_middleware):  # autenticacion Bearer del MCP (solo marca el usuario; /mcp la exige)
    app.add_middleware(_m.cls, **_m.kwargs)
STATIC = Path(__file__).parent / "static"
LOCK = DATA / "refresh.lock"
ROOT = Path(__file__).resolve().parent.parent


class Login(BaseModel):
    password: str


class Note(BaseModel):
    text: str
    day: str | None = None


class Text(BaseModel):
    text: str


def auth(request: Request) -> None:
    if not request.session.get("ok"):
        raise HTTPException(401)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.post("/api/login")
def login(body: Login, request: Request):
    ip = client_ip(request)
    if throttled(ip):
        raise HTTPException(429, "Demasiados intentos; espera unos minutos")
    if not hmac.compare_digest(body.password.encode(), os.environ["COACH_PASSWORD"].encode()):
        fail(ip)
        raise HTTPException(401, "Contrasena incorrecta")
    request.session["ok"] = True
    return {"ok": True}


@app.post("/api/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


def refreshing() -> bool:
    if not LOCK.exists():
        return False
    if time.time() - LOCK.stat().st_mtime > 900:  # bloqueo viejo
        LOCK.unlink(missing_ok=True)
        return False
    return True


@app.get("/api/data", dependencies=[Depends(auth)])
def data():
    return build_snapshot(refreshing())


@app.post("/api/settings", dependencies=[Depends(auth)])
def save_settings(body: dict):
    db = conn()
    for k in ("goal_name", "goal_date", "days_week", "context", "milestones", "history", "hr_max", "hr_recovery", "hr_long", "hr_easy", "zonas_fuente", "auto_send"):
        if k in body:
            db.execute("insert or replace into settings values (?, ?)", (k, str(body[k])))
    db.commit()
    return {"ok": True}


@app.post("/api/notes", dependencies=[Depends(auth)])
def add_note(n: Note):
    if not n.text.strip():
        raise HTTPException(400, "Nota vacia")
    db = conn()
    db.execute("insert into log (day, kind, text) values (?, 'nota', ?)", (n.day or date.today().isoformat(), n.text.strip()))
    db.commit()
    return {"ok": True}


@app.post("/api/import_log", dependencies=[Depends(auth)])
def import_log(t: Text):
    """Guarda un bloque de texto (log antiguo) como una entrada 'import' por cada linea no vacia."""
    db = conn()
    n = 0
    for line in t.text.splitlines():
        if line.strip():
            db.execute("insert into log (day, kind, text) values (?, 'import', ?)", (None, line.strip()))
            n += 1
    db.commit()
    return {"ok": True, "lineas": n}


@app.post("/api/refresh", dependencies=[Depends(auth)])
def refresh():
    if refreshing():
        return {"ok": True, "refreshing": True}
    DATA.mkdir(parents=True, exist_ok=True)
    LOCK.write_text(str(time.time()))
    py = sys.executable
    cmd = f'"{py}" -m coach.sync 7 ; "{py}" -m coach.recommend ; rm -f "{LOCK}"'
    subprocess.Popen(["/bin/sh", "-c", cmd], cwd=ROOT, env=os.environ.copy(),
                     stdout=open(DATA / "refresh.log", "w"), stderr=subprocess.STDOUT, start_new_session=True)
    return {"ok": True, "refreshing": True}


@app.get("/api/refresh_log", dependencies=[Depends(auth)])
def refresh_log():
    p = DATA / "refresh.log"
    return {"log": p.read_text()[-3000:] if p.exists() else ""}


def _today_workout(db):
    day = date.today().isoformat()
    rec = db.execute("select data from reco where day = ?", (day,)).fetchone()
    if not rec:
        raise HTTPException(400, "No hay recomendacion de hoy; pulsa 'Actualizar ahora'.")
    return day, json.loads(rec["data"]).get("today") or {}


@app.get("/api/preview_workout", dependencies=[Depends(auth)])
def preview_workout():
    from coach.garmin_push import build_workout
    day, today = _today_workout(conn())
    try:
        return build_workout(today, day)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/send_workout", dependencies=[Depends(auth)])
def send_workout():
    from coach.garmin_push import send_today
    try:
        return send_today(conn())
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"Garmin rechazo el entreno: {str(e)[:400]}")
