# garmin-mcp

Servidor MCP para Garmin Connect (HRV, sueno, actividades, readiness, subida de entrenos).

## Instalacion
    py -3.10 -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    .venv\Scripts\python.exe login.py

## Claude Desktop
Anade en claude_desktop_config.json un servidor "garmin" que ejecute .venv\Scripts\python.exe server.py.

Los tokens se guardan en ~/.garmin-mcp-tokens (fuera del repo).

# Garmin Coach (recomendacion diaria)

Flujo: Garmin -> `coach/sync.py` -> Supabase -> `coach/recommend.py` (Claude) -> Supabase -> `web/index.html`.
Se ejecuta a diario con `.github/workflows/daily.yml`.

## Pasos de puesta en marcha
1. Crear proyecto en Supabase y ejecutar `supabase/schema.sql` en el SQL Editor.
2. Crear tu usuario (email+contrasena) desde la web o Auth > Users y copiar su UUID.
3. `python login.py` en tu PC (genera tokens de Garmin).
4. Con las variables `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `COACH_USER_ID`: `python -m coach.upload_tokens`.
5. Secrets de GitHub: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `COACH_USER_ID`, `ANTHROPIC_API_KEY`.
6. Poner URL y anon key en `web/index.html` y publicar `web/` (GitHub Pages o Netlify).
