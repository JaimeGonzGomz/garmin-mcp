"""OAuth 2.1 para el conector MCP: claude.ai registra un cliente, te manda a /oauth/login,
tu escribes la contrasena de la web y recibe un token. Los tokens se guardan hasheados en SQLite."""
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from mcp.server.auth.provider import (
    AccessToken, AuthorizationCode, AuthorizationParams, RefreshToken, construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import BaseModel

from coach.db import conn
from coach.throttle import client_ip, fail, throttled

SCOPE = "coach"
ACCESS_TTL, REFRESH_TTL, CODE_TTL, PENDING_TTL = 3600, 30 * 86400, 300, 600
PENDING: dict[str, tuple[float, OAuthClientInformationFull, AuthorizationParams]] = {}

router = APIRouter()


def _db():
    db = conn()
    db.executescript("""
        create table if not exists oauth_clients (client_id text primary key, data text not null);
        create table if not exists oauth_codes (hash text primary key, data text not null, expires real not null);
        create table if not exists oauth_tokens (hash text primary key, kind text not null, client_id text not null,
                                                 scopes text not null, expires real not null);""")
    return db


def _h(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Provider:
    async def get_client(self, client_id: str):
        r = _db().execute("select data from oauth_clients where client_id = ?", (client_id,)).fetchone()
        return OAuthClientInformationFull.model_validate_json(r["data"]) if r else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        db = _db()
        db.execute("insert or replace into oauth_clients values (?, ?)", (client_info.client_id, client_info.model_dump_json()))
        db.commit()

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        now = time.time()
        for k in [k for k, v in PENDING.items() if v[0] < now]:
            del PENDING[k]
        req = secrets.token_urlsafe(24)
        PENDING[req] = (now + PENDING_TTL, client, params)
        return f"/oauth/login?req={req}"

    async def load_authorization_code(self, client, authorization_code: str):
        r = _db().execute("select data, expires from oauth_codes where hash = ?", (_h(authorization_code),)).fetchone()
        if not r or r["expires"] < time.time():
            return None
        code = AuthorizationCode.model_validate_json(r["data"])
        return code if code.client_id == client.client_id else None

    async def _issue(self, client_id: str, scopes: list[str]) -> OAuthToken:
        db, now = _db(), time.time()
        access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        for tok, kind, ttl in ((access, "access", ACCESS_TTL), (refresh, "refresh", REFRESH_TTL)):
            db.execute("insert into oauth_tokens values (?, ?, ?, ?, ?)", (_h(tok), kind, client_id, json.dumps(scopes), now + ttl))
        db.execute("delete from oauth_tokens where expires < ?", (now,))
        db.commit()
        return OAuthToken(access_token=access, token_type="Bearer", expires_in=ACCESS_TTL,
                          refresh_token=refresh, scope=" ".join(scopes))

    async def exchange_authorization_code(self, client, authorization_code: AuthorizationCode) -> OAuthToken:
        db = _db()
        db.execute("delete from oauth_codes where hash = ?", (_h(authorization_code.code),))  # un solo uso
        db.commit()
        return await self._issue(client.client_id, authorization_code.scopes)

    async def load_refresh_token(self, client, refresh_token: str):
        r = _db().execute("select * from oauth_tokens where hash = ? and kind = 'refresh'", (_h(refresh_token),)).fetchone()
        if not r or r["expires"] < time.time() or r["client_id"] != client.client_id:
            return None
        return RefreshToken(token=refresh_token, client_id=r["client_id"], scopes=json.loads(r["scopes"]),
                            expires_at=int(r["expires"]), subject="owner")

    async def exchange_refresh_token(self, client, refresh_token: RefreshToken, scopes: list[str]) -> OAuthToken:
        db = _db()
        db.execute("delete from oauth_tokens where hash = ?", (_h(refresh_token.token),))  # se rota
        db.commit()
        return await self._issue(client.client_id, scopes or refresh_token.scopes)

    async def load_access_token(self, token: str):
        r = _db().execute("select * from oauth_tokens where hash = ? and kind = 'access'", (_h(token),)).fetchone()
        if not r or r["expires"] < time.time():
            return None
        return AccessToken(token=token, client_id=r["client_id"], scopes=json.loads(r["scopes"]),
                           expires_at=int(r["expires"]), subject="owner")

    async def revoke_token(self, token) -> None:
        db = _db()
        db.execute("delete from oauth_tokens where hash = ?", (_h(token.token),))
        db.commit()


PAGE = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Autorizar acceso</title>
<style>body{font:16px/1.5 system-ui,sans-serif;max-width:420px;margin:4rem auto;padding:0 1rem}
input,button{font:inherit;padding:.5rem;width:100%;box-sizing:border-box;margin-top:.5rem}
@media(prefers-color-scheme:dark){body{background:#111;color:#e5e5e5}input{background:#222;color:inherit;border:1px solid #444}}
</style></head><body><h1>Garmin Coach</h1>
<p><b>__CLIENT__</b> quiere acceder a tus datos de entrenamiento (solo lectura). Escribe tu contrasena para permitirlo.</p>
<input id="pw" type="password" autocomplete="current-password" autofocus>
<button onclick="go()">Permitir</button><p id="msg"></p>
<script>
async function go(){
  const r = await fetch("/oauth/login", {method:"POST", headers:{"content-type":"application/json"},
    body: JSON.stringify({req: __REQ__, password: document.getElementById("pw").value})});
  const j = await r.json().catch(() => ({}));
  if (r.ok) location.href = j.redirect; else document.getElementById("msg").textContent = j.detail || "Error";
}
document.getElementById("pw").addEventListener("keydown", e => { if (e.key === "Enter") go(); });
</script></body></html>"""


@router.get("/oauth/login", response_class=HTMLResponse)
def login_page(req: str):
    from html import escape
    entry = PENDING.get(req)
    if not entry or entry[0] < time.time():
        raise HTTPException(400, "Solicitud caducada; vuelve a conectar desde claude.ai")
    name = escape(entry[1].client_name or "Una aplicacion")
    return PAGE.replace("__CLIENT__", name).replace("__REQ__", json.dumps(req))


class LoginBody(BaseModel):
    req: str
    password: str


@router.post("/oauth/login")
def login(body: LoginBody, request: Request):
    ip = client_ip(request)
    if throttled(ip):
        raise HTTPException(429, "Demasiados intentos; espera unos minutos")
    entry = PENDING.get(body.req)
    if not entry or entry[0] < time.time():
        raise HTTPException(400, "Solicitud caducada; vuelve a conectar desde claude.ai")
    if not hmac.compare_digest(body.password.encode(), os.environ["COACH_PASSWORD"].encode()):
        fail(ip)
        raise HTTPException(401, "Contrasena incorrecta")
    del PENDING[body.req]
    _, client, params = entry
    code = secrets.token_urlsafe(32)
    ac = AuthorizationCode(code=code, scopes=params.scopes or [SCOPE], expires_at=time.time() + CODE_TTL,
                           client_id=client.client_id, code_challenge=params.code_challenge,
                           redirect_uri=params.redirect_uri,
                           redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
                           resource=params.resource, subject="owner")
    db = _db()
    db.execute("insert into oauth_codes values (?, ?, ?)", (_h(code), ac.model_dump_json(), ac.expires_at))
    db.commit()
    return {"redirect": construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state)}
