#!/usr/bin/env bash
# Instalacion unica en Ubuntu/Debian (ejecutar como root desde el repo clonado en /opt/garmin-coach).
# Sustituye cualquier servidor web anterior por Caddy (HTTPS automatico) sirviendo contentaimaker.com.
set -euo pipefail
DOMAIN="${DOMAIN:-contentaimaker.com}"
APP=/opt/garmin-coach
cd "$APP"

apt-get update
apt-get install -y python3 python3-venv python3-pip curl debian-keyring debian-archive-keyring apt-transport-https gpg
# quitar servidores web anteriores
for s in apache2 nginx; do systemctl disable --now "$s" 2>/dev/null || true; done
# Caddy
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy.list
  sed -i 's#^deb #deb [signed-by=/usr/share/keyrings/caddy.gpg] #' /etc/apt/sources.list.d/caddy.list
  apt-get update && apt-get install -y caddy
fi
cat > /etc/caddy/Caddyfile <<CADDY
$DOMAIN, www.$DOMAIN {
	reverse_proxy 127.0.0.1:8000
}
CADDY

python3 -m venv .venv
.venv/bin/pip install -q -r coach/requirements.txt
mkdir -p data

if [ ! -f .env ]; then
  cat > .env <<ENV
COACH_PASSWORD=$(openssl rand -base64 12)
SESSION_SECRET=$(openssl rand -hex 32)
ANTHROPIC_API_KEY=PEGA_AQUI_TU_CLAVE
ENV
  chmod 600 .env
  echo ">>> Contrasena de la web generada en $APP/.env (COACH_PASSWORD). Edita ANTHROPIC_API_KEY ahi."
fi

cat > /etc/systemd/system/garmin-coach.service <<UNIT
[Unit]
Description=Garmin Coach web
After=network.target
[Service]
WorkingDirectory=$APP
EnvironmentFile=$APP/.env
ExecStart=$APP/.venv/bin/uvicorn coach.app:app --host 127.0.0.1 --port 8000
Restart=always
[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/garmin-coach-daily.service <<UNIT
[Unit]
Description=Garmin Coach sync + recomendacion
[Service]
Type=oneshot
WorkingDirectory=$APP
EnvironmentFile=$APP/.env
ExecStart=/bin/sh -c '$APP/.venv/bin/python -m coach.sync 7 && $APP/.venv/bin/python -m coach.recommend'
UNIT
cat > /etc/systemd/system/garmin-coach-daily.timer <<UNIT
[Unit]
Description=Garmin Coach diario
[Timer]
OnCalendar=*-*-* 05:30:00
Persistent=true
[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
systemctl enable --now garmin-coach garmin-coach-daily.timer
systemctl restart caddy
echo "Listo. Falta: copiar tokens de Garmin a $APP/data/tokens y poner ANTHROPIC_API_KEY en $APP/.env"
