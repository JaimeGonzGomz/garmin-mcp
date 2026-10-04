"""Genera la recomendacion diaria. Uso: python -m coach.recommend

Proveedor con COACH_PROVIDER: gemini (por defecto, GEMINI_API_KEY) o anthropic (ANTHROPIC_API_KEY).
Modelo con COACH_MODEL.
"""
import json
import os
from datetime import date, timedelta

import urllib.request

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
        text = ask(prompt)
    res = json.loads(text[text.index("{"): text.rindex("}") + 1])
    db.execute("insert or replace into recommendations (day, today, upcoming, analysis) values (?, ?, ?, ?)",
               (date.today().isoformat(), dumps(res["today"]), dumps(res["upcoming"]), res["analysis"]))
    db.commit()
    print("recomendacion guardada")


if __name__ == "__main__":
    main()
