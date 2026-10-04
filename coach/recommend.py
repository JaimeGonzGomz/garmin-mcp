"""Genera la recomendacion diaria con Claude y la guarda en Supabase. Uso: python -m coach.recommend

Variables: SUPABASE_URL, SUPABASE_SERVICE_KEY, COACH_USER_ID, ANTHROPIC_API_KEY
"""
import json
import os
from datetime import date, timedelta

import anthropic

from coach.sync import sb

MODEL = os.getenv("COACH_MODEL", "claude-sonnet-5-5")

SYSTEM = """Eres un entrenador personal de resistencia. Recibes datos de Garmin del usuario
(HRV, sueno, readiness, carga, actividades recientes) y devuelves SOLO un JSON con:
{"today": {"titulo","tipo","duracion_min","intensidad","detalle","motivo"},
 "upcoming": [{"day":"YYYY-MM-DD","titulo","tipo","duracion_min","intensidad"} x6 dias siguientes],
 "analysis": "overview detallada en espanol (markdown): estado de recuperacion, carga, tendencias, riesgos"}
Si HRV/sueno/readiness indican fatiga, recomienda descanso o sesion suave. Se concreto y breve."""


def main() -> None:
    db, user_id = sb(), os.environ["COACH_USER_ID"]
    since = (date.today() - timedelta(days=14)).isoformat()
    metrics = db.table("daily_metrics").select("day,data").eq("user_id", user_id).gte("day", since).order("day").execute().data
    acts = db.table("activities").select("start_time,type,data").eq("user_id", user_id).gte("start_time", since).order("start_time").execute().data
    slim_acts = [
        {k: a["data"].get(k) for k in ("activityName", "startTimeLocal", "distance", "duration", "averageHR", "maxHR", "aerobicTrainingEffect", "activityTrainingLoad")} | {"type": a["type"]}
        for a in acts
    ]
    prompt = f"Hoy es {date.today().isoformat()}.\nMETRICAS:\n{json.dumps(metrics, default=str)[:60000]}\nACTIVIDADES:\n{json.dumps(slim_acts, default=str)[:20000]}"
    msg = anthropic.Anthropic().messages.create(
        model=MODEL, max_tokens=4000, system=SYSTEM, messages=[{"role": "user", "content": prompt}]
    )
    text = msg.content[0].text
    result = json.loads(text[text.index("{"): text.rindex("}") + 1])
    db.table("recommendations").upsert({
        "user_id": user_id,
        "day": date.today().isoformat(),
        "today": result["today"],
        "upcoming": result["upcoming"],
        "analysis": result["analysis"],
    }).execute()
    print("recomendacion guardada")


if __name__ == "__main__":
    main()
