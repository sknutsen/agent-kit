---
name: create-pull-request
description: >-
  Push the current branch if needed and open a GitHub pull request with gh.
  Use when the user asks to create a pull request, open a PR, or requests a GitHub PR URL.
---

# Create pull request

Use `gh` for GitHub. Never update git config. Do not force-push to main/master; warn if the user asked for that.

## Snapshot the branch

In parallel:

- `git status`
- `git diff` (staged and unstaged)
- Check whether the branch tracks a remote and is up to date
- `git log` and `git diff <base>...HEAD` so the PR covers **all** commits since the branch diverged, not only the latest

## Then, in order

1. Create a branch if needed.
2. Push with `-u` if the branch has no upstream. Needs network.
3. Create the PR using a body form that works on this shell. Prefer piping to `--body-file -` so native PowerShell does not need bash HEREDOC.

**POSIX / Git Bash**

```bash
gh pr create --title "the pr title" --body-file - <<'EOF'
## Summary
-

## Test plan
- [ ]

EOF
```

**PowerShell** (native Windows)

```powershell
@"
## Summary
-

## Test plan
- [ ]
"@ | gh pr create --title "the pr title" --body-file -
```

Title and summary must reflect the full change set. Return the PR URL when done.
