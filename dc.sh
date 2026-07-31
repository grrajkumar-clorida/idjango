#!/usr/bin/env bash
# Always interpolate from idirect/.env (single source of truth).
set -euo pipefail
cd "$(dirname "$0")"
exec docker compose --env-file idirect/.env "$@"
