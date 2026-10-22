# AGENTS.md

This repository uses agent-kit. Shared skills (`code-review`, `architecture-analysis`, `git-commit`, `create-pull-request`) and shared subagents are copied into `.claude/` and `.cursor/` by `agent-kit/scripts/sync_project.py`. Do not fork those files here.

Project-only skills go in `.claude/skills/<name>/` under a **different** name (Cursor reads `.claude/skills/` too). File-type rules for Cursor stay in `.cursor/rules/*.mdc`.

`CLAUDE.md` starts with `@AGENTS.md` so Claude Code loads these instructions.

## Agent startup

1. Read this file (Claude Code: via `@AGENTS.md` in CLAUDE.md).
2. Use project skills that are not kit copies (see `.claude/agent-kit.json`).
3. Run and test using the commands below — do not invent a parallel workflow.
4. Treat hook denials as policy. Cursor and Claude Code evaluate the same `policy.json` through different adapters. User/project hooks are guardrails, not MDM-managed policy; do not disable them (`disableAllHooks`).
5. Delegate reviews to `code-reviewer` and architecture questions to `architecture-analyst`.

## Project

<!-- Fill this in. Delete bullets that do not apply. -->

- **What it is:**
- **How to run:**
- **Test / lint:**
- **Non-obvious caveats:** (auth, databases, generated code, deploy)
- **Secrets / env:** (what must exist, what must never be committed)
- **Host notes:** (Cursor vs Claude Code vs Pi only if they actually differ)

## Overlay

Conventions here override the kit when they conflict. Keep this section short.

- (none yet)
