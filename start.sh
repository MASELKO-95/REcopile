#!/usr/bin/env bash
set -euo pipefail
RECOMPILE_PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$RECOMPILE_PROJECT_DIR"
if [[ ! -f frontend/dist/client/index.html ]]; then
    if [[ ! -d frontend/node_modules ]]; then
        npm --prefix frontend ci --no-audit --no-fund
    fi
    npm --prefix frontend run build
fi
exec python3 launcher.py "$@"
