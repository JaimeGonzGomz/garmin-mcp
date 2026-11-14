"""Servidor MCP remoto (streamable HTTP) con OAuth: datos de Garmin en bruto (solo lectura) y envio de entrenos."""
import json
import os
import tempfile
from contextlib import contextmanager

from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from coach import garmin_data as gd
from coach.oauth import SCOPE, Provider

PUBLIC_URL = os.getenv("COACH_PUBLIC_URL", "https://contentaimaker.com").rstrip("/")
HOST = PUBLIC_URL.split("://", 1)[-1]
MAX_CHARS = 60_000


INSTRUCTIONS = (
    "Datos de Garmin del usuario (lectura, salvo send_workout si existe): actividades, sueno, VFC, Body Battery, estres, carga, zonas y entrenos "
    "programados. Las herramientas devuelven datos medidos o calculados, nunca recomendaciones tuyas. Cuando el usuario pida "
    "consejo de entrenamiento: 1) lee los datos que haga falta; 2) separa con claridad 'Lo que Garmin recomienda' (solo lo que "
    "Garmin aporta: entrenos programados, plan de Garmin Coach, readiness, estado de entrenamiento; si no hay nada, dilo y no "
    "lo inventes) de 'Mi recomendacion' (la tuya) y explica el porque citando las cifras concretas; 3) si ambas difieren, "
    "senala en que y cual elegirias. Para graficos usa metric_series y weekly_volume. No eres medico: ante dolor o sintomas, "
    "recomienda consultar a un profesional. Si existe send_workout, propon primero el entreno al usuario y solo lo envies "
    "cuando el confirme (primero con confirm=false para la vista previa)."
)

@contextmanager
def _sin_env_en_cwd():
    """FastMCP (pydantic-settings) intenta leer ./.env; el servicio corre sin privilegios y ese archivo es de root.
    Los secretos llegan por EnvironmentFile, asi que construimos FastMCP desde un directorio sin .env."""
    prev = os.getcwd()
    os.chdir(tempfile.gettempdir())
    try:
        yield
    finally:
        os.chdir(prev)


with _sin_env_en_cwd():
    mcp = FastMCP(
        "garmin-coach",
        instructions=INSTRUCTIONS,
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


READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)


def out(data) -> str:
    text = json.dumps(data, ensure_ascii=False, default=str)
    return text if len(text) <= MAX_CHARS else text[:MAX_CHARS] + "...[recortado]"


@mcp.tool(annotations=READ)
def activities(start_date: str | None = None, end_date: str | None = None, activity_type: str | None = None, limit: int = 30) -> str:
    """Actividades (mas recientes primero) entre dos fechas YYYY-MM-DD (por defecto, ultimos 30 dias). activity_type opcional:
    running, cycling, strength_training... Cada una trae km, min, ritmo (min/km), FC media y maxima, efecto de
    entrenamiento aerobico/anaerobico, carga, cadencia, desnivel, potencia y minutos en cada zona de FC. Maximo 100."""
    return out(gd.activities(start_date, end_date, activity_type, limit))


@mcp.tool(annotations=READ)
def activity_detail(activity_id: int) -> str:
    """Datos completos de una actividad concreta (el id sale de `activities`), tal como los devuelve Garmin."""
    d = gd.activity_detail(activity_id)
    return out(d) if d else "Actividad no encontrada"


@mcp.tool(annotations=READ)
def daily_metrics(start_date: str | None = None, end_date: str | None = None) -> str:
    """Una fila por dia entre dos fechas (por defecto, ultimos 14 dias): VFC (y su rango base), sueno (horas, puntuacion,
    fases), FC en reposo, Body Battery, estres, pasos, minutos de intensidad, readiness, carga aguda/cronica, ACWR,
    estado de entrenamiento y VO2max."""
    return out(gd.daily(start_date, end_date))


@mcp.tool(annotations=READ, description=(
    "Series temporales listas para graficar: devuelve {days:[...], series:{metrica:[valores]}}. "
    f"Metricas disponibles: {', '.join(gd.METRICS)}. Fechas YYYY-MM-DD (por defecto, ultimos 14 dias)."))
def metric_series(metrics: list[str], start_date: str | None = None, end_date: str | None = None) -> str:
    return out(gd.series(metrics, start_date, end_date))


@mcp.tool(annotations=READ)
def weekly_volume(weeks: int = 12) -> str:
    """Kilometros, minutos y numero de carreras por semana (lunes) de las ultimas semanas. Maximo 52."""
    return out(gd.weekly(weeks))


@mcp.tool(annotations=READ)
def training_summary() -> str:
    """Resumen calculado sobre los datos (sin IA): VO2max, FC en reposo, VFC, sueno, carga, cambio de volumen en 14 dias,
    tirada larga reciente, dias sin correr y ritmo real por zona de FC."""
    return out(gd.summary())


@mcp.tool(annotations=READ)
def pace_by_hr_zone() -> str:
    """Ritmo medio real (min/km) por zona de FC en los ultimos 28 dias frente a los 28 anteriores."""
    return out(gd.pace_by_hr_zone())


@mcp.tool(annotations=READ)
def hr_zones() -> str:
    """Zonas de frecuencia cardiaca configuradas en Garmin (suelo de cada zona, FC maxima y en reposo)."""
    return out(gd.hr_zones())


@mcp.tool(annotations=READ)
def race_predictions() -> str:
    """Predicciones de tiempo de carrera de Garmin (5K, 10K, media, maraton)."""
    return out(gd.race_predictions())


@mcp.tool(annotations=READ)
def scheduled_workouts(start_date: str | None = None, end_date: str | None = None) -> str:
    """Lo que Garmin tiene programado o recomendado: entrenos del plan de Garmin Coach y del calendario. Por defecto, desde hace 7 dias hasta dentro de 28."""
    return out(gd.scheduled_workouts(start_date, end_date))


@mcp.tool(annotations=READ)
def training_plan() -> str:
    """Plan de entrenamiento activo en Garmin Coach: nombre, fechas, semanas, entrenos por semana y fases."""
    return out(gd.training_plan())


# Escribir en Garmin solo si se activa en el .env (COACH_ENABLE_SEND=1): usa los tokens de garminconnect de esta instancia.
# El conector publico no lo activa; con Business se sustituira por la Training API.
ENABLE_SEND = os.getenv("COACH_ENABLE_SEND") == "1"

if ENABLE_SEND:
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True))
    def send_workout(name: str, date: str, steps: list[dict], description: str = "", confirm: bool = False) -> str:
        """Crea un entreno de CARRERA estructurado en Garmin Connect y lo programa en `date` (YYYY-MM-DD, entre hoy y +60 dias);
        se sincroniza con el reloj. Con confirm=false solo devuelve la vista previa: ensenasela al usuario y llama de nuevo con
        confirm=true cuando el diga que si. Cada paso es un dict:
          {"type": "warmup|run|recovery|rest|cooldown", "name": "...", "note": "...",
           "duration_min": 10 | "distance_km": 1.0 | "distance_m": 400,        (uno de los tres)
           "target": {"type": "hr", "min": 140, "max": 155}                       (lpm)
                  o {"type": "pace", "min": "5:10", "max": "5:30"}                (min:seg por km)
                  o {"type": "none"}}
        Para repetir: {"repeat": 5, "steps": [ ...pasos... ]} (sin anidar). Maximo 40 pasos."""
        from coach import garmin_push
        w = garmin_push.workout_from_spec(name, date, steps, description)
        if not confirm:
            return out({"vista_previa": True, "nombre": w["workoutName"], "fecha": date, "pasos": steps,
                        "siguiente": "Si el usuario confirma, llama de nuevo con confirm=true."})
        try:
            r = garmin_push.push(w, date)
        except Exception as e:
            raise RuntimeError(f"Garmin rechazo el entreno: {str(e)[:300]}") from e
        return out({"enviado": True, "nombre": w["workoutName"], **r})


@mcp.prompt(title="Garmin vs mi recomendacion")
def garmin_vs_recommendation(question: str = "Que deberia entrenar hoy?") -> str:
    """Compara lo que Garmin recomienda con la recomendacion razonada del asistente."""
    return (f"{question}\n\n"
            "Usa las herramientas de Garmin: entrenos programados, resumen de entrenamiento, metricas de los "
            "ultimos 14 dias y actividades recientes. Responde con tres apartados: 'Lo que Garmin recomienda', "
            "'Mi recomendacion' y 'Por que' (con cifras).")
