#!/usr/bin/env python3
"""Block reads of secret files. Cursor beforeReadFile / Tab read."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import (  # noqa: E402
    PayloadError,
    decide_read,
    emit_cursor,
    malformed_decision,
    read_stdin,
)


def main() -> None:
    try:
        payload = read_stdin()
    except PayloadError:
        emit_cursor(malformed_decision())
        return
    attachments = payload.get("attachments") or []
    paths = [payload.get("file_path") or ""]
    if isinstance(attachments, list):
        for item in attachments:
            if isinstance(item, dict) and isinstance(item.get("file_path"), str):
                paths.append(item["file_path"])
    content = payload.get("content") or ""
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None
    for path in paths:
        decision = decide_read(path, content if isinstance(content, str) else "", cwd=cwd)
        if decision.permission != "allow":
            emit_cursor(decision)
            return
    emit_cursor(decide_read(paths[0], content if isinstance(content, str) else "", cwd=cwd))


if __name__ == "__main__":
    main()
