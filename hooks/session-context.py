#!/usr/bin/env python3
"""Inject a short kit reminder at Cursor session start."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import PayloadError, emit, read_stdin, workspace_roots  # noqa: E402


def main() -> None:
    try:
        payload = read_stdin()
    except PayloadError:
        emit({"additional_context": "agent-kit session hook received malformed JSON."})
        return
    roots = workspace_roots(payload)
    lines = [
        "This user uses agent-kit across Cursor and Claude Code, on macOS, Linux, and Windows.",
        "Do not re-ask for conventions already in skills or AGENTS.md.",
        "AGENTS.md is the project source of truth. CLAUDE.md must import it with @AGENTS.md.",
        "Layers: skills = portable workflows; host rules/hooks = adapters; subagents = isolated specialists.",
        "Prefer code-reviewer for reviews and architecture-analyst for architecture/project analysis.",
        "Commit and open PRs only when asked; follow git-commit and create-pull-request.",
        "Recurring work: use the current host (Cursor /loop /goal /automate, or Claude Code equivalents). See recurring-jobs.",
        "Treat hook denials as policy. Do not evade them with shell redirects or scripts.",
        "User/project hooks are guardrails, not managed MDM policy. Shell sandboxing is still required for untrusted commands.",
    ]
    if not roots:
        lines.append("No workspace root was provided.")
    for root in roots:
        agents = root / "AGENTS.md"
        claude = root / "CLAUDE.md"
        if agents.is_file():
            lines.append(f"Read {agents} before other project files.")
        elif claude.is_file():
            lines.append(f"Read {claude} (no AGENTS.md present).")
        for stamp in (root / ".claude" / "agent-kit.json", root / ".cursor" / "agent-kit.json"):
            if stamp.is_file():
                lines.append(f"This repo is synced with agent-kit ({stamp}).")
                break
        names = []
        for skills in (root / ".claude" / "skills", root / ".cursor" / "skills"):
            if skills.is_dir():
                names.extend(
                    sorted(p.name for p in skills.iterdir() if (p / "SKILL.md").is_file())
                )
        names = sorted(set(names))
        if names:
            lines.append("Project skills: " + ", ".join(names) + ".")
    emit({"additional_context": "\n".join(lines)})


if __name__ == "__main__":
    main()
