"""Foto del estado del coach leida de SQLite; la usan la web (/api/data) y el servidor MCP."""
import json
from datetime import date, timedelta

from coach.db import conn, get_extra, get_settings
from coach.digest import activity_digest, calendar_digest, day_digest, plan_info, plan_tasks, weekly_volume
from coach.estado import calcular


def build_snapshot(refreshing: bool = False) -> dict:
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
        "estado": calcular(metrics, acts, plans, st, get_extra(db, "race_predictions"), get_extra(db, "hr_zones")),
        "race_predictions": get_extra(db, "race_predictions"),
        "sent": {r["day"]: {"name": r["name"], "at": r["sent_at"]} for r in db.execute("select * from sent order by day desc limit 14")},
        "log": [dict(r) for r in db.execute("select id, day, kind, text from log order by id desc limit 150")],
        "refreshing": refreshing,
    }
