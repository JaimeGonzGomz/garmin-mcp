# garmin-mcp

Servidor MCP para Garmin Connect (HRV, sueno, actividades, readiness, subida de entrenos).

## Instalacion
    py -3.10 -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    .venv\Scripts\python.exe login.py

## Claude Desktop
Anade en claude_desktop_config.json un servidor "garmin" que ejecute .venv\Scripts\python.exe server.py.

Los tokens se guardan en ~/.garmin-mcp-tokens (fuera del repo).
