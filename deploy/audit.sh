#!/bin/bash
# Auditoria de solo lectura del servidor. No modifica nada ni imprime secretos.
# Uso: bash /opt/garmin-coach/deploy/audit.sh
APP=/opt/garmin-coach
sec() { printf '\n== %s ==\n' "$1"; }

sec "PUERTOS EN ESCUCHA"
ss -tlnp 2>/dev/null | awk 'NR==1 || /LISTEN/ {print $1, $4}'

sec "SSH (configuracion efectiva)"
sudo sshd -T 2>/dev/null | grep -iE '^(permitrootlogin|passwordauthentication|pubkeyauthentication|port|kbdinteractiveauthentication|allowusers) '

sec "FIREWALL / PROTECCIONES"
echo "ufw: $(systemctl is-active ufw 2>&1)"; sudo ufw status 2>/dev/null | head -15
echo "fail2ban: $(systemctl is-active fail2ban 2>&1)"
echo "unattended-upgrades: $(systemctl is-active unattended-upgrades 2>&1)"

sec "PERMISOS (deberian ser .env=600, data=700, tokens=700)"
for f in $APP/.env $APP/data $APP/data/tokens $APP/data/coach.db; do stat -c '%a %U:%G %n' "$f" 2>&1; done

sec "SERVICIO garmin-coach"
systemctl show garmin-coach -p User -p ExecStart 2>/dev/null | sed 's/--.*//' | cut -c1-120
echo "escucha solo en local: $(ss -tlnp 2>/dev/null | grep -c '127.0.0.1:8000')"

sec "CADDY"
systemctl is-active caddy; sudo caddy version 2>/dev/null | head -1
grep -vE '^\s*#' /etc/caddy/Caddyfile 2>/dev/null

sec "ACTUALIZACIONES"
echo "kernel en uso: $(uname -r)"
ls /var/run/reboot-required 2>&1 | head -1
echo "paquetes actualizables: $(apt list --upgradable 2>/dev/null | grep -c upgradable)"
echo "de seguridad: $(apt list --upgradable 2>/dev/null | grep -c -- -security)"

sec "USUARIOS CON SHELL Y CON SUDO"
grep -vE 'nologin|false' /etc/passwd | cut -d: -f1,7
getent group sudo

sec "INTENTOS SSH FALLIDOS (ultimas 24h)"
sudo journalctl -u ssh --since "24 hours ago" 2>/dev/null | grep -c "Failed password"

sec "ESTADO DEL REPO"
git -C $APP status -sb | head -3
echo; echo "FIN"
