#!/usr/bin/env python3
"""Gate destructive, network-heavy, and out-of-repo shell writes."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import (  # noqa: E402
    PayloadError,
    decide_shell,
    emit_cursor,
    malformed_decision,
    read_stdin,
    workspace_roots,
)


def main() -> None:
    try:
        payload = read_stdin()
    except PayloadError:
        emit_cursor(malformed_decision())
        return
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None
    emit_cursor(
        decide_shell(
            payload.get("command") or "",
            cwd=cwd,
            roots=workspace_roots(payload),
        )
    )


if __name__ == "__main__":
    main()
