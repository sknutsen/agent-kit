---
name: architecture-analysis
description: >-
  Analyze a project's architecture, boundaries, data flow, and fit for a
  change. Use when the user asks how a repo is structured, where to put a
  feature, for a design review, refactor roadmap, or project/architecture
  analysis.
---

# Architecture analysis

Prefer the `architecture-analyst` subagent. Stay readonly unless the user asked for edits.

## Goal

Produce a map that is useful for the next decision. Prefer a sharp model of *this* repo over a generic textbook architecture.

## Method

1. Read `AGENTS.md`, README, and the top-level layout.
2. Find entrypoints (main, server, app bootstrap, IaC, mobile hosts).
3. Trace one request or job through transport → domain → storage → side effects.
4. Note actual layering vs stated layering. Name drift with file paths.
5. Identify the store, auth, and deployment as they really are, not as comments claim.
6. If the user has a change in mind, evaluate where it belongs and what it would couple.

Do not dump directory trees. Cite a few representative files.

## Output

1. **What this system is** — one paragraph.
2. **Runtime map** — mermaid flowchart of the real moving parts.
3. **Boundaries** — which packages/folders own transport, domain, data, UI.
4. **Invariants** — auth, tenancy, data stores, build/deploy.
5. **Risks / drift** — concrete, path-backed.
6. **If a change was named** — recommended seam, files to touch, files to avoid.
7. **Open questions** — only ones that block a better map.

Keep the whole write-up short enough to paste into a later chat as orientation.
