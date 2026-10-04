"""Web del coach (FastAPI). Un usuario, contrasena en COACH_PASSWORD."""
import hmac
import json
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from coach.db import conn

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.environ["SESSION_SECRET"], max_age=60 * 60 * 24 * 30, https_only=True)
STATIC = Path(__file__).parent / "static"


class Login(BaseModel):
    password: str


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


@app.get("/api/data", dependencies=[Depends(auth)])
def data():
    db = conn()
    rec = db.execute("select * from recommendations order by day desc limit 1").fetchone()
    metrics = [{"day": r["day"], "data": json.loads(r["data"])}
               for r in db.execute("select * from daily_metrics order by day desc limit 14")]
    return {
        "recommendation": rec and {"day": rec["day"], "today": json.loads(rec["today"]),
                                   "upcoming": json.loads(rec["upcoming"]), "analysis": rec["analysis"]},
        "metrics": metrics,
    }
