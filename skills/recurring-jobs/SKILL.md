---
name: recurring-jobs
description: >-
  Run recurring, scheduled, or long-running agent work using the current host.
  Use when the user says every N minutes, cron, watch until, babysit a PR,
  keep working until done, or asks for a recurring job.
---

# Recurring jobs

Pick the **current host's** mechanism. Do not invent a parallel scheduler, and do not call Cursor-only tools from Claude Code or Pi.

## Cursor

| Need | Mechanism |
| --- | --- |
| Keep going until a defined end state is true | `/goal` (CreateGoal / UpdateGoal). No time budget. |
| Repeat a prompt on an interval or until told to stop | `/loop` |
| Fire on GitHub/Slack/schedule outside this chat | `/automate` |
| Watch a PR for comments, CI, conflicts | built-in `/babysit` |

`/goal`: restate the objective, call `CreateGoal` once, start real work in the same turn. Do not mark complete until current evidence proves every requirement.

`/loop`: follow the built-in loop skill for local vs cloud. Unique sentinel per loop.

## Claude Code

Use Claude Code's own looping, scheduled, or GitHub-integrated tools if they are available in this session. If none are, do one pass, report, and ask how the user wants it repeated. Do not emulate Cursor `/goal` tools that are not present.

## Pi

Interactive Pi has no Cursor `/loop` or `/goal`. Do one pass in the session, or use the host's own follow-up / steering. For scripts and later automation, `pi --print` (one-shot) or `pi --mode rpc` (long-lived). Do not install a web UI or Kubernetes runner to fake a scheduler.

Pi does not evaluate `policy.json` yet. Recurring Pi work is still ungated by this kit's hooks.

## Safety

Recurring work still goes through `policy.json` on Cursor and Claude Code. Do not weaken fail-closed hooks to make a loop quieter.
