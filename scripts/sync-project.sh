#!/usr/bin/env bash
set -euo pipefail
KIT="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$KIT/scripts/sync_project.py" "$@"
