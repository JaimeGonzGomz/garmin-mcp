"""Genera la recomendacion diaria. Uso: python -m coach.recommend

Proveedor con COACH_PROVIDER: gemini (por defecto, GEMINI_API_KEY) o anthropic (ANTHROPIC_API_KEY).
Modelo con COACH_MODEL.
"""
import json
import os
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

from coach.db import conn, dumps

PROVIDER = os.getenv("COACH_PROVIDER", "gemini")
MODEL = os.getenv("COACH_MODEL") or ("claude-sonnet-5-5" if PROVIDER == "anthropic" else "gemini-2.5-flash")

SYSTEM = """Eres un entrenador personal de resistencia. Recibes datos de Garmin del usuario
(HRV, sueno, readiness, carga, actividades recientes) y devuelves SOLO un JSON con:
{"today": {"titulo","tipo","duracion_min","intensidad","detalle","motivo"},
 "upcoming": [{"day":"YYYY-MM-DD","titulo","tipo","duracion_min","intensidad"} x6 dias siguientes],
 "analysis": "overview detallada en espanol (markdown): estado de recuperacion, carga, tendencias, riesgos"}
Si HRV/sueno/readiness indican fatiga, recomienda descanso o sesion suave. Se concreto y breve."""


def ask(prompt: str) -> str:
    if PROVIDER == "anthropic":
        import anthropic
        msg = anthropic.Anthropic().messages.create(
            model=MODEL, max_tokens=4000, system=SYSTEM, messages=[{"role": "user", "content": prompt}])
        return msg.content[0].text
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 8000},
    }
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_API_KEY"]})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:500]
            if e.code in (429, 500, 503) and attempt < 4:
                print(f"Gemini {e.code}, reintento {attempt + 1}/4: {detail}")
                time.sleep(15 * (attempt + 1))
                continue
            raise SystemExit(f"Gemini {e.code}: {detail}")


def main() -> None:
    db = conn()
    since = (date.today() - timedelta(days=14)).isoformat()
    metrics = [{"day": r["day"], "data": json.loads(r["data"])}
               for r in db.execute("select * from daily_metrics where day >= ? order by day", (since,))]
    acts = []
    for r in db.execute("select type, data from activities where start_time >= ? order by start_time", (since,)):
        a = json.loads(r["data"])
        acts.append({k: a.get(k) for k in ("activityName", "startTimeLocal", "distance", "duration", "averageHR",
                                           "maxHR", "aerobicTrainingEffect", "activityTrainingLoad")} | {"type": r["type"]})
    prompt = f"Hoy es {date.today().isoformat()}.\nMETRICAS:\n{dumps(metrics)[:60000]}\nACTIVIDADES:\n{dumps(acts)[:20000]}"
    text = ask(prompt)
    res = json.loads(text[text.index("{"): text.rindex("}") + 1])
    db.execute("insert or replace into recommendations (day, today, upcoming, analysis) values (?, ?, ?, ?)",
               (date.today().isoformat(), dumps(res["today"]), dumps(res["upcoming"]), res["analysis"]))
    db.commit()
    print("recomendacion guardada")


if __name__ == "__main__":
    main()
