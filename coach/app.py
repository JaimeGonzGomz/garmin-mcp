"""Web del coach (FastAPI). Un usuario, contrasena en COACH_PASSWORD."""
import hmac
import json
import os
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from coach.db import DATA, conn, get_extra, get_settings
from coach.estado import calcular
from coach.digest import activity_digest, calendar_digest, day_digest, plan_info, plan_tasks, weekly_volume

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.environ["SESSION_SECRET"], max_age=60 * 60 * 24 * 30,
                   https_only=os.getenv("COACH_INSECURE_COOKIES") != "1")
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
    if not hmac.compare_digest(body.password, os.environ["COACH_PASSWORD"]):
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
    db = conn()
    today = date.today()
    metrics = [{"day": r["day"], **day_digest(json.loads(r["data"]))}
               for r in db.execute("select * from daily_metrics order by day desc limit 60")][::-1]
    acts = [activity_digest(json.loads(r["data"]))
            for r in db.execute("select data from activities order by start_time")]
    rec = db.execute("select * from reco order by day desc limit 1").fetchone()
    a, b = (today - timedelta(days=7)).isoformat(), (today + timedelta(days=28)).isoformat()
    plans = get_extra(db, "garmin_plans")
    cal = plan_tasks(plans, a, b) or [{"date": c["date"], "title": c.get("title"), "sport": c.get("sportTypeKey")}
                                      for c in calendar_digest(get_extra(db, "calendar") or [], a, b)]
    st = get_settings(db)
    try:
        days_left = (date.fromisoformat(st["goal_date"]) - today).days
    except ValueError:
        days_left = None
    return {
        "today": today.isoformat(),
        "settings": st,
        "days_left": days_left,
        "reco": rec and {"day": rec["day"], "created_at": rec["created_at"], **json.loads(rec["data"])},
        "metrics": metrics,
        "activities": acts[-40:][::-1],
        "weekly": weekly_volume(acts),
        "calendar": cal,
        "plan": plan_info(plans),
        "estado": calcular(metrics, acts, plans, st, get_extra(db, "race_predictions")),
        "race_predictions": get_extra(db, "race_predictions"),
        "log": [dict(r) for r in db.execute("select id, day, kind, text from log order by id desc limit 150")],
        "refreshing": refreshing(),
    }


@app.post("/api/settings", dependencies=[Depends(auth)])
def save_settings(body: dict):
    db = conn()
    for k in ("goal_name", "goal_date", "days_week", "context", "milestones", "history", "hr_max", "hr_recovery", "hr_long", "hr_easy"):
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
