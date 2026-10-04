"""Panel de estado: metricas clave calculadas a partir de tus datos (sin LLM)."""
from datetime import date, datetime, timedelta
from statistics import median

from coach.digest import RUN_TYPES, plan_tasks


def _d(a):
    return datetime.fromisoformat(a["start"][:19]).date() if a.get("start") else None


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 1) if xs else None


def _back(metrics, key, days_ago):
    """Ultimo valor no nulo de `key` con antiguedad >= days_ago."""
    limit = (date.today() - timedelta(days=days_ago)).isoformat()
    for m in reversed(metrics):
        if m["day"] <= limit and m.get(key) is not None:
            return m[key]
    return None


def garmin_bands(hr_zones):
    """Zonas de FC de Garmin (running si existe, si no DEFAULT) -> [(nombre, etiqueta, funcion)] y FC max usada."""
    if not isinstance(hr_zones, list):
        return None, None
    by = {str(z.get("sport", "")).upper(): z for z in hr_zones if isinstance(z, dict)}
    z = by.get("RUNNING") or by.get("DEFAULT") or next(iter(by.values()), None)
    try:
        f = [float(z[f"zone{i}Floor"]) for i in range(1, 6)]
        mx = float(z.get("maxHeartRateUsed") or 0) or None
    except (TypeError, ValueError, KeyError):
        return None, None
    names = ["Z1 recuperación", "Z2 aeróbica", "Z3 tempo", "Z4 umbral", "Z5 máximo"]
    bands = []
    for i in range(5):
        lo = f[i] if i else 0
        hi = f[i + 1] if i < 4 else 999
        label = f"{f[i]:.0f}–{(f[i + 1] - 1):.0f}" if i < 4 else f"≥ {f[4]:.0f}"
        bands.append((names[i], label, (lambda h, lo=lo, hi=hi: lo <= h < hi)))
    return bands, mx


def zonas(acts, st, hr_zones=None):
    """Ritmo medio real por zona de FC del usuario (ajustes hr_recovery < hr_long < hr_easy)."""
    bands, source, mx = None, "manual", None
    if st.get("zonas_fuente", "garmin") == "garmin":
        bands, mx = garmin_bands(hr_zones)
        source = "garmin"
    if not bands:
        source = "manual"
        rec, lng, easy = (_num(st.get(k)) for k in ("hr_recovery", "hr_long", "hr_easy"))
        if not (rec and lng and easy):
            return None
    if source == "manual":
        bands = [("Recuperación", f"< {rec:.0f}", lambda h: h <= rec), ("Tirada larga", f"{rec:.0f}–{lng:.0f}", lambda h: rec < h <= lng),
             ("Rodaje fácil", f"{lng:.0f}–{easy:.0f}", lambda h: lng < h <= easy), ("Sobre fácil (tempo/series)", f"> {easy:.0f}", lambda h: h > easy)]
        mx = _num(st.get("hr_max"))
    today = date.today()
    runs = [a for a in acts if a["type"] in RUN_TYPES and (a["km"] or 0) >= 3 and a["hr"] and a["pace"] and _d(a)]
    out = []
    for name, label, f in bands:
        cur = [a["pace"] for a in runs if f(a["hr"]) and 0 <= (today - _d(a)).days < 28]
        prev = [a["pace"] for a in runs if f(a["hr"]) and 28 <= (today - _d(a)).days < 56]
        out.append({"zona": name, "fc": label, "n": len(cur), "pace": round(median(cur), 2) if cur else None,
                    "n_prev": len(prev), "pace_prev": round(median(prev), 2) if prev else None})
    return {"fuente": source, "fc_max": mx, "zonas": out}


def calcular(metrics, acts, plans, st, race_predictions=None, hr_zones=None):
    today = date.today()
    runs = [a for a in acts if a["type"] in RUN_TYPES and _d(a)]
    km = lambda a, b: round(sum(x["km"] or 0 for x in runs if a <= (today - _d(x)).days <= b), 1)
    last14, prev14 = km(0, 13), km(14, 27)
    change = round((last14 - prev14) / prev14 * 100) if prev14 else None
    long28 = max((x for x in runs if (today - _d(x)).days <= 27), key=lambda x: x["km"] or 0, default=None)
    last_run = max((_d(x) for x in runs), default=None)
    tasks = plan_tasks(plans, (today - timedelta(days=14)).isoformat(), (today - timedelta(days=1)).isoformat())
    done = sum(1 for t in tasks if t["status"] == "COMPLETE")
    L = metrics[-1] if metrics else {}
    return {
        "vo2max": {"actual": L.get("vo2max"), "hace_30d": _back(metrics, "vo2max", 30), "hace_60d": _back(metrics, "vo2max", 60)},
        "rhr": {"ult7": _avg([m["rhr"] for m in metrics[-7:]]), "prev21": _avg([m["rhr"] for m in metrics[-28:-7]])},
        "hrv": {"ult7": _avg([m["hrv"] for m in metrics[-7:]]), "rango": [L.get("hrv_low"), L.get("hrv_high")], "estado": L.get("hrv_status")},
        "sueno": {"ult7": _avg([m["sleep_h"] for m in metrics[-7:]]), "prev21": _avg([m["sleep_h"] for m in metrics[-28:-7]])},
        "carga": {"aguda": L.get("load_acute"), "cronica": L.get("load_chronic"), "acwr": L.get("acwr"), "estado": L.get("status")},
        "volumen": {"km_14d": last14, "km_14d_previos": prev14, "cambio_pct": change,
                    "alerta_10pct": bool(change is not None and change > 10)},
        "largo_28d": long28 and {"km": long28["km"], "min": long28["min"], "dia": (long28["start"] or "")[:10], "fc": long28["hr"]},
        "dias_sin_correr": (today - last_run).days if last_run else None,
        "fuerza_14d": sum(1 for a in acts if a["type"] == "strength_training" and _d(a) and (today - _d(a)).days < 14),
        "plan_14d": {"hechas": done, "programadas": len(tasks)},
        "zonas": zonas(acts, st, hr_zones),
        "prediccion_garmin": race_predictions,
    }
