"""Servidor MCP para Garmin Connect (lectura de datos + subida de entrenos)."""
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from garminconnect import Garmin
from mcp.server.fastmcp import FastMCP

TOKENS = Path.home() / ".garmin-mcp-tokens"
MAX_CHARS = 60_000

mcp = FastMCP("garmin")
_client: Garmin | None = None


def client() -> Garmin:
    global _client
    if _client is None:
        c = Garmin()
        c.login(str(TOKENS))
        _client = c
    return _client


def out(data: Any) -> str:
    text = json.dumps(data, ensure_ascii=False, default=str)
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "...[recortado]"
    return text


def _day(d: str | None) -> str:
    return d or date.today().isoformat()


def _range(days: int) -> tuple[str, str]:
    end = date.today()
    return (end - timedelta(days=days - 1)).isoformat(), end.isoformat()


@mcp.tool()
def recent_activities(limit: int = 20, activity_type: str | None = None) -> str:
    """Ultimas actividades (carrera, bici, fuerza...). activity_type opcional: running, cycling..."""
    return out(client().get_activities(0, limit, activity_type))


@mcp.tool()
def activities_between(start_date: str, end_date: str, activity_type: str | None = None) -> str:
    """Actividades entre dos fechas (YYYY-MM-DD)."""
    return out(client().get_activities_by_date(start_date, end_date, activity_type))


@mcp.tool()
def activity_summary(activity_id: str) -> str:
    """Resumen de una actividad."""
    return out(client().get_activity(activity_id))


@mcp.tool()
def activity_splits(activity_id: str) -> str:
    """Parciales/vueltas de una actividad."""
    return out(client().get_activity_splits(activity_id))


@mcp.tool()
def activity_hr_zones(activity_id: str) -> str:
    """Tiempo en cada zona de frecuencia cardiaca de una actividad."""
    return out(client().get_activity_hr_in_timezones(activity_id))


@mcp.tool()
def hrv(day: str | None = None) -> str:
    """HRV de una noche (YYYY-MM-DD, por defecto hoy): media nocturna, rango base, estado."""
    return out(client().get_hrv_data(_day(day)))


@mcp.tool()
def hrv_trend(days: int = 14) -> str:
    """HRV de los ultimos N dias (media nocturna y estado)."""
    rows = []
    for i in range(days):
        d = (date.today() - timedelta(days=i)).isoformat()
        try:
            data = client().get_hrv_data(d) or {}
        except Exception as e:  # dia sin datos
            rows.append({"date": d, "error": str(e)})
            continue
        s = data.get("hrvSummary") or {}
        rows.append({
            "date": d,
            "lastNightAvg": s.get("lastNightAvg"),
            "weeklyAvg": s.get("weeklyAvg"),
            "status": s.get("status"),
            "baseline": s.get("baseline"),
        })
    return out(rows)


@mcp.tool()
def sleep(day: str | None = None) -> str:
    """Sueno de una noche (YYYY-MM-DD, por defecto hoy)."""
    data = client().get_sleep_data(_day(day))
    data.pop("sleepMovement", None)  # series enormes
    data.pop("sleepLevels", None)
    return out(data)


@mcp.tool()
def body_battery(days: int = 7) -> str:
    """Body Battery de los ultimos N dias."""
    start, end = _range(days)
    return out(client().get_body_battery(start, end))


@mcp.tool()
def stress(day: str | None = None) -> str:
    """Estres del dia (resumen)."""
    data = client().get_stress_data(_day(day))
    for k in ("stressValuesArray", "bodyBatteryValuesArray"):
        data.pop(k, None)
    return out(data)


@mcp.tool()
def resting_hr(day: str | None = None) -> str:
    """Frecuencia cardiaca en reposo del dia."""
    return out(client().get_rhr_day(_day(day)))


@mcp.tool()
def daily_summary(day: str | None = None) -> str:
    """Resumen del dia: pasos, calorias, FC, estres, Body Battery, minutos de intensidad."""
    return out(client().get_user_summary(_day(day)))


@mcp.tool()
def training_readiness(day: str | None = None) -> str:
    """Disposicion para entrenar (Training Readiness)."""
    return out(client().get_training_readiness(_day(day)))


@mcp.tool()
def training_status(day: str | None = None) -> str:
    """Estado de entrenamiento: carga aguda/cronica, VO2max, tendencia."""
    return out(client().get_training_status(_day(day)))


@mcp.tool()
def max_metrics(day: str | None = None) -> str:
    """VO2 max y metricas maximas."""
    return out(client().get_max_metrics(_day(day)))


@mcp.tool()
def race_predictions() -> str:
    """Predicciones de tiempo para 5K, 10K, media y maraton."""
    return out(client().get_race_predictions())


@mcp.tool()
def endurance_score(days: int = 30) -> str:
    """Puntuacion de resistencia en los ultimos N dias."""
    start, end = _range(days)
    return out(client().get_endurance_score(start, end))


@mcp.tool()
def weigh_ins(days: int = 30) -> str:
    """Pesajes de los ultimos N dias."""
    start, end = _range(days)
    return out(client().get_weigh_ins(start, end))


@mcp.tool()
def list_workouts(limit: int = 30) -> str:
    """Entrenos guardados en tu cuenta de Garmin Connect."""
    return out(client().get_workouts(0, limit))


@mcp.tool()
def upload_workout(workout_json: str) -> str:
    """Sube un entreno estructurado (JSON de Garmin Connect) a tu cuenta; se sincroniza al reloj."""
    return out(client().upload_workout(json.loads(workout_json)))


@mcp.tool()
def schedule_workout(workout_id: str, date_str: str) -> str:
    """Programa un entreno ya subido en una fecha (YYYY-MM-DD) del calendario."""
    return out(client().schedule_workout(workout_id, date_str))


if __name__ == "__main__":
    mcp.run()
