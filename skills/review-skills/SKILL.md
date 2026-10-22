---
name: review-skills
description: >-
  Review agent skills, subagents, and hooks for trigger quality, duplication,
  and kit placement. Use when asked to review a skill, after creating or
  editing SKILL.md, or when skills feel noisy or ignored.
---

# Review skills

Prefer the `skill-reviewer` subagent. Work from the files on disk, not memory of an earlier draft.

## Scope

Review the named skill, or every skill under the kit `skills/` plus any project `.cursor/skills/` in the current workspace.

## Checklist

Use [checklist.md](checklist.md). Fail the review if any **blocker** item fails.

## Output

Verdict: **Ready**, **Needs changes**, or **Misplaced**.

Then:

- Blockers
- Improvements
- Placement (shared / local-only / project) and whether `manifest.json` matches
- Description rewrite if the current one is vague or first-person

If you changed a **shared** skill, remind to run `scripts/sync_project.py` on repos that already import the kit.
