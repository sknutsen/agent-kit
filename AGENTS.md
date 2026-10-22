# AGENTS.md

Personal kit for Cursor, Claude Code, and Pi on macOS, Linux, and Windows. See README.md for philosophy.

## What to run

```bash
python3 scripts/install.py
python3 scripts/install.py --status
python3 scripts/sync_project.py <repo>
python3 scripts/sync_project.py <repo> --work
python3 scripts/test-hooks.sh
```

Native Windows: `py -3 scripts\install.py`.

## Layout

- `skills/` — portable workflows (linked into `~/.cursor/skills`, `~/.claude/skills`, and `~/.agents/skills`)
- `agents/` — subagents for Cursor, Claude Code, and Pi (`~/.agents/agents`)
- `hooks/policy.json` — one safety policy; Cursor and Claude adapters consume it. Pi is not wired yet.
- `CLAUDE.md` / `templates/CLAUDE.md` — `@AGENTS.md` import for Claude Code
- `manifest.json` — what sync copies into projects

## Conventions while editing the kit

- Shared analysis and git skills stay identical everywhere. Change them here, then re-sync.
- Local-only: `agent-conventions`, `manage-skills`, `review-skills`, `recurring-jobs`, `skill-reviewer`.
- Skills must work on Windows PowerShell and Unix shells unless they are explicitly host-specific.
- Do not put employer secrets or job-only runbooks in this repo. Pi `auth.json` and `~/.pi/agent` settings stay in the sibling Pi config repo.
- After hook changes, run `scripts/test-hooks.sh`.

## Tests

`scripts/test-hooks.sh` runs policy, installer, and sync tests. On Windows, `py -3 scripts\test_hooks.py`.
