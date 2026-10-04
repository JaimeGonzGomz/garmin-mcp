"""Genera la recomendacion diaria con Claude. Uso: python -m coach.recommend (requiere ANTHROPIC_API_KEY)"""
import json
import os
from datetime import date, timedelta

import anthropic

from coach.db import conn, dumps

MODEL = os.getenv("COACH_MODEL", "claude-sonnet-5-5")

SYSTEM = """Eres un entrenador personal de resistencia. Recibes datos de Garmin del usuario
(HRV, sueno, readiness, carga, actividades recientes) y devuelves SOLO un JSON con:
{"today": {"titulo","tipo","duracion_min","intensidad","detalle","motivo"},
 "upcoming": [{"day":"YYYY-MM-DD","titulo","tipo","duracion_min","intensidad"} x6 dias siguientes],
 "analysis": "overview detallada en espanol (markdown): estado de recuperacion, carga, tendencias, riesgos"}
Si HRV/sueno/readiness indican fatiga, recomienda descanso o sesion suave. Se concreto y breve."""


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
    msg = anthropic.Anthropic().messages.create(
        model=MODEL, max_tokens=4000, system=SYSTEM, messages=[{"role": "user", "content": prompt}])
    text = msg.content[0].text
    res = json.loads(text[text.index("{"): text.rindex("}") + 1])
    db.execute("insert or replace into recommendations (day, today, upcoming, analysis) values (?, ?, ?, ?)",
               (date.today().isoformat(), dumps(res["today"]), dumps(res["upcoming"]), res["analysis"]))
    db.commit()
    print("recomendacion guardada")


if __name__ == "__main__":
    main()
