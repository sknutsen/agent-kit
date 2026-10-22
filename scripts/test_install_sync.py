#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, os, shutil, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def check(cond, msg):
    if not cond:
        raise SystemExit(msg)

def test_points_at_kit():
    inst = load("install", ROOT/"scripts"/"install.py")
    tmp = Path(tempfile.mkdtemp(prefix="agent-kit-own-"))
    try:
        kit = tmp/"kit"; kit.mkdir(); inst.KIT = kit
        sibling = tmp/"kit-backup"; sibling.mkdir(); owned = sibling/"x.txt"; owned.write_text("x\n", encoding="utf-8")
        check(not inst.points_at_kit(owned), "prefix sibling must not be kit-owned")
        child = kit/"hooks"; child.mkdir(); check(inst.points_at_kit(child), "descendant must be kit-owned")
        print("ok ownership")
    finally:
        shutil.rmtree(tmp)

def test_claude_unmerge_preserves_other():
    inst = load("install", ROOT/"scripts"/"install.py")
    tmp = Path(tempfile.mkdtemp(prefix="agent-kit-set-"))
    try:
        inst.HOME = tmp; inst.STATE_PATH = tmp/".cursor"/"agent-kit-state.json"
        settings = tmp/".claude"/"settings.json"; settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Read", "hooks": [{"type": "command", "command": "python3", "args": ["/other/claude-pretool.py"]}]}]}})+"\n", encoding="utf-8")
        inst.merge_claude_settings(settings, ROOT/"hooks"/"claude-pretool.py")
        inst.unmerge_claude_settings(settings)
        data = json.loads(settings.read_text(encoding="utf-8"))
        blob = json.dumps(data)
        check("/other/claude-pretool.py" in blob, "unrelated hook lost")
        check(inst.KIT_STATUS not in blob, "kit hook not removed")
        print("ok claude unmerge")
    finally:
        shutil.rmtree(tmp)

def test_install_status_symlink():
    inst = load("install", ROOT/"scripts"/"install.py")
    tmp = Path(tempfile.mkdtemp(prefix="agent-kit-home-"))
    try:
        inst.HOME = tmp; inst.STATE_PATH = tmp/".cursor"/"agent-kit-state.json"
        inst.install(cursor=True, claude=True, agents_compat=False)
        code = inst.status()
        check(code == 0, f"status expected 0, got {code}")
        wrong = tmp/".cursor"/"skills"
        if wrong.is_symlink() or wrong.exists():
            if wrong.is_symlink():
                wrong.unlink()
            elif wrong.is_dir():
                shutil.rmtree(wrong)
            wrong.symlink_to(tmp/"nope")
        line, ok = inst.describe(wrong)
        check(not ok and line.startswith("??"), f"wrong symlink should be unhealthy: {line}")
        inst.uninstall()
        print("ok install status")
    finally:
        shutil.rmtree(tmp)

def test_managed_copy():
    inst = load("install", ROOT/"scripts"/"install.py")
    tmp = Path(tempfile.mkdtemp(prefix="agent-kit-copy-"))
    try:
        inst.HOME = tmp; inst.STATE_PATH = tmp/".cursor"/"agent-kit-state.json"
        dest = tmp/".cursor"/"hooks.json"; dest.parent.mkdir(parents=True)
        dest.write_text("{ }\n", encoding="utf-8")
        inst.mark_managed_copy(dest)
        check(inst.is_kit_owned(dest), "managed copy should be owned")
        inst.remove_dest(dest)
        check(not dest.exists(), "managed copy not removed")
        print("ok managed copy")
    finally:
        shutil.rmtree(tmp)

def test_sync_merge_and_prune():
    sync = load("sync", ROOT/"scripts"/"sync_project.py")
    repo = Path(tempfile.mkdtemp(prefix="agent-kit-repo-"))
    try:
        hooks = repo/".cursor"; hooks.mkdir()
        (hooks/"hooks.json").write_text(json.dumps({"version": 1, "hooks": {"beforeShellExecution": [{"command": "project-audit.py", "timeout": 3}]}})+"\n", encoding="utf-8")
        sys.argv = ["sync_project.py", str(repo)]
        sync.main()
        data = json.loads((repo/".cursor"/"hooks.json").read_text(encoding="utf-8"))
        cmds = [e.get("command") for e in data["hooks"].get("beforeShellExecution", [])]
        check(any("project-audit.py" in str(c) for c in cmds), "project hook lost")
        check((repo/".claude"/"settings.json").exists(), "missing Claude project settings")
        settings = json.loads((repo/".claude"/"settings.json").read_text(encoding="utf-8"))
        check("agent-kit safety" in json.dumps(settings), "missing Claude kit hook")
        stamp = json.loads((repo/".claude"/"agent-kit.json").read_text(encoding="utf-8"))
        check("source" not in stamp and "synced_at" not in stamp, "stamp leaked machine data")
        check((repo/".claude"/"hooks"/"claude-pretool.py").exists(), "missing Claude hook copy")
        extra = repo/".claude"/"skills"/"code-review"
        check(extra.exists(), "shared skill missing")
        manifest = json.loads((ROOT/"manifest.json").read_text(encoding="utf-8"))
        old = list(manifest["shared_skills"])
        # prune simulation: rewrite stamp then prune via second sync after monkeypatching manifest is heavy; call prune_managed directly
        sync.prune_managed(repo/".claude"/"skills", "dir", old, [s for s in old if s != "code-review"])
        check(not extra.exists(), "retired skill not pruned")
        leftover = repo/".claude"/"skills"/"project-only"; leftover.mkdir(); (leftover/"SKILL.md").write_text("# x\n", encoding="utf-8")
        sync.prune_managed(repo/".claude"/"skills", "dir", ["code-review"], ["code-review"])
        check(leftover.exists(), "untracked project skill deleted")
        print("ok sync")
    finally:
        shutil.rmtree(repo)

def main():
    test_points_at_kit(); test_claude_unmerge_preserves_other(); test_managed_copy(); test_install_status_symlink(); test_sync_merge_and_prune()
    print("all install/sync tests passed")

if __name__ == "__main__":
    main()
