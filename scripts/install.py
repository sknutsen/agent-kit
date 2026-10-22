#!/usr/bin/env python3
"""Install agent-kit into this user account for Cursor and/or Claude Code."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
HOME = Path.home()
STATE_PATH = HOME / ".cursor" / "agent-kit-state.json"
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


def python_invocation(script: Path) -> tuple[str, list[str]]:
    if os.name == "nt":
        return "py", ["-3", str(script)]
    return "python3", [str(script)]


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"managed_copies": {}}
        if isinstance(data, dict):
            data.setdefault("managed_copies", {})
            return data
    return {"managed_copies": {}}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def mark_managed_copy(dest: Path) -> None:
    state = load_state()
    state["managed_copies"][str(dest.resolve())] = {"kind": "copy"}
    save_state(state)


def unmark_managed_copy(dest: Path) -> None:
    state = load_state()
    state["managed_copies"].pop(str(dest.resolve()), None)
    save_state(state)


def is_managed_copy(dest: Path) -> bool:
    try:
        key = str(dest.resolve())
    except OSError:
        key = str(dest)
    return key in load_state().get("managed_copies", {})


def points_at_kit(dest: Path) -> bool:
    if not dest.exists() and not dest.is_symlink():
        return False
    try:
        resolved = dest.resolve()
        kit = KIT.resolve()
    except OSError:
        return False
    return resolved == kit or kit in resolved.parents


def is_kit_owned(dest: Path) -> bool:
    if dest.is_symlink() or dest.exists():
        if points_at_kit(dest):
            return True
    return dest.exists() and not dest.is_symlink() and dest.is_file() and is_managed_copy(dest)


def remove_dest(dest: Path) -> None:
    if dest.is_symlink():
        dest.unlink()
        return
    if dest.is_file():
        dest.unlink()
        unmark_managed_copy(dest)
        return
    if dest.is_dir():
        if os.name == "nt":
            dest.rmdir()
            return
        if not any(dest.iterdir()):
            dest.rmdir()
            return
        raise SystemExit(f"Refusing to replace non-empty directory: {dest}")
    if dest.exists():
        raise SystemExit(f"Refusing to replace: {dest}")


def link_path(src: Path, dest: Path) -> None:
    src = src.resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink() or dest.exists():
        if is_kit_owned(dest) or (dest.is_dir() and not dest.is_symlink() and not any(dest.iterdir())):
            remove_dest(dest)
        else:
            raise SystemExit(
                f"Refusing to replace existing path that is not an agent-kit link: {dest}"
            )
    if os.name == "nt":
        if src.is_dir():
            subprocess.check_call(["cmd", "/c", "mklink", "/J", str(dest), str(src)])
        else:
            try:
                dest.symlink_to(src)
            except OSError:
                shutil.copy2(src, dest)
                mark_managed_copy(dest)
                print(f"copied {dest} (Windows file symlink unavailable)")
                return
    else:
        dest.symlink_to(src, target_is_directory=src.is_dir())
    print(f"linked {dest} -> {src}")


def is_managed_claude_hook(hook: dict, script: Path) -> bool:
    if not isinstance(hook, dict):
        return False
    if hook.get("statusMessage") == KIT_STATUS:
        return True
    script_r = script.resolve()
    for item in hook.get("args") or []:
        if not isinstance(item, str):
            continue
        try:
            if Path(item).expanduser().resolve() == script_r:
                return True
        except OSError:
            continue
    return False


def filter_claude_entries(entries: list, script: Path) -> list:
    kept = []
    for entry in entries:
        if not isinstance(entry, dict):
            kept.append(entry)
            continue
        hooks = entry.get("hooks") or []
        if not isinstance(hooks, list):
            kept.append(entry)
            continue
        remaining = [h for h in hooks if not is_managed_claude_hook(h, script)]
        if remaining:
            new_entry = dict(entry)
            new_entry["hooks"] = remaining
            kept.append(new_entry)
        elif not any(is_managed_claude_hook(h, script) for h in hooks):
            kept.append(entry)
    return kept


def kit_command_hook(script: Path) -> dict:
    cmd, args = python_invocation(script)
    return {
        "type": "command",
        "command": cmd,
        "args": args,
        "timeout": 8,
        "statusMessage": KIT_STATUS,
    }


def merge_permissions(data: dict) -> None:
    perms = data.setdefault("permissions", {})
    if not isinstance(perms, dict):
        perms = {}
        data["permissions"] = perms
    deny = [item for item in (perms.get("deny") or []) if item not in MANAGED_DENY]
    perms["deny"] = deny + list(MANAGED_DENY)


def unmerge_permissions(data: dict) -> None:
    perms = data.get("permissions")
    if not isinstance(perms, dict):
        return
    deny = [item for item in (perms.get("deny") or []) if item not in MANAGED_DENY]
    if deny:
        perms["deny"] = deny
    else:
        perms.pop("deny", None)
    if not perms:
        data.pop("permissions", None)


def merge_claude_settings(settings_path: Path, script: Path) -> None:
    data: dict = {}
    if settings_path.exists():
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise SystemExit(f"Unexpected Claude settings file: {settings_path}")
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks
    hook_obj = kit_command_hook(script)
    for event, extra in (
        ("PreToolUse", {"matcher": CLAUDE_MATCHER}),
        ("ConfigChange", {}),
    ):
        current = list(hooks.get(event) or [])
        current = filter_claude_entries(current, script)
        entry = {"hooks": [hook_obj], **extra}
        current.append(entry)
        hooks[event] = current
    merge_permissions(data)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"merged Claude hooks into {settings_path}")


def unmerge_claude_settings(settings_path: Path) -> None:
    if not settings_path.exists():
        return
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return
    script = KIT / "hooks" / "claude-pretool.py"
    hooks = data.get("hooks") or {}
    if isinstance(hooks, dict):
        for event in list(hooks):
            entries = hooks.get(event) or []
            if isinstance(entries, list):
                new_entries = filter_claude_entries(entries, script)
                if new_entries:
                    hooks[event] = new_entries
                else:
                    hooks.pop(event, None)
        if hooks:
            data["hooks"] = hooks
        else:
            data.pop("hooks", None)
    unmerge_permissions(data)
    settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"removed agent-kit hooks from {settings_path}")


def install(cursor: bool, claude: bool, agents_compat: bool) -> None:
    if cursor:
        cursor_home = HOME / ".cursor"
        cursor_home.mkdir(parents=True, exist_ok=True)
        link_path(KIT / "skills", cursor_home / "skills")
        link_path(KIT / "agents", cursor_home / "agents")
        link_path(KIT / "hooks", cursor_home / "hooks")
        link_path(KIT / "user-hooks.json", cursor_home / "hooks.json")
    if agents_compat:
        agents_home = HOME / ".agents"
        agents_home.mkdir(parents=True, exist_ok=True)
        link_path(KIT / "skills", agents_home / "skills")
        link_path(KIT / "agents", agents_home / "agents")
    if claude:
        claude_home = HOME / ".claude"
        claude_home.mkdir(parents=True, exist_ok=True)
        link_path(KIT / "skills", claude_home / "skills")
        link_path(KIT / "agents", claude_home / "agents")
        merge_claude_settings(claude_home / "settings.json", KIT / "hooks" / "claude-pretool.py")
    print()
    print(f"agent-kit {KIT} installed.")
    print("Install in the environment where the agent process runs:")
    print("  native Windows Cursor/Claude  -> this Windows home")
    print("  WSL Claude Code               -> run this script again inside WSL")
    print("  Linux/macOS                   -> this Unix home")
    print("Restart Cursor / Claude Code. Cloud agents still need sync_project.py.")
    print("Pi user config is a separate repo; this install only shares skills via ~/.agents.")


def uninstall() -> None:
    for dest in (
        HOME / ".cursor" / "skills",
        HOME / ".cursor" / "agents",
        HOME / ".cursor" / "hooks",
        HOME / ".cursor" / "hooks.json",
        HOME / ".agents" / "skills",
        HOME / ".agents" / "agents",
        HOME / ".claude" / "skills",
        HOME / ".claude" / "agents",
    ):
        if dest.is_symlink() or dest.exists():
            if is_kit_owned(dest):
                remove_dest(dest)
                print(f"removed {dest}")
            else:
                print(f"skip {dest} (not an agent-kit link)")
    unmerge_claude_settings(HOME / ".claude" / "settings.json")
    print("uninstall complete")


def describe(dest: Path) -> tuple[str, bool]:
    settings_ok = dest.name == "settings.json" and dest.exists() and KIT_STATUS in dest.read_text(
        encoding="utf-8", errors="ignore"
    )
    if dest.is_symlink():
        try:
            target = dest.readlink()
        except OSError:
            return f"??  {dest} broken symlink", False
        if points_at_kit(dest):
            return f"OK  {dest} -> {target}", True
        return f"??  {dest} -> {target} (not agent-kit)", False
    if dest.exists() and dest.is_file() and is_managed_copy(dest):
        return f"OK  {dest} (managed copy)", True
    if dest.exists() and points_at_kit(dest):
        return f"OK  {dest} -> {dest.resolve()}", True
    if settings_ok:
        return f"OK  {dest} (agent-kit adapter merged)", True
    if dest.exists():
        return f"??  {dest} exists", False
    return f"NO  {dest} missing", False


def status() -> int:
    print(f"kit: {KIT}")
    print(f"home: {HOME}")
    dests = [
        HOME / ".cursor" / "skills",
        HOME / ".cursor" / "agents",
        HOME / ".cursor" / "hooks",
        HOME / ".cursor" / "hooks.json",
        HOME / ".agents" / "skills",
        HOME / ".agents" / "agents",
        HOME / ".claude" / "skills",
        HOME / ".claude" / "agents",
        HOME / ".claude" / "settings.json",
    ]
    optional = {HOME / ".agents" / "skills", HOME / ".agents" / "agents"}
    healthy = True
    for dest in dests:
        line, ok = describe(dest)
        print(line)
        if dest in optional:
            continue
        if not ok:
            healthy = False
    return 0 if healthy else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--no-cursor", action="store_true")
    parser.add_argument("--no-claude", action="store_true")
    parser.add_argument("--no-agents-compat", action="store_true")
    args = parser.parse_args()
    if args.status:
        raise SystemExit(status())
    if args.uninstall:
        uninstall()
        return
    install(
        cursor=not args.no_cursor,
        claude=not args.no_claude,
        agents_compat=not args.no_agents_compat,
    )


if __name__ == "__main__":
    main()
