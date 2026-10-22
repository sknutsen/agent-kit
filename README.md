# agent-kit

One personal source of truth for how agents work: Cursor at home, Claude Code at work, Pi as a third host, on macOS, Linux, and Windows.

Git-synced across machines. Not a collaboration product. Not an employer config repo.

## Philosophy

**The kit is yours. Hosts and operating systems are adapters.**

- **Portable core:** `SKILL.md` workflows, `agents/*.md`, `AGENTS.md`, and `hooks/policy.json`.
- **Host adapters:** Cursor reads `~/.cursor` and `.cursor/`; Claude Code reads `~/.claude` and `.claude/`. Pi reads kit skills from `~/.agents/skills`. Pi *user config* (`~/.pi/agent`) lives in a sibling repo, not this kit.
- **OS adapters:** install with junctions on native Windows, symlinks on Unix. No git symlinks inside projects (they break on Windows).
- **Work vs personal:** the kit travels with you. Employer repos get an overlay (`sync_project.py --work`) and keep their own `CLAUDE.md` / settings if they already exist. Job-only workflows stay in those repos.

Cursor is the usual host for personal projects. Claude Code is the usual host for work. Pi is a terminal/SDK host that should feel like the same operator. Pi user config lives in a sibling repo, not this kit; skills still load through `~/.agents/skills`.

## How it actually loads

```text
agent-kit (this git repo)
  install.py  →  ~/.cursor/skills,agents,hooks     Cursor, this environment
              →  ~/.claude/skills,agents           Claude Code, this environment
              →  ~/.claude/settings.json           Claude PreToolUse + ConfigChange adapter
              →  ~/.agents/skills,agents           Agent Skills / Pi
  sync_project.py → <repo>/.claude/skills+agents   Claude Code + Cursor
                  → <repo>/.cursor/skills+agents   Cursor (duplicate copy, no symlinks)
                  → personal mode: project Cursor hooks + .claude/settings.json merge
                  → AGENTS.md + CLAUDE.md (@AGENTS.md import)
```

| Layer | Job | Cursor | Claude Code | Pi |
| --- | --- | --- | --- | --- |
| Skills | Workflows | `~/.cursor/skills` and `.claude/skills` | `~/.claude/skills` and `.claude/skills` | `~/.agents/skills` (Agent Skills spec) |
| Subagents | Isolated specialists | `~/.cursor/agents` | `~/.claude/agents` | `~/.agents/agents` |
| Always-on project text | Orientation | `AGENTS.md` | `CLAUDE.md` imports `@AGENTS.md` | cwd `AGENTS.md` / `CLAUDE.md` plus `~/.pi/agent/AGENTS.md` |
| Safety policy | Deny/ask | `~/.cursor/hooks.json` | `settings.json` → `claude-pretool.py` | not wired yet; see Safety |
| Cloud / other clone | Same repo files | project `.cursor` + `.claude` | project `.claude` (including hooks in personal mode) | sibling Pi config repo → `~/.pi/agent` |

Claude Code does **not** auto-load `AGENTS.md` unless `CLAUDE.md` imports it. Cursor **does** read `.claude/skills/` for compatibility. That is why project skills are written to `.claude/skills/` first.

**Windows native vs WSL are two homes.** `%USERPROFILE%\.claude` is not `\\wsl$\Ubuntu\home\you\.claude`. Install in the environment where the binary runs.

## Machine setup

Nix hosts (Apple Silicon macOS, Linux, WSL). Clone first — the installer links `~/.cursor`, `~/.claude`, and `~/.agents` to this checkout, not the Nix store:

```bash
git clone <this-repo> ~/Code/agent-kit   # Linux/WSL: ~/code/agent-kit
cd ~/Code/agent-kit                      # Linux/WSL: cd ~/code/agent-kit
nix run .#install
nix run .#status
```

`nix develop` (or direnv) puts `python3` and `git` on PATH. `nix run .` is the same as `nix run .#install`.

Home Manager (from `~/.nixconf` or similar):

```nix
# flake input: agent-kit.url = "github:sknutsen/agent-kit";
imports = [ inputs.agent-kit.homeModules.default ];
programs.agent-kit.enable = true;
```

Activation clones `https://github.com/sknutsen/agent-kit.git` into `~/Code/agent-kit` (Linux/WSL: `~/code/agent-kit`) when that path is missing. It does not pull an existing checkout.

Without Nix:

```bash
# macOS: ~/Code/agent-kit   Linux/WSL: ~/code/agent-kit
git clone <this-repo> ~/Code/agent-kit
cd ~/Code/agent-kit
python3 scripts/install.py
python3 scripts/install.py --status
```

```powershell
# Native Windows (PowerShell). Developer Mode helps file symlinks; directories use junctions.
py -3 scripts\install.py
py -3 scripts\install.py --status
```

`install.py` links Cursor, Claude Code, and `~/.agents` by default. `--no-claude`, `--no-cursor`, or `--no-agents-compat` if a machine should skip a host. Pi discovers kit skills from `~/.agents/skills`; its settings, MCP, and `auth.json` stay in the sibling Pi config repo.

Restart the host app. Confirm Cursor **Customize → Skills** / Hooks and Claude Code `/skills`. Pi needs `/reload` only after its own config repo is installed.

## Work machines (Claude Code)

On a job laptop, **user-level install is the default**. That puts review, git, and safety skills in *your* `%USERPROFILE%\.claude` (or WSL `~/.claude`) without committing anything to the employer repo.

Only run `sync_project.py --work` if you want those skills in that repository's git history and policy allows it. `--work` never writes hook config or `.claude/settings.json`. If `CLAUDE.md` already exists, sync will not overwrite it.

Do not copy employer runbooks, secrets, or internal URLs into agent-kit.

## Project setup

```bash
python3 scripts/sync_project.py ~/Code/your-repo          # personal
python3 scripts/sync_project.py ~/work/employer-repo --work
```

Personal mode merges kit hooks into existing `.cursor/hooks.json` and `.claude/settings.json` instead of replacing project-owned entries. It copies hook scripts into both `.cursor/hooks/` and `.claude/hooks/` so cloud Claude sessions, which do not read `~/.claude/settings.json`, still get the adapter. Project settings use `python3` plus `${CLAUDE_PROJECT_DIR}`; native Windows cloud/user installs still use `py -3` at user scope.

Then fill the **Project** section of that repo's `AGENTS.md`. Leave `CLAUDE.md` as the `@AGENTS.md` import unless the employer file already existed (sync will not overwrite it).

Re-run sync after changing a shared skill, agent, or hook. Managed copies listed in `agent-kit.json` are pruned when removed from `manifest.json`; project-owned files are left alone.

## Safety

One policy file: `hooks/policy.json`. Cursor and Claude Code both evaluate it. Pi does **not** yet: there is no extension wrapping these Python hooks. Treat Pi tool calls as ungated until that adapter exists.

| Action | Typical result |
| --- | --- |
| `curl` / `wget` / `Invoke-WebRequest` (including `sudo` wrappers), force-push, `rm -rf`, `Remove-Item -Recurse` | ask |
| `rm -rf /` and similar root wipes | deny |
| Private keys, KeePass, `.env`, sops | deny read (path deny beats `.env.example` allow) |
| Write inside the opened repo (including subdirs) or its Cursor project dir | allow |
| Write outside the repo (and shell redirects/`cp`/`mv`/`tee` to outside paths) | ask (approval is bound to that workspace) |
| Write to project hook config (`.cursor/hooks`, `.claude/settings.json`) | deny |
| Malformed hook JSON | deny (fail closed) |

Write scope expands to the git work tree and the matching `~/.cursor/projects/<slug>/` sidecar for the opened folder, so agent-tools/assets under that project dir are allowed. Outside-repo writes require approval instead of a hard deny; shell redirects are gated the same way so scripts cannot silently bypass the Write tool.

User/project hooks are **guardrails**. They are not MDM/managed policy: a project can still disable Claude hooks via settings if those files are edited outside this adapter. Use host sandboxing / managed settings when you need a non-bypassable boundary.

Cursor safety hooks are fail-closed. Claude Code uses PreToolUse `permissionDecision`. Claude Read inspects the file on disk because PreToolUse does not include file contents. PEM detection is line-anchored so docs that *mention* keys are not blocked.

## Recurring work

Host-specific. See `recurring-jobs`: Cursor `/loop` `/goal` `/automate`; Claude Code uses its own tools; Pi uses `pi --print` / `--mode rpc`. Never fake another host's APIs.

## Adding a skill later

Follow `manage-skills`. Keep skills OS-neutral. Shared names go in `manifest.json`. `--work` repos do not receive hook copies.

## Layout

```text
skills/     portable SKILL.md trees
agents/     subagent prompts
hooks/      policy.json, Cursor hooks, claude-pretool.py
scripts/    install.py, sync_project.py, install.ps1
templates/  AGENTS.md, CLAUDE.md, project-hooks.json
flake.nix   Nix apps, devShell, Home Manager module
```
