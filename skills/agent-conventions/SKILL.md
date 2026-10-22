---
name: agent-conventions
description: >-
  Personal agent-kit operating conventions for Cursor, Claude Code, and Pi on
  macOS, Linux, and Windows. Use at the start of work in any repository, when
  choosing between skills, rules, hooks, and subagents, or when a new
  conversation needs orientation.
---

# Agent conventions

This user keeps **agent-kit** as one portable operating system for agents. Cursor (personal), Claude Code (work), and Pi (TUI/SDK) are hosts. macOS, Linux, Windows, and WSL are environments. Do not re-ask for conventions that this skill, `AGENTS.md`, or hooks already specify.

## Hosts

| Host | Always-on project file | User skills | Project skills |
| --- | --- | --- | --- |
| Cursor | `AGENTS.md` | `~/.cursor/skills` | `.cursor/skills` and `.claude/skills` |
| Claude Code | `CLAUDE.md` (must start with `@AGENTS.md`) | `~/.claude/skills` | `.claude/skills` only |
| Pi | cwd `AGENTS.md` / `CLAUDE.md` plus `~/.pi/agent/AGENTS.md` | `~/.agents/skills` | `.pi/skills` after project trust |

Install the kit **in the home of the process that runs the agent**. Native Windows Claude Code does not see WSL `~/.claude`. WSL Claude Code does not see `%USERPROFILE%\.claude`. Pi user config is a sibling repo linked into `~/.pi/agent`; this kit only shares skills through `~/.agents`.

## Work vs personal

- The kit is **personal identity**: how this user wants every agent to review, commit, and stay safe.
- **Work/employer repos**: overlay only. Use `sync_project.py --work`. Never overwrite an existing `CLAUDE.md` or `.claude/settings.json`. Never put employer secrets, internal URLs, or job-only workflows in agent-kit.
- **Personal repos**: full sync, including Cursor hooks.
- Stack-specific workflows stay in the repo that owns them.

## Read first

1. `AGENTS.md` if present; otherwise `CLAUDE.md`.
2. Project skills under `.claude/skills/` (and `.cursor/skills/` on Cursor).
3. Shared analysis and git skills are identical everywhere. Do not fork them.

## Layers

| Layer | Role |
| --- | --- |
| Skills (`SKILL.md`) | Portable workflows. Auto-apply when relevant. |
| `AGENTS.md` | Always-on project orientation. |
| Host rules | Cursor `.mdc` / Claude `.claude/rules`. File-type constraints. |
| `hooks/policy.json` | One safety policy. Cursor `hooks.json` and Claude `settings.json` are adapters. Pi is not wired yet. |
| Subagents | Isolated specialists. |

## Delegation

- Code review → `code-reviewer` (follows `code-review`).
- Architecture → `architecture-analyst` (follows `architecture-analysis`).
- Skill authoring → `manage-skills`. Quality pass → `skill-reviewer` / `review-skills`.
- Recurring work → `recurring-jobs` (host-specific mechanism).

## Git

Follow `git-commit` and `create-pull-request`. Never commit, push, amend, or force-push unless the user explicitly asked. Never skip hooks. Prefer POSIX git; on Windows PowerShell do not require bash HEREDOC.

## New work in a repo

Bootstrap with `scripts/sync_project.py` (`--work` on employer repos). Do not invent a parallel convention system per host or OS.
