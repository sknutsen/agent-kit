#!/usr/bin/env bash
set -euo pipefail
KIT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$KIT/scripts/test_hooks.py"
python3 "$KIT/scripts/test_install_sync.py"
python3 -m py_compile "$KIT"/hooks/*.py "$KIT"/scripts/*.py
