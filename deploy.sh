#!/usr/bin/env bash
# Deploy GR8 idjango -> VPS /srv/idjango
# Single env file: idirect/.env
#
# Usage:
#   export VPS_HOST=root@168.231.102.28
#   ./deploy.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VPS_HOST="${VPS_HOST:-root@168.231.102.28}"
VPS_PATH="${VPS_PATH:-/srv/idjango}"

if [[ ! -f idirect/.env ]]; then
  echo "Missing idirect/.env — copy from example and set passwords:"
  echo "  cp idirect/.env.example idirect/.env"
  exit 1
fi

for key in DATABASE_NAME DATABASE_USER DATABASE_PASSWORD MYSQL_ROOT_PASSWORD; do
  if ! grep -q "^${key}=.\+" idirect/.env; then
    echo "idirect/.env: ${key} is missing or empty"
    exit 1
  fi
done

echo "==> Syncing project to ${VPS_HOST}:${VPS_PATH}"
rsync -avz --delete \
  --exclude '.git/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.env' \
  --exclude 'idirect/.env' \
  --exclude 'media/' \
  --exclude 'staticfiles/' \
  --exclude 'data/mysql/' \
  --exclude 'venv/' \
  --exclude 'my_env/' \
  --exclude '_tips/' \
  --exclude '*.xlsx' \
  --exclude 'idjango/' \
  --exclude '.env.root.bak' \
  "${ROOT}/" "${VPS_HOST}:${VPS_PATH}/"

scp "${ROOT}/idirect/.env" "${VPS_HOST}:${VPS_PATH}/idirect/.env"

echo "==> Building on VPS"
ssh "$VPS_HOST" bash -s <<EOF
set -euo pipefail
cd ${VPS_PATH}
mkdir -p idirect data/mysql media staticfiles
ln -sfn idirect/.env .env
test -f idirect/.env
docker network inspect npm-network >/dev/null 2>&1 || docker network create npm-network
docker rm -f idjango 2>/dev/null || true
docker compose --env-file idirect/.env build --no-cache idjango
docker compose --env-file idirect/.env up -d
docker compose --env-file idirect/.env exec -T idjango python manage.py migrate --noinput || true
docker compose --env-file idirect/.env exec -T idjango python manage.py collectstatic --noinput || true
docker compose --env-file idirect/.env ps
EOF

echo ""
echo "Done. Site: https://idjango.rbynex.in/"
