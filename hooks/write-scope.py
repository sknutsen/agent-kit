#!/usr/bin/env python3
"""Gate mutating file tools: allow in-repo (and bound dirs), ask outside, deny hook config."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import (  # noqa: E402
    PayloadError,
    decide_writes,
    emit_cursor,
    extract_tool_paths,
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
    tool_input = payload.get("tool_input") or {}
    paths = extract_tool_paths(tool_input)
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None
    emit_cursor(decide_writes(paths, cwd, workspace_roots(payload)))


if __name__ == "__main__":
    main()
