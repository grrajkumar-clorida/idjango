#!/usr/bin/env bash
# Generate secure secrets into idirect/.env only.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DATABASE_NAME="${DATABASE_NAME:-idirect}"
DATABASE_USER="${DATABASE_USER:-idirect_app}"
DATABASE_PASSWORD="$(openssl rand -base64 36 | tr -d '/+=' | head -c 32)"
MYSQL_ROOT_PASSWORD="$(openssl rand -base64 36 | tr -d '/+=' | head -c 32)"
SECRET_KEY="$(openssl rand -base64 64 | tr -d '/+=' | head -c 50)"

if [[ -f idirect/.env ]]; then
  echo "Refusing to overwrite existing idirect/.env (delete it first if you want new secrets)."
  exit 1
fi

cp idirect/.env.example idirect/.env
export DATABASE_NAME DATABASE_USER DATABASE_PASSWORD MYSQL_ROOT_PASSWORD SECRET_KEY
python3 <<'PY'
from pathlib import Path
import os

vals = {
    "SECRET_KEY": os.environ["SECRET_KEY"],
    "DATABASE_NAME": os.environ["DATABASE_NAME"],
    "DATABASE_USER": os.environ["DATABASE_USER"],
    "DATABASE_PASSWORD": os.environ["DATABASE_PASSWORD"],
    "MYSQL_ROOT_PASSWORD": os.environ["MYSQL_ROOT_PASSWORD"],
    "DATABASE_HOST": "idjango-mysql",
    "DATABASE_PORT": "3306",
    "DATABASE_USE_SOCKET": "False",
    "DEBUG": "False",
    "ALLOWED_HOSTS": "idjango.rbynex.in,localhost,127.0.0.1",
}
path = Path("idirect/.env")
out, seen = [], set()
for line in path.read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k = line.split("=", 1)[0].strip()
        if k in vals:
            out.append(f"{k}={vals[k]}")
            seen.add(k)
            continue
    out.append(line)
for k, v in vals.items():
    if k not in seen:
        out.append(f"{k}={v}")
path.write_text("\n".join(out) + "\n")
PY

# Optional convenience for compose default .env discovery
ln -sfn idirect/.env .env

echo "Wrote secure secrets to idirect/.env only"
echo "DB name: ${DATABASE_NAME}"
echo "DB user: ${DATABASE_USER}"
echo "Passwords are only in idirect/.env (not printed here)."
echo ""
echo "Run with:"
echo "  ./dc.sh up -d"
echo "  # or: docker compose --env-file idirect/.env up -d"
