"""Descarga datos de Garmin y los guarda en Supabase. Uso: python -m coach.sync [dias]

Variables: SUPABASE_URL, SUPABASE_SERVICE_KEY, COACH_USER_ID (uuid del usuario en Supabase Auth)
Tokens de Garmin: se leen de la tabla garmin_tokens (o de GARMINTOKENS / ~/.garmin-mcp-tokens).
"""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from garminconnect import Garmin
from supabase import create_client

LOCAL_TOKENS = Path.home() / ".garmin-mcp-tokens"


def sb():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def garmin_client(db, user_id: str) -> Garmin:
    row = db.table("garmin_tokens").select("tokens").eq("user_id", user_id).execute().data
    c = Garmin()
    if row:
        c.login(row[0]["tokens"])
    else:
        c.login(str(LOCAL_TOKENS))
    # guarda tokens refrescados
    db.table("garmin_tokens").upsert({"user_id": user_id, "tokens": c.client.dumps()}).execute()
    return c


def safe(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        print("aviso:", getattr(fn, "__name__", fn), a, e)
        return None


def sync(days: int = 7) -> None:
    db, user_id = sb(), os.environ["COACH_USER_ID"]
    g = garmin_client(db, user_id)
    for i in range(days):
        d = (date.today() - timedelta(days=i)).isoformat()
        data = {
            "summary": safe(g.get_user_summary, d),
            "hrv": safe(g.get_hrv_data, d),
            "sleep": safe(g.get_sleep_data, d),
            "readiness": safe(g.get_training_readiness, d),
            "status": safe(g.get_training_status, d),
            "rhr": safe(g.get_rhr_day, d),
            "stress": safe(g.get_stress_data, d),
            "max_metrics": safe(g.get_max_metrics, d),
        }
        sleep = data["sleep"] or {}
        for k in ("sleepMovement", "sleepLevels"):
            sleep.pop(k, None)
        stress = data["stress"] or {}
        for k in ("stressValuesArray", "bodyBatteryValuesArray"):
            stress.pop(k, None)
        db.table("daily_metrics").upsert({"user_id": user_id, "day": d, "data": data}).execute()
    start = (date.today() - timedelta(days=max(days, 28))).isoformat()
    acts = safe(g.get_activities_by_date, start, date.today().isoformat()) or []
    rows = [
        {
            "user_id": user_id,
            "activity_id": a["activityId"],
            "start_time": a.get("startTimeGMT"),
            "type": (a.get("activityType") or {}).get("typeKey"),
            "data": a,
        }
        for a in acts
    ]
    if rows:
        db.table("activities").upsert(rows).execute()
    print(f"sync ok: {days} dias, {len(rows)} actividades")


if __name__ == "__main__":
    sync(int(sys.argv[1]) if len(sys.argv) > 1 else 7)
