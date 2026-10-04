"""Convierte el entreno de hoy (pasos estructurados del coach) en un entreno de Garmin y lo programa."""
import re
from datetime import date

from garminconnect import Garmin

from coach.sync import TOKENS

STEP = {"calentamiento": (1, "warmup", 1), "enfriamiento": (2, "cooldown", 2), "correr": (3, "interval", 3),
        "series": (3, "interval", 3), "recuperacion": (4, "recovery", 4), "descanso": (5, "rest", 5)}
NO_TARGET = {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target", "displayOrder": 1}


def _secs(x):
    """'5:30' o 5.5 (min/km) -> segundos por km."""
    if isinstance(x, (int, float)):
        return x * 60 if x < 30 else x
    m = re.match(r"^\s*(\d+):(\d{1,2})", str(x or ""))
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def _target(obj):
    obj = obj or {}
    kind = str(obj.get("tipo", "ninguno")).lower()
    if kind == "fc":
        lo, hi = obj.get("min"), obj.get("max")
        try:
            lo, hi = float(lo or 0), float(hi)
        except (TypeError, ValueError):
            return NO_TARGET, {}
        return ({"workoutTargetTypeId": 4, "workoutTargetTypeKey": "heart.rate.zone", "displayOrder": 4},
                {"targetValueOne": lo, "targetValueTwo": hi})
    if kind == "ritmo":
        fast, slow = _secs(obj.get("min")), _secs(obj.get("max"))
        if not fast or not slow:
            return NO_TARGET, {}
        fast, slow = sorted((fast, slow))
        # Garmin guarda el ritmo como velocidad (m/s): primero la mas rapida, luego la mas lenta
        return ({"workoutTargetTypeId": 6, "workoutTargetTypeKey": "pace.zone", "displayOrder": 6},
                {"targetValueOne": round(1000 / fast, 4), "targetValueTwo": round(1000 / slow, 4)})
    return NO_TARGET, {}


def _end(p):
    if p.get("duracion_min"):
        return {"conditionTypeId": 2, "conditionTypeKey": "time", "displayOrder": 2, "displayable": True}, float(p["duracion_min"]) * 60
    if p.get("distancia_m") or p.get("distancia_km"):
        m = float(p.get("distancia_m") or float(p["distancia_km"]) * 1000)
        return {"conditionTypeId": 3, "conditionTypeKey": "distance", "displayOrder": 3, "displayable": True}, m
    return {"conditionTypeId": 1, "conditionTypeKey": "lap.button", "displayOrder": 1, "displayable": True}, None


def _steps(pasos, counter):
    out = []
    for p in pasos:
        counter[0] += 1
        order = counter[0]
        if p.get("repeticiones") and p.get("pasos"):
            inner = _steps(p["pasos"], counter)
            out.append({"type": "RepeatGroupDTO", "stepOrder": order, "stepType": {"stepTypeId": 6, "stepTypeKey": "repeat", "displayOrder": 6},
                        "numberOfIterations": int(p["repeticiones"]), "workoutSteps": inner, "smartRepeat": False,
                        "endCondition": {"conditionTypeId": 7, "conditionTypeKey": "iterations", "displayOrder": 7, "displayable": False},
                        "endConditionValue": float(p["repeticiones"])})
            continue
        sid, key, disp = STEP.get(str(p.get("tipo", "correr")).lower(), STEP["correr"])
        end, val = _end(p)
        ttype, tvals = _target(p.get("objetivo"))
        step = {"type": "ExecutableStepDTO", "stepOrder": order, "stepType": {"stepTypeId": sid, "stepTypeKey": key, "displayOrder": disp},
                "endCondition": end, "endConditionValue": val, "targetType": ttype, **tvals}
        if p.get("nombre") or p.get("detalle"):
            step["description"] = (f"{p.get('nombre', '')}: {p.get('detalle', '')}".strip(": "))[:200]
        out.append(step)
    return out


def build_workout(today: dict, day: str) -> dict:
    if str(today.get("tipo", "")).lower() not in ("running", "carrera", "correr", "run"):
        raise ValueError("Solo se pueden enviar entrenos de carrera (el de hoy es de tipo: %s)" % today.get("tipo"))
    pasos = today.get("pasos") or []
    if not any(isinstance(p, dict) and ("duracion_min" in p or "distancia_m" in p or "distancia_km" in p or p.get("pasos")) for p in pasos):
        raise ValueError("El entreno no tiene pasos estructurados; pulsa 'Actualizar ahora' para que el coach los genere.")
    steps = _steps([p for p in pasos if isinstance(p, dict)], [0])
    return {
        "workoutName": f"Coach {day} {today.get('titulo', '')}"[:60],
        "description": str(today.get("motivo", ""))[:500],
        "sportType": {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1},
        "estimatedDurationInSecs": int(float(today.get("duracion_min") or 0) * 60),
        "workoutSegments": [{"segmentOrder": 1, "sportType": {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1},
                             "workoutSteps": steps}],
    }


def push(workout: dict, day: str, previous_id=None) -> dict:
    g = Garmin()
    g.login(str(TOKENS))
    if previous_id:  # reenvio del mismo dia: borrar el anterior para no duplicar
        try:
            g.delete_workout(previous_id)
        except Exception as e:  # ya borrado a mano, etc.
            print("aviso: no se pudo borrar el entreno anterior:", e)
    up = g.upload_workout(workout)
    wid = up.get("workoutId")
    if not wid:
        raise RuntimeError(f"Garmin no devolvio workoutId: {str(up)[:300]}")
    g.schedule_workout(wid, day)
    return {"workout_id": wid, "day": day}


def send_today(db) -> dict:
    """Envia a Garmin el entreno de hoy de la ultima recomendacion y lo registra. ValueError si no es enviable."""
    import json
    day = date.today().isoformat()
    rec = db.execute("select data from reco where day = ?", (day,)).fetchone()
    if not rec:
        raise ValueError("No hay recomendacion de hoy; pulsa 'Actualizar ahora'.")
    w = build_workout(json.loads(rec["data"]).get("today") or {}, day)
    prev = db.execute("select workout_id from sent where day = ?", (day,)).fetchone()
    r = push(w, day, prev["workout_id"] if prev else None)
    db.execute("insert or replace into sent (day, workout_id, name) values (?, ?, ?)", (day, str(r["workout_id"]), w["workoutName"]))
    db.commit()
    return {**r, "name": w["workoutName"], "ok": True}
