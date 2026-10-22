---
name: manage-skills
description: >-
  Create, place, update, or retire agent-kit skills, subagents, hooks, and
  project overlays for Cursor, Claude Code, and Pi. Use when the user wants a
  new skill, to turn a workflow into a skill, to bootstrap a repo, or to
  install the kit on a new machine.
---

# Manage skills

This kit is the source of truth. Host directories (`~/.cursor`, `~/.claude`, `~/.agents`) are install targets, not places to edit. Pi user config (`~/.pi/agent`, including `auth.json`) lives in a sibling repo, never here.

## Decide placement

| Kind | Location |
| --- | --- |
| Identical everywhere (review, analysis, git, safety policy) | kit `skills/` / `agents/` / `hooks/policy.json`; `shared_*` in `manifest.json` |
| Personal, every host on this user account (meta, conventions) | kit `local_only_*` |
| One repo's stack or product workflow | `<repo>/.claude/skills/<name>/` (portable). Cursor also reads that path. |
| Cursor-only file-type constraints | `<repo>/.cursor/rules/<name>.mdc` |
| Employer-only workflow | that work repo, never agent-kit |
| Hard deny/ask | `hooks/policy.json`; adapters pick it up after reinstall/re-sync |
| Pi user config | sibling Pi repo, never this kit. This kit only shares skills via `~/.agents` |

Default new skills to **auto-invoke**. Set `disable-model-invocation: true` only when implicit use would be noisy.

Skills must stay **OS-neutral**: no `/Users/zdk` paths, no macOS-only assumptions. Python hooks are the portable runtime. Do not add bash-only or PowerShell-only skill scripts unless the skill is explicitly host-specific.

`name` is lowercase hyphenated and **must match the folder name**. Description is third person, WHAT + WHEN.

After writing, run `review-skills`.

## Install a machine / environment

```bash
python3 scripts/install.py          # macOS/Linux/WSL: Cursor + Claude Code + ~/.agents
nix run .#install                   # Nix hosts, from a checkout
py -3 scripts\install.py           # native Windows
python3 scripts/install.py --status
```

Run this **inside** WSL if Claude Code runs in WSL. Native Windows is a separate home.

## Bootstrap a project

```bash
python3 scripts/sync_project.py /path/to/repo           # personal
python3 scripts/sync_project.py /path/to/repo --work    # employer repo
```

`--work` copies skills and agents and will create `AGENTS.md` / `CLAUDE.md` only if missing. It never writes hook config or `.claude/settings.json`. Personal mode merges kit hook entries and prunes only previously stamped managed files.

Then fill the **Project** section of `AGENTS.md`. Commit `.claude/`, `.cursor/` (if present), `AGENTS.md`, and `CLAUDE.md`.

## Retire

Remove the folder, drop it from `manifest.json`, re-sync projects that still copy it. Sync deletes only names recorded in that repo's `agent-kit.json`.
