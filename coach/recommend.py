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

from coach.db import conn, dumps

PROVIDER = os.getenv("COACH_PROVIDER", "gemini")
DEFAULT_MODELS = "claude-sonnet-5-5" if PROVIDER == "anthropic" else (
    "gemini-3.8-flash,gemini-3.7-flash,gemini-3.5-flash-lite,gemini-2.5-flash,gemini-2.5-flash-lite")
MODELS = [m.strip() for m in (os.getenv("COACH_MODEL") or DEFAULT_MODELS).split(",") if m.strip()]

SYSTEM = """Eres un entrenador personal de resistencia. Recibes datos de Garmin del usuario
(HRV, sueno, readiness, carga, actividades recientes) y devuelves SOLO un JSON con:
{"today": {"titulo","tipo","duracion_min","intensidad","detalle","motivo"},
 "upcoming": [{"day":"YYYY-MM-DD","titulo","tipo","duracion_min","intensidad"} x6 dias siguientes],
 "analysis": "overview detallada en espanol (markdown): estado de recuperacion, carga, tendencias, riesgos"}
Si HRV/sueno/readiness indican fatiga, recomienda descanso o sesion suave. Se concreto y breve."""


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


def generate(prompt: str) -> dict:
    errors = []
    for model in MODELS:
        try:
            text = ask(prompt, model)
            res = json.loads(text[text.index("{"): text.rindex("}") + 1])
            for k in ("today", "upcoming", "analysis"):
                res[k]
            print("modelo usado:", model)
            return res
        except Exception as e:
            msg = f"{model}: {type(e).__name__}: {e}"
            print("fallo ->", msg)
            errors.append(msg)
    raise SystemExit("Todos los modelos fallaron:\n" + "\n".join(errors))


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
    res = generate(prompt)
    db.execute("insert or replace into recommendations (day, today, upcoming, analysis) values (?, ?, ?, ?)",
               (date.today().isoformat(), dumps(res["today"]), dumps(res["upcoming"]), res["analysis"]))
    db.commit()
    print("recomendacion guardada")


if __name__ == "__main__":
    main()
