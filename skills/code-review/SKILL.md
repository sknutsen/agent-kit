---
name: code-review
description: >-
  Review code for correctness, security, regressions, and maintainability.
  Use when reviewing pull requests, diffs, commits, or recently edited files,
  when the user asks for a review, or after a substantial implementation.
---

# Code review

Prefer the `code-reviewer` subagent for an independent pass. If you review in this thread, follow this file exactly.

## Scope

1. Default to the current change: `git status`, `git diff` (staged and unstaged), `git diff main...HEAD` or the repo's base branch when this is a PR, and **untracked files** (`git ls-files --others --exclude-standard`). In a new repository the diff is empty; still read the untracked implementation. Do not skip files just because they are untracked.
2. If the user names files, commits, or a PR, that is the scope. Do not expand into a repo-wide audit unless they ask.
3. Read `AGENTS.md` and matching `.cursor/rules` / `.claude/rules` before commenting on style.

## What to look for

- Correctness and edge cases; silent no-ops; wrong error handling.
- Security: injection, authz gaps, secret leakage, unsafe shell, path traversal.
- Tests: missing coverage for the change, tests that cannot fail, skipped assertions.
- API/schema/compat breaks and migration risk.
- Complexity that the surrounding code does not already use.

Skip formatting nits unless a project rule forbids the pattern. Do not rewrite the patch unless the user asked for fixes.

## Output

Lead with a verdict: **Approve**, **Request changes**, or **Comment**.

Then findings, most severe first:

- Critical — must fix before merge
- Should fix — real issue, not a blocker if the user accepts the risk
- Nit — optional

Each finding: file path, what's wrong, why it matters, and a concrete fix. No finding is a valid result; say so and still note residual risk.

End with: what you did not review (e.g. no runtime test, no load check).
