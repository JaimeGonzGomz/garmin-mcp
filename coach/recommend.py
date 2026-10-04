"""Genera la recomendacion diaria. Uso: python -m coach.recommend

Proveedor con COACH_PROVIDER: gemini (por defecto, GEMINI_API_KEY) o anthropic (ANTHROPIC_API_KEY).
Modelos con COACH_MODEL (lista separada por comas; se prueban en orden).
"""
import json
import os
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

from coach.db import conn, dumps, get_extra, get_settings
from coach.estado import calcular
from coach.digest import activity_digest, day_digest, plan_info, plan_tasks, weekly_volume

PROVIDER = os.getenv("COACH_PROVIDER", "gemini")
DEFAULT_MODELS = "claude-sonnet-5-5" if PROVIDER == "anthropic" else (
    "gemini-3.8-flash,gemini-3.7-flash,gemini-3.5-flash-lite,gemini-2.5-flash,gemini-2.5-flash-lite")
MODELS = [m.strip() for m in (os.getenv("COACH_MODEL") or DEFAULT_MODELS).split(",") if m.strip()]

SYSTEM = """Eres un entrenador de running experto y prudente. Preparas al usuario para su maraton objetivo.
Recibes JSON con: objetivo y semanas restantes, contexto del usuario (plan/historial de otro proyecto), registro
reciente, metricas diarias de Garmin (HRV, sueno, readiness, carga, FC reposo, Body Battery), actividades recientes,
volumen semanal, el plan de Garmin Coach (info, y entrenos de los ultimos 10 dias con su estado de cumplimiento y de los proximos 14) y predicciones de carrera.
NO des por hecho decisiones del usuario que no consten en los datos, el registro o sus notas (p.ej. que ha cancelado o cambiado una sesion);
si algo es una suposicion, formulala como pregunta en "preguntas".
PRIORIDAD: el contexto del usuario (zonas, FC maxima, reglas, lesiones, plantilla semanal) manda sobre los datos y zonas
de Garmin; si dice que Garmin sobreestima zonas/FC/VO2max, usa SUS zonas por FC y trata esos valores de Garmin solo como
referencia. Las molestias o lesiones recientes (contexto, registro, notas) condicionan todo: ante duda, recorta y dilo.
Reglas: progresion de carga segura (no subir el volumen semanal mas de ~10%), semana de descarga cada 3-4 semanas,
afinar hacia la carrera (fases base/desarrollo/especifica/taper segun semanas restantes). Si HRV baja, sueno malo o
readiness bajo, recorta o descansa. Contrasta SIEMPRE el entreno de hoy con el que Garmin Coach tiene programado.
PASO (se envia al reloj Garmin, asi que todo paso de carrera debe llevar duracion o distancia y objetivo):
 {"tipo":"calentamiento|correr|recuperacion|enfriamiento|descanso","nombre":"...","detalle":"...",
  "duracion_min":10  (o "distancia_m":1000),
  "objetivo":{"tipo":"fc|ritmo|ninguno","min":..,"max":..}}   fc: bpm (min,max); ritmo: "m:ss" por km (min = el mas rapido).
 Series: {"repeticiones":6,"pasos":[PASO,PASO]}. Rodajes fáciles y tiradas largas: objetivo por FC segun las zonas del usuario.
 Para fuerza/descanso/bici: pasos solo descriptivos (nombre/detalle, sin objetivo).
Responde SOLO con un JSON (en espanol) con esta forma exacta:
{
 "fase": "base|desarrollo|especifica|taper",
 "resumen": "2-3 frases con la conclusion del dia",
 "today": {"titulo","tipo":"running|fuerza|bici|descanso|otro","duracion_min","distancia_km","intensidad":"descanso|suave|moderada|fuerte",
   "fc_objetivo":"rango o tope en lpm, p.ej. '<150' o '140-150'","ritmo_objetivo":"rango min/km orientativo, p.ej. '6:45-7:05'",
   "pasos":[PASO,...], "motivo",
   "garmin_coach": {"planificado":"que tiene programado Garmin hoy o 'nada'","decision":"seguir|modificar|sustituir|descanso","comentario"}},
 "upcoming": [{"day":"YYYY-MM-DD","titulo","tipo","duracion_min","distancia_km","intensidad","fc":"lpm esperada","ritmo":"min/km esperado","notas"} x7 dias siguientes],
 "analisis": {
   "recuperacion": {"estado":"bien|atencion|mal","texto"},
   "sueno": {"estado","texto"}, "hrv": {"estado","texto"}, "carga": {"estado","texto"},
   "progreso_objetivo": {"estado","texto"}, "semana": {"estado","texto"},
   "riesgos": ["..."], "recomendaciones": ["..."]},
 "estado": {"resumen":"overview de 2-3 frases de la forma actual",
   "estimaciones":{"vo2max":"tu lectura del VO2max (Garmin suele sobreestimar si el contexto lo dice)","maraton_ritmo":"min/km objetivo razonable hoy","maraton_tiempo":"h:mm","media_tiempo":"h:mm","10k_tiempo":"mm:ss","5k_tiempo":"mm:ss","confianza":"baja|media|alta","base":"en que datos te basas"},
   "ritmos_objetivo":[{"zona","ritmo":"m:ss/km","uso":"para que sesiones"}],
   "recomendaciones_generales":["3-6 recomendaciones de fondo para las proximas semanas"]},
 "preguntas": ["datos que te faltan y cambiarian la recomendacion (lesiones, fisio, sesiones sin registrar, fechas de hitos)"],
 "log_entry": "una frase para el registro del dia"
}
En "estado": usa estado_calculado (ritmos reales por zona, volumen, tendencias); las estimaciones de tiempos deben ser
prudentes, justificadas con datos y marcadas con su confianza; si no hay datos suficientes di que no se puede estimar.
OBLIGATORIO: todo entreno de carrera (hoy y los 7 dias de upcoming) lleva FC esperada y ritmo esperado en rangos concretos, coherentes
con las zonas del usuario y con los ritmos reales por zona de estado_calculado (en rodajes y tiradas largas manda la FC; el ritmo es
la consecuencia esperada, no el objetivo). Fuerza/descanso/bici: pon "—" en ritmo y, si procede, FC.
Cada "texto" con cifras concretas de los datos (valores, comparacion con tu media, tendencia). Si falta un dato, dilo."""


def ask(prompt: str, model: str) -> str:
    if PROVIDER == "anthropic":
        import anthropic
        msg = anthropic.Anthropic().messages.create(
            model=model, max_tokens=4000, system=SYSTEM, messages=[{"role": "user", "content": prompt}])
        return msg.content[0].text
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 16000},
    }
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_API_KEY"]})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.load(r)
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts if not p.get("thought"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 503) and attempt == 0:
                time.sleep(20)
                continue
            raise RuntimeError(f"HTTP {e.code}: {detail}")


RUN = ("running", "carrera", "correr", "run")


def missing_targets(res: dict) -> list[str]:
    """Entrenos de carrera sin FC o ritmo esperados (hoy y proximos dias)."""
    bad = []
    t = res.get("today") or {}
    if str(t.get("tipo", "")).lower() in RUN and not (t.get("fc_objetivo") and t.get("ritmo_objetivo")):
        bad.append("hoy")
    for u in res.get("upcoming") or []:
        if str(u.get("tipo", "")).lower() in RUN and not (u.get("fc") and u.get("ritmo")):
            bad.append(str(u.get("day", "?")))
    return bad


def generate(prompt: str) -> dict:
    errors, best = [], None
    for model in MODELS:
        try:
            text = ask(prompt, model)
            res = json.loads(text[text.index("{"): text.rindex("}") + 1])
            for k in ("today", "upcoming", "analisis"):
                res[k]
            falta = missing_targets(res)
            if falta:
                print("fallo -> %s: faltan FC/ritmo en %s" % (model, ", ".join(falta)))
                errors.append(f"{model}: faltan FC/ritmo en {', '.join(falta)}")
                if best is None or len(falta) < best[0]:
                    best = (len(falta), res, model)
                continue
            print("modelo usado:", model)
            return res
        except Exception as e:
            msg = f"{model}: {type(e).__name__}: {e}"
            print("fallo ->", msg)
            errors.append(msg)
    if best:  # ningun modelo cumplio todo: usar el que menos le faltaba
        print(f"aviso: usando {best[2]} aunque faltan FC/ritmo en {best[0]} entrenos")
        return best[1]
    raise SystemExit("Todos los modelos fallaron:\n" + "\n".join(errors))


def build_prompt(db) -> str:
    st = get_settings(db)
    today = date.today()
    since = (today - timedelta(days=21)).isoformat()
    metrics = [{"day": r["day"], **day_digest(json.loads(r["data"]))}
               for r in db.execute("select * from daily_metrics where day >= ? order by day", (since,))]
    metrics_long = [{"day": r["day"], **day_digest(json.loads(r["data"]))}
                    for r in db.execute("select * from daily_metrics order by day desc limit 60")][::-1]
    acts = [activity_digest(json.loads(r["data"]))
            for r in db.execute("select data from activities order by start_time")]
    plans = get_extra(db, "garmin_plans")
    log = [dict(r) for r in db.execute("select day, kind, text from log order by id desc limit 30")][::-1]
    try:
        weeks_left = max(0, (date.fromisoformat(st["goal_date"]) - today).days // 7)
    except ValueError:
        weeks_left = None
    payload = {
        "hoy": today.isoformat(),
        "objetivo": {"nombre": st["goal_name"], "fecha": st["goal_date"], "semanas_restantes": weeks_left,
                     "dias_entreno_por_semana": st["days_week"] or "no indicado"},
        "contexto_usuario": st["context"][:12000],
        "hitos_intermedios": st["milestones"][:1500],
        "historial_previo": st["history"][:14000],
        "registro_reciente": log,
        "metricas_diarias": metrics,
        "actividades_recientes": acts[-30:],
        "volumen_semanal": weekly_volume(acts),
        "plan_garmin_info": plan_info(plans),
        "plan_garmin_entrenos": plan_tasks(plans, (today - timedelta(days=10)).isoformat(), (today + timedelta(days=14)).isoformat()),
        "estado_calculado": calcular(metrics_long, acts, plans, st, get_extra(db, "race_predictions"), get_extra(db, "hr_zones")),
        "predicciones_carrera": (dumps(get_extra(db, "race_predictions"))[:2500]),
        "umbral_lactato": (dumps(get_extra(db, "lactate"))[:1500]),
        "resistencia": (dumps(get_extra(db, "endurance"))[:1500]),
    }
    return dumps(payload)


def main() -> None:
    db = conn()
    res = generate(build_prompt(db))
    today = date.today().isoformat()
    db.execute("insert or replace into reco (day, data) values (?, ?)", (today, dumps(res)))
    db.execute("delete from log where day = ? and kind = 'coach'", (today,))
    db.execute("insert into log (day, kind, text) values (?, 'coach', ?)", (today, str(res.get("log_entry") or res.get("resumen", ""))))
    db.commit()
    print("recomendacion guardada")
    if get_settings(db).get("auto_send") == "1":
        try:
            from coach.garmin_push import send_today
            print("enviado al reloj:", send_today(db)["name"])
        except Exception as e:  # no bloquear la recomendacion si Garmin falla
            print("aviso: no se pudo enviar al reloj:", e)


if __name__ == "__main__":
    main()
