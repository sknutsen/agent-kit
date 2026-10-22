---
name: git-commit
description: >-
  Create git commits using this user's safety protocol and message style.
  Use when the user asks to commit, write a commit message, or stage and commit changes.
---

# Git commit

Only create commits when the user explicitly asked. If unclear, ask.

## Protocol

Never update git config. Never `--no-verify` / `--no-gpg-sign` unless the user asked. Never force-push or hard-reset unless the user asked in this query. Never `git commit --amend` unless all of: the user asked to amend, HEAD was created by you in this conversation, and the commit has not been pushed. If a commit failed a hook, fix it and make a **new** commit; do not amend.

Do not use `git` `-i` (no `git add -i`, no `git rebase -i`).

## Before committing

Run in parallel:

- `git status`
- `git diff` (staged and unstaged)
- `git log` (recent messages, match style)

Do not commit secrets (`.env`, `credentials.json`, key files). Warn if the user asked to include them.

Draft a 1–2 sentence message that says **why**, not a file list. Use `add` / `update` / `fix` accurately.

## Commit

Stage the relevant files. Then commit in a way that works on this shell:

**POSIX / Git Bash**

```bash
git commit -m "$(cat <<'EOF'
Commit message here.

EOF
)"
```

**PowerShell** (native Windows, no bash HEREDOC):

```powershell
git commit -m @"
Commit message here.
"@
```

If there is nothing to commit, do not create an empty commit.

Afterward, run `git status` and report the result. Do not push unless the user asked.
