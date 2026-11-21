# Garmin Coach

[Read in English](README.md)

Un entrenador personal construido sobre tus propios datos de Garmin Connect, más un **conector MCP** para que un asistente
de IA (Claude) pueda leerlos y hablar de ellos: *"¿qué hago hoy?"*, volumen semanal, recuperación, gráficos y, de forma
opcional, enviar un entreno estructurado al reloj.

> **Estado: proyecto personal, compartido tal cual. No es un servicio público ni lo desarrollo como tal.**
> Abajo explico por qué, por si le sirve a alguien que quiera hacer algo parecido.

## Qué hace

- **Web** (FastAPI + SQLite): sincronización diaria con Garmin, vista "hoy", volumen semanal y recomendación diaria.
- **Servidor MCP** (`coach/mcp_app.py`, Streamable HTTP, OAuth 2.1 con una contraseña que pones tú): herramientas de solo
  lectura como `training_summary`, `daily_metrics`, `activities`, `activity_detail`, `weekly_volume`, `hr_zones`,
  `race_predictions`, `scheduled_workouts`, `training_plan`, `metric_series` y `pace_by_hr_zone`. Al asistente se le
  indica que separe *lo que Garmin recomienda* de *su propia recomendación y por qué*, y que nunca invente
  recomendaciones de Garmin.
- **`send_workout` opcional** (apagado por defecto, `COACH_ENABLE_SEND=1`): construye un entreno de carrera
  estructurado, muestra una vista previa y solo lo envía tras confirmación explícita. No está probado a fondo;
  revisa cada entreno antes de usarlo.
- `server.py`: servidor MCP local mínimo (stdio) para Claude Desktop.
- `coach/garmin_dev.py`: receptor experimental de las notificaciones push del Garmin Connect Developer Program
  (ver "Por qué no es un servicio público").

## Por qué no es un servicio público

El objetivo era un conector que cualquiera pudiera añadir a Claude. Lo dejé por motivos que tienen que ver sobre todo con
lo que Garmin ofrece y con lo que cuesta operarlo con responsabilidad:

1. **Qué datos ofrece.** Los datos personales que lee este proyecto (readiness, estado de entrenamiento, carga,
   predicciones de carrera, plan de Garmin Coach) salen de endpoints de Garmin Connect que **no están documentados** en
   la referencia pública de la API Personal (28 endpoints `GET` de solo lectura cuando lo revisé). Funcionan con tu
   cuenta, pero Garmin puede cambiarlos o quitarlos sin aviso, y no son una base sólida para un servicio de terceros.
2. **La vía oficial para varios usuarios es limitada.** La descripción pública del programa Garmin Connect Developer
   presenta el nivel Starter como solo push y sin histórico. En mis pruebas con una sola cuenta llegan actividades,
   resúmenes diarios, sueño, HRV, estrés, SpO2, respiración y similares; no vi readiness, estado de entrenamiento, carga
   ni plan de Garmin Coach. Un usuario nuevo empezaría con el historial vacío y "¿qué recomienda Garmin hoy?" no se
   podría responder.
3. **Almacenamiento y responsabilidad.** El push obliga al operador a recibir y guardar los datos de salud de cada
   usuario. Eso trae obligaciones de protección de datos (RGPD en mi caso), condiciones de uso y una exposición legal
   que recae en una persona física si no hay una empresa detrás. Para un servicio que aporta poco más de lo que ya
   muestran las apps de Garmin, no quise asumirlo.
4. **Condiciones sobre IA.** Pasar los datos de un usuario a un asistente de IA es un uso que las reglas del programa
   tratan con cuidado. Pedí aclaraciones a Garmin y solo recibí una respuesta automática genérica, así que no quise
   construir sobre una suposición.

Nada de esto es una crítica a Garmin; es una foto de lo que encontré. Si piensas hacer algo parecido, comprueba tú las
condiciones vigentes del programa.

## Usarlo para ti

Necesitas tu propia cuenta de Garmin Connect y un servidor u ordenador que controles.

```bash
python -m venv .venv
.venv/bin/pip install -r coach/requirements.txt      # Windows: .venv\Scripts\pip
python login.py                                       # login único; guarda tokens en ~/.garmin-mcp-tokens
```

- **Local con Claude Desktop:** añade un servidor MCP que ejecute `python server.py` en `claude_desktop_config.json`.
- **Web + conector remoto:** `deploy/setup.sh` lo instala en Ubuntu/Debian (Caddy para HTTPS + systemd):
  `DOMAIN=ejemplo.com bash deploy/setup.sh`, luego copia tus tokens a `data/tokens` y rellena `.env`.
  Añade el conector en Claude con `https://tu-dominio/mcp`; inicia sesión en `/oauth/login` con tu contraseña.
- `deploy/audit.sh` es una auditoría de seguridad del servidor de solo lectura; `deploy/run-as-coach.sh` ejecuta el
  servicio con un usuario sin privilegios.

Configuración (variables de entorno en `.env`):

| Variable | Para qué |
|---|---|
| `COACH_PASSWORD` | Contraseña de la web y del login del conector |
| `SESSION_SECRET` | Clave para firmar cookies |
| `COACH_PUBLIC_URL` | URL pública base, p. ej. `https://ejemplo.com` (obligatoria para el conector) |
| `COACH_DATA` | Carpeta de datos (por defecto `./data`) |
| `GEMINI_API_KEY` / `ANTHROPIC_API_KEY`, `COACH_PROVIDER`, `COACH_MODEL` | Solo para la recomendación diaria de la web |
| `COACH_ENABLE_SEND` | `1` activa `send_workout` |
| `GARMIN_PUSH_TOKEN` | Solo para el receptor push experimental |
| `PRIVACY_CONTROLLER_NAME`, `PRIVACY_CONTACT_EMAIL`, `PRIVACY_COUNTRY`, `PRIVACY_HOSTING` | Rellenan la página de privacidad |

## Notas importantes

- **No oficial.** Sin relación, aval ni soporte de Garmin Ltd. ni de Anthropic. Usa la librería comunitaria
  `garminconnect` y endpoints no documentados; su uso puede chocar con las condiciones de Garmin. Úsalo solo con tu
  propia cuenta y bajo tu responsabilidad.
- **No es consejo médico.** Las sugerencias de entrenamiento son orientativas. Para y consulta a un profesional si te
  encuentras mal.
- **Seguridad.** El repositorio no contiene credenciales. Mantén en privado `.env`, `data/` y tus tokens de Garmin.
  Las páginas legales (`coach/legal.py`) son borradores que escribí para mi despliegue y **no** son asesoramiento
  jurídico; haz que las revise un profesional antes de reutilizarlas.
- **Aún no hay licencia**, así que por defecto todos los derechos están reservados. Pregunta si quieres reutilizar el código.

## Contacto

Preguntas sobre el proyecto o ideas en las que apoyarse: **jaimegonzgomz@gmail.com**. Si a alguien de Garmin le resulta
útil esta idea, encantado de hablar.
