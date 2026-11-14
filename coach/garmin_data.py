"""Capa de datos de Garmin para el conector MCP: solo lee lo ya sincronizado en SQLite (sin IA).

Es el unico sitio por el que el MCP accede a los datos: cuando el origen pase de `garminconnect` a la
API oficial (Business, por push y por usuario) basta con cambiar esta capa."""
import json
from datetime import date, datetime, timedelta

from coach.db import conn, get_extra, get_settings
from coach.digest import RUN_TYPES, activity_digest, calendar_digest, day_digest, plan_info, plan_tasks, weekly_volume
from coach.estado import calcular, zonas

METRICS = list(day_digest({}).keys())


def _range(start: str | None, end: str | None, default_days: int) -> tuple[str, str]:
    e = end or date.today().isoformat()
    s = start or (date.fromisoformat(e) - timedelta(days=default_days - 1)).isoformat()
    date.fromisoformat(s), date.fromisoformat(e)  # valida el formato YYYY-MM-DD
    return s, e


def _activity_row(a: dict) -> dict:
    row = activity_digest(a)
    zmin = [a.get(f"hrTimeInZone_{i}") for i in range(1, 6)]
    row.update({
        "te_anaerobic": a.get("anaerobicTrainingEffect"),
        "cadence": a.get("averageRunningCadenceInStepsPerMinute"),
        "elev_gain_m": a.get("elevationGain"),
        "calories": a.get("calories"),
        "avg_power": a.get("avgPower"),
        "hr_zone_min": [round(z / 60, 1) if isinstance(z, (int, float)) else None for z in zmin] if any(z is not None for z in zmin) else None,
    })
    return row


def activities(start: str | None = None, end: str | None = None, type: str | None = None, limit: int = 30) -> list[dict]:
    s, e = _range(start, end, 30)
    rows = conn().execute(
        "select data from activities where substr(start_time, 1, 10) between ? and ? order by start_time desc", (s, e)).fetchall()
    out = [_activity_row(json.loads(r["data"])) for r in rows]
    if type:
        out = [a for a in out if a["type"] == type or (type == "running" and a["type"] in RUN_TYPES)]
    return out[: max(1, min(limit, 100))]


def activity_detail(activity_id: int) -> dict | None:
    r = conn().execute("select data from activities where activity_id = ?", (activity_id,)).fetchone()
    return json.loads(r["data"]) if r else None


def daily(start: str | None = None, end: str | None = None) -> list[dict]:
    s, e = _range(start, end, 14)
    rows = conn().execute("select day, data from daily_metrics where day between ? and ? order by day", (s, e)).fetchall()
    return [{"day": r["day"], **day_digest(json.loads(r["data"]))} for r in rows]


def series(metrics: list[str], start: str | None = None, end: str | None = None) -> dict:
    """Series temporales listas para graficar: {"days": [...], "series": {metrica: [valores...]}}."""
    bad = [m for m in metrics if m not in METRICS]
    if bad:
        raise ValueError(f"Metricas desconocidas {bad}. Disponibles: {METRICS}")
    rows = daily(start, end)
    return {"days": [r["day"] for r in rows], "series": {m: [r.get(m) for r in rows] for m in metrics}}


def weekly(weeks: int = 12) -> list[dict]:
    rows = conn().execute("select data from activities order by start_time").fetchall()
    return weekly_volume([activity_digest(json.loads(r["data"])) for r in rows], max(1, min(weeks, 52)))


def hr_zones():
    return get_extra(conn(), "hr_zones")


def race_predictions():
    return get_extra(conn(), "race_predictions")


def scheduled_workouts(start: str | None = None, end: str | None = None) -> list[dict]:
    """Entrenos programados en Garmin (plan de Garmin Coach y calendario) entre dos fechas."""
    s, e = _range(start, end, 1)
    if not start:
        s = (date.today() - timedelta(days=7)).isoformat()
    if not end:
        e = (date.today() + timedelta(days=28)).isoformat()
    db = conn()
    plans = get_extra(db, "garmin_plans")
    return plan_tasks(plans, s, e) or [{"date": c["date"], "title": c.get("title"), "sport": c.get("sportTypeKey")}
                                       for c in calendar_digest(get_extra(db, "calendar") or [], s, e)]


def training_plan() -> dict:
    return plan_info(get_extra(conn(), "garmin_plans"))


def summary() -> dict:
    """Resumen calculado (sin IA): VO2max, FC en reposo, VFC, sueno, carga, volumen, ritmo real por zona de FC."""
    db = conn()
    metrics = [{"day": r["day"], **day_digest(json.loads(r["data"]))}
               for r in db.execute("select * from daily_metrics order by day desc limit 60")][::-1]
    acts = [activity_digest(json.loads(r["data"])) for r in db.execute("select data from activities order by start_time")]
    return calcular(metrics, acts, get_extra(db, "garmin_plans"), get_settings(db),
                    get_extra(db, "race_predictions"), get_extra(db, "hr_zones"))


def pace_by_hr_zone() -> dict | None:
    db = conn()
    acts = [activity_digest(json.loads(r["data"])) for r in db.execute("select data from activities order by start_time")]
    return zonas(acts, get_settings(db), get_extra(db, "hr_zones"))
