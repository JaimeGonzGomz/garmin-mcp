#!/usr/bin/env bash
# Ejecuta la web y el timer diario con un usuario sin privilegios ("coach") en vez de root.
# Uso: sudo bash /opt/garmin-coach/deploy/run-as-coach.sh
# Idempotente. Para deshacer: sudo bash /opt/garmin-coach/deploy/run-as-coach.sh --undo
set -euo pipefail
APP=/opt/garmin-coach
UNITS="garmin-coach garmin-coach-daily"

if [ "${1:-}" = "--undo" ]; then
  for u in $UNITS; do rm -rf "/etc/systemd/system/$u.service.d"; done
  chown -R root:root "$APP/data"
  systemctl daemon-reload && systemctl restart garmin-coach
  echo "Revertido: el servicio vuelve a correr como root."; exit 0
fi

id coach >/dev/null 2>&1 || useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin coach

systemctl stop garmin-coach
# El codigo y .env siguen siendo de root (solo lectura para coach); coach solo escribe en data/
chown -R coach:coach "$APP/data"
chmod 700 "$APP/data"; chmod 600 "$APP/data/coach.db" 2>/dev/null || true
[ -d "$APP/data/tokens" ] && chmod -R go-rwx "$APP/data/tokens"
chmod 755 "$APP" "$APP/coach"

for u in $UNITS; do
  mkdir -p "/etc/systemd/system/$u.service.d"
  cat > "/etc/systemd/system/$u.service.d/hardening.conf" <<CONF
[Service]
User=coach
Group=coach
Environment=PYTHONDONTWRITEBYTECODE=1
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$APP/data
CONF
done

systemctl daemon-reload
systemctl restart garmin-coach
sleep 2
systemctl is-active garmin-coach
ps -o user=,cmd= -C uvicorn
echo "Listo. Si algo falla: sudo bash $APP/deploy/run-as-coach.sh --undo"
