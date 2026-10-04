#!/usr/bin/env bash
# Actualizar: git pull + dependencias + reinicio
set -euo pipefail
cd /opt/garmin-coach
git pull
.venv/bin/pip install -q -r coach/requirements.txt
systemctl restart garmin-coach
