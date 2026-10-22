#!/usr/bin/env python3
"""Claude Code PreToolUse / ConfigChange adapter over policy.json."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import (  # noqa: E402
    Decision,
    PayloadError,
    decide_config_change,
    decide_read,
    decide_shell,
    decide_writes,
    emit_claude,
    event_name,
    extract_tool_paths,
    malformed_decision,
    read_stdin,
    workspace_roots,
)

SHELL_TOOLS = {"Bash", "PowerShell", "Shell"}
READ_TOOLS = {"Read", "Grep", "Glob"}
WRITE_TOOLS = {
    "Write",
    "Edit",
    "Delete",
    "StrReplace",
    "EditNotebook",
    "NotebookEdit",
    "ApplyPatch",
}


def main() -> None:
    try:
        payload = read_stdin()
    except PayloadError:
        emit_claude(malformed_decision())
        return

    event = event_name(payload)
    if event.lower() == "configchange":
        emit_claude(decide_config_change(payload), event="ConfigChange")
        return

    tool = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None

    roots = workspace_roots(payload)
    if tool in SHELL_TOOLS:
        emit_claude(
            decide_shell(
                tool_input.get("command") or payload.get("command") or "",
                cwd=cwd,
                roots=roots,
            )
        )
        return

    if tool in READ_TOOLS:
        paths = extract_tool_paths(tool_input)
        raw = paths[0] if paths else (payload.get("file_path") or "")
        content = tool_input.get("content") or payload.get("content") or ""
        inspect = tool == "Read"
        emit_claude(
            decide_read(
                raw,
                content if isinstance(content, str) else "",
                inspect_disk=inspect,
                cwd=cwd,
            )
        )
        return

    if tool in WRITE_TOOLS:
        paths = extract_tool_paths(tool_input)
        emit_claude(decide_writes(paths, cwd, roots))
        return

    emit_claude(Decision("allow"))


if __name__ == "__main__":
    main()
