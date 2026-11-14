"""Servidor MCP remoto (streamable HTTP) con OAuth. Herramientas de lectura sobre la base de datos del coach
y una de escritura (anadir nota al registro)."""
import json
import os
from datetime import date

from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from coach.db import conn
from coach.oauth import SCOPE, Provider
from coach.snapshot import build_snapshot

PUBLIC_URL = os.getenv("COACH_PUBLIC_URL", "https://contentaimaker.com").rstrip("/")
HOST = PUBLIC_URL.split("://", 1)[-1]
MAX_CHARS = 60_000

mcp = FastMCP(
    "garmin-coach",
    instructions="Datos de entrenamiento del usuario (Garmin) y la recomendacion diaria del coach. Solo lectura, salvo add_note.",
    auth_server_provider=Provider(),
    auth=AuthSettings(
        issuer_url=PUBLIC_URL,
        resource_server_url=f"{PUBLIC_URL}/mcp",
        validate_token_resource=False,
        required_scopes=[SCOPE],
        client_registration_options=ClientRegistrationOptions(enabled=True, valid_scopes=[SCOPE], default_scopes=[SCOPE]),
        revocation_options=RevocationOptions(enabled=True),
    ),
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(allowed_hosts=[HOST, f"{HOST}:*"], allowed_origins=[PUBLIC_URL]),
)


def out(data) -> str:
    text = json.dumps(data, ensure_ascii=False, default=str)
    return text if len(text) <= MAX_CHARS else text[:MAX_CHARS] + "...[recortado]"


@mcp.tool()
def today_recommendation() -> str:
    """Recomendacion del coach para hoy (sesion, FC y ritmo esperados) y su fecha."""
    return out(build_snapshot()["reco"])


@mcp.tool()
def training_status() -> str:
    """Estado actual: ritmos reales por zona, volumen, tendencias y dias hasta el objetivo."""
    s = build_snapshot()
    return out({"days_left": s["days_left"], "goal": s["settings"].get("goal_name"), "estado": s["estado"],
                "race_predictions": s["race_predictions"], "plan": s["plan"]})


@mcp.tool()
def recent_activities(limit: int = 15) -> str:
    """Ultimas actividades (resumen por actividad), de la mas reciente a la mas antigua. Maximo 40."""
    return out(build_snapshot()["activities"][: max(1, min(limit, 40))])


@mcp.tool()
def daily_metrics(days: int = 14) -> str:
    """Metricas diarias (sueno, VFC, Body Battery, FC en reposo...) de los ultimos dias. Maximo 60."""
    return out(build_snapshot()["metrics"][-max(1, min(days, 60)):])


@mcp.tool()
def weekly_volume() -> str:
    """Volumen semanal de las ultimas semanas."""
    return out(build_snapshot()["weekly"])


@mcp.tool()
def upcoming_calendar() -> str:
    """Sesiones programadas desde hace una semana hasta dentro de cuatro."""
    return out(build_snapshot()["calendar"])


@mcp.tool()
def log_entries(limit: int = 30) -> str:
    """Notas y entradas del registro del entrenamiento, las mas recientes primero. Maximo 150."""
    return out(build_snapshot()["log"][: max(1, min(limit, 150))])


@mcp.tool()
def add_note(text: str, day: str | None = None) -> str:
    """Anade una nota al registro (sensaciones, molestias, resultado del fisio...). day opcional YYYY-MM-DD."""
    text = text.strip()
    if not text:
        return "Nota vacia"
    if len(text) > 2000:
        return "Nota demasiado larga (max 2000 caracteres)"
    db = conn()
    db.execute("insert into log (day, kind, text) values (?, 'nota', ?)", (day or date.today().isoformat(), text))
    db.commit()
    return "Nota guardada"
