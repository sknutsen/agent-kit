#!/usr/bin/env python3
"""Copy the portable subset of agent-kit into a project repo."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
KIT_STATUS = "agent-kit safety"
CLAUDE_MATCHER = "Bash|PowerShell|Read|Write|Edit|Delete|Grep|Glob|NotebookEdit"
MANAGED_DENY = [
    "Read(**/id_rsa)",
    "Read(**/id_ed25519)",
    "Read(**/id_ecdsa)",
    "Read(**/id_dsa)",
    "Read(**/*.kdbx)",
    "Read(**/keepass/**)",
    "Read(**/*.age-key.txt)",
    "Read(**/age.key)",
]
KIT_HOOK_SCRIPTS = {
    "session-context.py",
    "shell-safety.py",
    "secret-read.py",
    "write-scope.py",
    "claude-pretool.py",
}


def copy_dir(src: Path, dst: Path) -> None:
    if dst.exists() or dst.is_symlink():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def write_if_missing(path: Path, template: Path, label: str) -> None:
    if path.exists():
        print(f"{label} exists — left unchanged")
        return
    path.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"created {label} from template")


def command_script_name(command: str) -> str:
    return Path(str(command).replace("\\", "/")).name


def is_kit_cursor_entry(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    return command_script_name(entry.get("command") or "") in KIT_HOOK_SCRIPTS


def merge_cursor_hooks(dest: Path, template: Path) -> None:
    template_data = json.loads(template.read_text(encoding="utf-8"))
    if dest.exists():
        try:
            existing = json.loads(dest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Refusing to merge malformed {dest}: {exc}") from exc
        if not isinstance(existing, dict):
            raise SystemExit(f"Refusing to merge unexpected hooks file: {dest}")
    else:
        existing = {"version": 1, "hooks": {}}
    hooks = existing.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise SystemExit(f"Refusing to merge unexpected hooks object: {dest}")
    for event, entries in (template_data.get("hooks") or {}).items():
        current = [e for e in (hooks.get(event) or []) if not is_kit_cursor_entry(e)]
        hooks[event] = current + list(entries)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")


def is_managed_claude_hook(hook: object) -> bool:
    return isinstance(hook, dict) and hook.get("statusMessage") == KIT_STATUS


def filter_claude_entries(entries: list) -> list:
    kept = []
    for entry in entries:
        if not isinstance(entry, dict):
            kept.append(entry)
            continue
        hooks = entry.get("hooks") or []
        if not isinstance(hooks, list):
            kept.append(entry)
            continue
        remaining = [h for h in hooks if not is_managed_claude_hook(h)]
        if remaining:
            new_entry = dict(entry)
            new_entry["hooks"] = remaining
            kept.append(new_entry)
    return kept


def project_claude_hook() -> dict:
    return {
        "type": "command",
        "command": "python3",
        "args": ["${CLAUDE_PROJECT_DIR}/.claude/hooks/claude-pretool.py"],
        "timeout": 8,
        "statusMessage": KIT_STATUS,
    }


def merge_project_claude_settings(settings_path: Path) -> None:
    data: dict = {}
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Refusing to merge malformed {settings_path}: {exc}") from exc
        if not isinstance(data, dict):
            raise SystemExit(f"Unexpected Claude settings file: {settings_path}")
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks
    hook_obj = project_claude_hook()
    for event, extra in (("PreToolUse", {"matcher": CLAUDE_MATCHER}), ("ConfigChange", {})):
        current = filter_claude_entries(list(hooks.get(event) or []))
        current.append({"hooks": [hook_obj], **extra})
        hooks[event] = current
    perms = data.setdefault("permissions", {})
    if not isinstance(perms, dict):
        perms = {}
        data["permissions"] = perms
    deny = [item for item in (perms.get("deny") or []) if item not in MANAGED_DENY]
    perms["deny"] = deny + list(MANAGED_DENY)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def load_stamp(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def prune_managed(root: Path, kind: str, previous: list, current: list, suffix: str = "") -> None:
    for name in set(previous) - set(current):
        path = root / f"{name}{suffix}"
        if not path.exists() and not path.is_symlink():
            continue
        if kind == "dir" and path.is_dir():
            shutil.rmtree(path)
            print(f"pruned {path}")
        elif kind == "file" and (path.is_file() or path.is_symlink()):
            path.unlink()
            print(f"pruned {path}")


def copy_hook_files(src_dir: Path, dst: Path, names: list[str]) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for name in names:
        src = src_dir / name
        if not src.exists():
            sys.exit(f"missing hook file: {src}")
        dest = dst / name
        shutil.copy2(src, dest)
        if os.name != "nt":
            dest.chmod(dest.stat().st_mode | 0o111)
        print(f"hook {name} -> {dst}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", type=Path)
    parser.add_argument(
        "--work",
        action="store_true",
        help="Employer/work repo: skills+agents+instruction files only. Never touch hooks or Claude settings.json.",
    )
    args = parser.parse_args()
    repo = args.repo.expanduser().resolve()
    if not repo.is_dir():
        sys.exit(f"not a directory: {repo}")

    manifest = json.loads((KIT / "manifest.json").read_text(encoding="utf-8"))
    version = (KIT / "VERSION").read_text(encoding="utf-8").strip()

    skill_roots = [repo / ".claude" / "skills", repo / ".cursor" / "skills"]
    agent_roots = [repo / ".claude" / "agents", repo / ".cursor" / "agents"]
    for root in skill_roots + agent_roots:
        root.mkdir(parents=True, exist_ok=True)

    prev_cursor = load_stamp(repo / ".cursor" / "agent-kit.json")
    prev_claude = load_stamp(repo / ".claude" / "agent-kit.json")
    prev = prev_cursor or prev_claude

    for name in manifest["shared_skills"]:
        src = KIT / "skills" / name
        if not (src / "SKILL.md").exists():
            sys.exit(f"missing skill: {src}")
        for root in skill_roots:
            copy_dir(src, root / name)
        print(f"skill {name}")

    for name in manifest["shared_agents"]:
        src = KIT / "agents" / f"{name}.md"
        if not src.exists():
            sys.exit(f"missing agent: {src}")
        for root in agent_roots:
            shutil.copy2(src, root / f"{name}.md")
        print(f"agent {name}")

    for root in skill_roots:
        prune_managed(root, "dir", prev.get("skills") or [], manifest["shared_skills"])
    for root in agent_roots:
        prune_managed(root, "file", prev.get("agents") or [], manifest["shared_agents"], ".md")

    if not args.work:
        names = list(manifest["hooks"])
        copy_hook_files(KIT / "hooks", repo / ".cursor" / "hooks", names)
        copy_hook_files(KIT / "hooks", repo / ".claude" / "hooks", names)
        for hook_root in (repo / ".cursor" / "hooks", repo / ".claude" / "hooks"):
            prune_managed(hook_root, "file", prev.get("hooks") or [], names)
        merge_cursor_hooks(repo / ".cursor" / "hooks.json", KIT / "templates" / "project-hooks.json")
        merge_project_claude_settings(repo / ".claude" / "settings.json")
        print("merged Cursor hooks.json and Claude settings.json")
    else:
        print("work mode: skipped Cursor/Claude hook config")

    stamp = {
        "kit": "agent-kit",
        "version": version,
        "mode": "work" if args.work else "personal",
        "skills": manifest["shared_skills"],
        "agents": manifest["shared_agents"],
        "hooks": [] if args.work else list(manifest["hooks"]),
        "note": (
            "Shared kit files are overwritten by sync_project.py. "
            "Put project-only skills in .claude/skills/ under a different name "
            "(Cursor also reads that path). Do not fork shared names."
        ),
    }
    for stamp_dir in (repo / ".cursor", repo / ".claude"):
        stamp_dir.mkdir(parents=True, exist_ok=True)
        (stamp_dir / "agent-kit.json").write_text(
            json.dumps(stamp, indent=2) + "\n", encoding="utf-8"
        )
    print("agent-kit.json")

    write_if_missing(repo / "AGENTS.md", KIT / "templates" / "AGENTS.md", "AGENTS.md")
    write_if_missing(repo / "CLAUDE.md", KIT / "templates" / "CLAUDE.md", "CLAUDE.md")

    print()
    print(f"synced agent-kit into {repo} ({'work' if args.work else 'personal'} mode)")
    print("Commit .claude/, .cursor/, AGENTS.md, and CLAUDE.md so every host sees them.")


if __name__ == "__main__":
    main()
