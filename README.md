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

Garmin -> `coach/sync.py` -> SQLite -> `coach/recommend.py` (Claude) -> web (`coach/app.py`) en contentaimaker.com.
Todo corre en un servidor Hetzner (Ubuntu/Debian), sin Supabase.

## Despliegue (una vez, como root en el servidor)
    git clone https://github.com/JaimeGonzGomz/garmin-mcp /opt/garmin-coach
    cd /opt/garmin-coach && git checkout claude/serene-hamilton-388b4o
    bash deploy/setup.sh
Luego:
1. En tu PC: `python login.py`, y copia los tokens: `scp -r ~/.garmin-mcp-tokens root@IP:/opt/garmin-coach/data/tokens`
2. En el servidor, edita `/opt/garmin-coach/.env` y pon `GEMINI_API_KEY`; la contrasena de la web esta ahi (`COACH_PASSWORD`).
3. Primera ejecucion: `cd /opt/garmin-coach && set -a && . ./.env && .venv/bin/python -m coach.sync 14 && .venv/bin/python -m coach.recommend`
4. El DNS de contentaimaker.com (y www) debe apuntar a la IP del servidor.

Comprobar que se rellenan las metricas: `cd /opt/garmin-coach && sudo .venv/bin/python -m coach.digest` (los campos `null` no se encontraron en los datos de Garmin).

Actualizar: `bash /opt/garmin-coach/deploy/update.sh`. Se ejecuta solo cada dia a las 05:30 (systemd timer).
