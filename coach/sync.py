"""Descarga datos de Garmin y los guarda en SQLite. Uso: python -m coach.sync [dias]

Tokens de Garmin: carpeta data/tokens (se copia desde tu PC, ver README).
"""
import sys
from datetime import date, timedelta

from garminconnect import Garmin

from coach.db import DATA, conn, dumps

TOKENS = DATA / "tokens"


def safe(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        print("aviso:", getattr(fn, "__name__", fn), a, e)
        return None


def sync(days: int = 7) -> None:
    g = Garmin()
    g.login(str(TOKENS))
    db = conn()
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
        for key, drop in (("sleep", ("sleepMovement", "sleepLevels")),
                          ("stress", ("stressValuesArray", "bodyBatteryValuesArray"))):
            for k in drop:
                (data[key] or {}).pop(k, None)
        db.execute("insert or replace into daily_metrics values (?, ?)", (d, dumps(data)))
    start = (date.today() - timedelta(days=max(days, 28))).isoformat()
    acts = safe(g.get_activities_by_date, start, date.today().isoformat()) or []
    for a in acts:
        db.execute("insert or replace into activities values (?, ?, ?, ?)",
                   (a["activityId"], a.get("startTimeGMT"), (a.get("activityType") or {}).get("typeKey"), dumps(a)))
    db.commit()
    print(f"sync ok: {days} dias, {len(acts)} actividades")


if __name__ == "__main__":
    sync(int(sys.argv[1]) if len(sys.argv) > 1 else 7)
