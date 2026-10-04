"""Resumenes compactos de los datos crudos de Garmin (para la web y para el prompt)."""
import json
from collections import deque
from datetime import date, datetime, timedelta

RUN_TYPES = {"running", "trail_running", "treadmill_running", "track_running", "virtual_run"}


def deep_find(obj, key):
    """Primer valor no nulo de `key` buscando en anchura dentro de dicts/listas anidados."""
    q = deque([obj])
    while q:
        o = q.popleft()
        if isinstance(o, dict):
            if o.get(key) is not None:
                return o[key]
            q.extend(o.values())
        elif isinstance(o, list):
            q.extend(o)
    return None


def _div(x, d, nd=1):
    return round(x / d, nd) if isinstance(x, (int, float)) else None


def day_digest(data: dict) -> dict:
    hrv = (data.get("hrv") or {}).get("hrvSummary") or {}
    base = hrv.get("baseline") or {}
    sl = (data.get("sleep") or {}).get("dailySleepDTO") or {}
    rd = data.get("readiness")
    rd = (rd[0] if isinstance(rd, list) and rd else rd) or {}
    sm = data.get("summary") or {}
    st = data.get("status") or {}
    mm = data.get("max_metrics")
    return {
        "hrv": hrv.get("lastNightAvg"),
        "hrv_weekly": hrv.get("weeklyAvg"),
        "hrv_status": hrv.get("status"),
        "hrv_low": base.get("balancedLow"),
        "hrv_high": base.get("balancedUpper"),
        "sleep_h": _div(sl.get("sleepTimeSeconds"), 3600, 2),
        "sleep_score": ((sl.get("sleepScores") or {}).get("overall") or {}).get("value"),
        "deep_min": _div(sl.get("deepSleepSeconds"), 60, 0),
        "rem_min": _div(sl.get("remSleepSeconds"), 60, 0),
        "awake_min": _div(sl.get("awakeSleepSeconds"), 60, 0),
        "rhr": sm.get("restingHeartRate"),
        "bb_high": sm.get("bodyBatteryHighestValue"),
        "bb_low": sm.get("bodyBatteryLowestValue"),
        "stress": sm.get("averageStressLevel"),
        "steps": sm.get("totalSteps"),
        "int_mod": sm.get("moderateIntensityMinutes"),
        "int_vig": sm.get("vigorousIntensityMinutes"),
        "readiness": rd.get("score"),
        "readiness_level": rd.get("level"),
        "readiness_msg": rd.get("feedbackShort"),
        "load_acute": deep_find(st, "dailyTrainingLoadAcute"),
        "load_chronic": deep_find(st, "dailyTrainingLoadChronic"),
        "acwr": deep_find(st, "dailyAcuteChronicWorkloadRatio"),
        "status": deep_find(st, "trainingStatusFeedbackPhrase"),
        "vo2max": deep_find(mm, "vo2MaxPreciseValue") or deep_find(mm, "vo2MaxValue")
        or deep_find(st, "vo2MaxPreciseValue") or deep_find(st, "vo2MaxValue"),
    }


def activity_digest(a: dict) -> dict:
    dist, dur, spd = a.get("distance"), a.get("duration"), a.get("averageSpeed")
    return {
        "id": a.get("activityId"),
        "name": a.get("activityName"),
        "start": a.get("startTimeLocal"),
        "type": (a.get("activityType") or {}).get("typeKey"),
        "km": _div(dist, 1000, 2),
        "min": _div(dur, 60, 1),
        "pace": round(1000 / spd / 60, 2) if isinstance(spd, (int, float)) and spd > 0 else None,
        "hr": a.get("averageHR"),
        "hr_max": a.get("maxHR"),
        "te": a.get("aerobicTrainingEffect"),
        "load": a.get("activityTrainingLoad"),
    }


def weekly_volume(acts: list[dict], weeks: int = 12) -> list[dict]:
    """Km y minutos de carrera por semana (lunes). `acts` son activity_digest."""
    monday = date.today() - timedelta(days=date.today().weekday())
    out = {(monday - timedelta(weeks=i)).isoformat(): {"week": (monday - timedelta(weeks=i)).isoformat(), "km": 0.0, "min": 0.0, "runs": 0}
           for i in range(weeks)}
    for a in acts:
        if a["type"] not in RUN_TYPES or not a["start"]:
            continue
        d = datetime.fromisoformat(a["start"][:19]).date()
        w = (d - timedelta(days=d.weekday())).isoformat()
        if w in out:
            out[w]["km"] = round(out[w]["km"] + (a["km"] or 0), 1)
            out[w]["min"] = round(out[w]["min"] + (a["min"] or 0), 0)
            out[w]["runs"] += 1
    return sorted(out.values(), key=lambda x: x["week"])


def calendar_digest(months: list[dict], start: str, end: str) -> list[dict]:
    """Entrenos programados en el calendario de Garmin (incluye Garmin Coach) entre dos fechas."""
    items = []
    for m in months:
        for it in (m or {}).get("calendarItems") or []:
            d = it.get("date")
            if not d or not (start <= d <= end):
                continue
            kind = str(it.get("itemType") or "")
            if "workout" not in kind.lower() and not it.get("workoutId"):
                continue
            items.append({k: v for k, v in list(it.items()) if isinstance(v, (str, int, float)) and v != ""}
                         | {"date": d})
    return sorted(items, key=lambda x: x["date"])


if __name__ == "__main__":  # python -m coach.digest -> ultimo dia, para comprobar que campos se rellenan
    from coach.db import conn
    r = conn().execute("select day, data from daily_metrics order by day desc limit 1").fetchone()
    if r:
        print(r["day"], json.dumps(day_digest(json.loads(r["data"])), indent=1, ensure_ascii=False))
