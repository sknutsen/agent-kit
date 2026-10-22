# Skill review checklist

## Blockers

- [ ] `name` matches the folder that contains `SKILL.md`
- [ ] `description` is third person, non-empty, includes WHAT and WHEN / trigger terms
- [ ] Body is instructions to the agent, not an essay about the domain the model already knows
- [ ] `SKILL.md` is under 500 lines
- [ ] Linked extra files are one level deep from `SKILL.md`
- [ ] Placement is correct (kit shared vs kit local-only vs project)
- [ ] If shared, the name is in `manifest.json`; if local-only, it is not in `shared_*`
- [ ] No secrets, no machine-specific paths (`/Users/zdk`, `C:\\Users\\...`)
- [ ] Works on macOS, Linux, and Windows unless explicitly host-specific
- [ ] No time-boxed API advice without an "old patterns" section

## Quality

- [ ] Auto-invoke is appropriate; `disable-model-invocation: true` only when implicit use would be noisy
- [ ] One workflow per skill; overlapping skills have a clear split
- [ ] Concrete output format or checklist where quality depends on structure
- [ ] Scripts are Python or otherwise portable; bash-only is documented as Unix-only
- [ ] Cursor-only or Claude-only steps are labeled by host
- [ ] Terminology is consistent
- [ ] Subagent descriptions say when to delegate

## Hooks (if this review includes hooks)

- [ ] Policy lives in `hooks/policy.json`; host files are adapters only
- [ ] Cursor events use Cursor JSON; Claude Code uses `hookSpecificOutput.permissionDecision`
- [ ] Fail-closed is set on deny-style Cursor safety hooks
- [ ] Malformed payloads deny (fail closed); adapters emit one protocol-valid document
- [ ] PEM / secret content checks are line-anchored so documentation is not blocked
- [ ] Paths are compared with separators normalized (`\\` → `/`)
