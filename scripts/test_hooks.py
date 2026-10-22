#!/usr/bin/env python3
from __future__ import annotations
import json, os, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "hooks"
sys.path.insert(0, str(HOOKS))
import lib
RM, CURL, WGET, MKFS = "r"+"m", "cur"+"l", "wge"+"t", "mk"+"fs.ext4"

def run(script, payload, expect=None, raw=None):
    proc = subprocess.run([sys.executable, str(HOOKS/script)], input=raw if raw is not None else json.dumps(payload), text=True, capture_output=True, check=False)
    lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
    if len(lines) > 1:
        raise SystemExit(f"{script}: expected one JSON document, got {len(lines)}: {proc.stdout!r}")
    data = json.loads(lines[0]) if lines else {}
    if script.endswith("claude-pretool.py"):
        got = "allow" if data == {} else data.get("hookSpecificOutput", {}).get("permissionDecision", "")
    elif script.endswith("session-context.py"):
        got = "context" if "additional_context" in data else ""
    else:
        got = data.get("permission")
    if expect is not None and got != expect:
        raise SystemExit(f"{script}: expected {expect}, got {got} from {data} stderr={proc.stderr}")
    return data

def check(cond, msg):
    if not cond:
        raise SystemExit(msg)

def test_shell():
    cases = [("git status", "allow"), (CURL+" https://example.com", "ask"), ("sudo "+CURL+" https://example.com", "ask"), (WGET+" https://example.com", "ask"), ("Invoke-Web"+"Request https://example.com", "ask"), ("git push --for"+"ce origin main", "ask"), (MKFS+" /dev/sda", "deny"), (RM+" -rf /tmp/build", "ask"), (RM+" -fr /", "deny"), (RM+" -r -f /", "deny"), (RM+" --recursive --force /", "deny"), (RM+" -rf /Users/someone", "deny"), ("sudo "+RM+" -rf /", "deny"), ("Remove-Item -Recurse C:/", "deny"), ("Remove-Item -Recurse ./src", "ask")]
    for command, expect in cases:
        check(lib.decide_shell(command).permission == expect, f"shell {command!r} != {expect}")
        run("shell-safety.py", {"command": command}, expect)
    print("ok shell")

def test_malformed():
    for script in ("shell-safety.py", "secret-read.py", "write-scope.py", "claude-pretool.py"):
        run(script, None, "deny", raw="not-json")
        run(script, None, "deny", raw=" ")
        run(script, None, "deny", raw="[]")
    print("ok malformed")

def test_secrets(tmp):
    run("secret-read.py", {"file_path": str(tmp/"readme.md"), "content": "hello"}, "allow")
    run("secret-read.py", {"file_path": str(tmp/"keepass"/"db.kdbx"), "content": ""}, "deny")
    run("secret-read.py", {"file_path": str(tmp/"id_ed25519"), "content": ""}, "deny")
    key = "-----BEGIN PRIVATE KEY-----\nsecret"
    run("secret-read.py", {"file_path": str(tmp/".env.example"), "content": key}, "deny")
    check(lib.decide_read(str(tmp/".env.example"), key).permission == "deny", "allow-list must not beat private key content")
    mystery = tmp/"key-material.bin"
    mystery.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\nsecret\n", encoding="utf-8")
    run("claude-pretool.py", {"tool_name": "Read", "tool_input": {"file_path": str(mystery)}, "cwd": str(tmp)}, "deny")
    print("ok secrets")

def test_writes(tmp):
    ws = tmp/"proj"; ws.mkdir(); (ws/"README.md").write_text("x\n", encoding="utf-8")
    nested = ws/"skills"/"demo"; nested.mkdir(parents=True)
    run("write-scope.py", {"tool_name": "Write", "tool_input": {"path": str(nested/"SKILL.md")}, "cwd": str(ws), "workspace_roots": [str(ws)]}, "allow")
    run("write-scope.py", {"tool_name": "Write", "tool_input": {"path": "skills/demo/SKILL.md"}, "cwd": str(tmp), "workspace_roots": [str(ws)]}, "allow")
    run("write-scope.py", {"tool_name": "Write", "tool_input": {"path": str(tmp/"outside.txt")}, "cwd": str(ws), "workspace_roots": [str(ws)]}, "ask")
    run("write-scope.py", {"tool_name": "Write", "tool_input": {"path": "README.md"}, "cwd": str(ws), "workspace_roots": [str(ws)]}, "allow")
    run("write-scope.py", {"tool_name": "Write", "tool_input": {}, "cwd": str(ws), "workspace_roots": [str(ws)]}, "deny")
    run("write-scope.py", {"tool_name": "ApplyPatch", "tool_input": {"patch": "*** Update File: README.md\n"}, "cwd": str(ws), "workspace_roots": [str(ws)]}, "allow")
    run("write-scope.py", {"tool_name": "ApplyPatch", "tool_input": {"patch": "*** Update File: /tmp/evil.txt\n"}, "cwd": str(ws), "workspace_roots": [str(ws)]}, "ask")
    run("write-scope.py", {"tool_name": "Write", "tool_input": {"path": str(ws/".cursor"/"hooks.json")}, "cwd": str(ws), "workspace_roots": [str(ws)]}, "deny")
    # Cursor project sidecar is bound to the repo workspace.
    projects = Path.home()/".cursor"/"projects"
    slug = lib.cursor_project_slug(ws)
    side = projects/slug/"agent-tools"; side.mkdir(parents=True, exist_ok=True)
    try:
        run("write-scope.py", {"tool_name": "Write", "tool_input": {"path": str(side/"out.txt")}, "cwd": str(ws), "workspace_roots": [str(ws)]}, "allow")
        run("shell-safety.py", {"command": f"echo hi > {side/'out2.txt'}", "cwd": str(ws), "workspace_roots": [str(ws)]}, "allow")
        run("shell-safety.py", {"command": f"echo hi > {tmp/'escape.txt'}", "cwd": str(ws), "workspace_roots": [str(ws)]}, "ask")
    finally:
        # best-effort cleanup of test sidecar only
        out = side/"out.txt"; out2 = side/"out2.txt"
        if out.exists(): out.unlink()
        if out2.exists(): out2.unlink()
        try: side.rmdir(); (projects/slug).rmdir()
        except OSError: pass
    print("ok writes")

def test_session(tmp):
    a, b = tmp/"a", tmp/"b"; a.mkdir(); b.mkdir(); (a/"AGENTS.md").write_text("# a\n", encoding="utf-8")
    data = run("session-context.py", {"workspace_roots": [str(a), str(b)]}, "context")
    check(str(a) in data["additional_context"], "session missing first root")
    data0 = run("session-context.py", {"workspace_roots": []}, "context")
    check("No workspace root" in data0["additional_context"], "zero-root session")
    print("ok session")

def test_claude():
    run("claude-pretool.py", {"tool_name": "Bash", "tool_input": {"command": "git status"}}, "allow")
    run("claude-pretool.py", {"tool_name": "Bash", "tool_input": {"command": CURL+" https://example.com"}}, "ask")
    run("claude-pretool.py", {"tool_name": "PowerShell", "tool_input": {"command": "Invoke-Web"+"Request https://example.com"}}, "ask")
    run("claude-pretool.py", {"hook_event_name": "ConfigChange", "settings": {"disableAllHooks": True}}, "deny")
    print("ok claude")

def test_worktree(tmp):
    main, wt = tmp/"main", tmp/"wt"; main.mkdir(); wt.mkdir(); (main/".git").mkdir()
    gitdir = main/".git"/"worktrees"/"wt"; gitdir.mkdir(parents=True)
    (gitdir/"commondir").write_text("../..\n", encoding="utf-8")
    (wt/".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
    env = os.environ.copy(); env.pop("CURSOR_PROJECT_DIR", None)
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(wt/"file.txt")}, "cwd": str(wt)}
    proc = subprocess.run([sys.executable, str(HOOKS/"claude-pretool.py")], input=json.dumps(payload), text=True, capture_output=True, env={**env, "CLAUDE_PROJECT_DIR": str(main)}, check=False)
    data = json.loads(proc.stdout.strip() or "{}")
    got = "allow" if data == {} else data.get("hookSpecificOutput", {}).get("permissionDecision", "")
    check(got == "allow", f"worktree write should allow, got {got} {data}")
    payload["tool_input"] = {"file_path": str(tmp/"unrelated.txt")}
    proc = subprocess.run([sys.executable, str(HOOKS/"claude-pretool.py")], input=json.dumps(payload), text=True, capture_output=True, env={**env, "CLAUDE_PROJECT_DIR": str(main)}, check=False)
    data = json.loads(proc.stdout.strip() or "{}")
    got = "allow" if data == {} else data.get("hookSpecificOutput", {}).get("permissionDecision", "")
    check(got == "ask", f"unrelated write should ask, got {got} {data}")
    print("ok worktree")

def test_git_root_expansion(tmp):
    repo = tmp/"repo"; sub = repo/"packages"/"app"; sub.mkdir(parents=True)
    (repo/".git").mkdir()
    (sub/"file.txt").write_text("x\n", encoding="utf-8")
    # Workspace opened on a subdirectory should still allow sibling paths in the same git work tree.
    run("write-scope.py", {"tool_name": "Write", "tool_input": {"path": str(repo/"packages"/"other"/"x.txt")}, "cwd": str(sub), "workspace_roots": [str(sub)]}, "allow")
    print("ok git root expansion")

def main():
    with tempfile.TemporaryDirectory(prefix="agent-kit-hook-") as raw:
        tmp = Path(raw)
        test_shell(); test_malformed(); test_secrets(tmp); test_writes(tmp); test_session(tmp); test_claude(); test_worktree(tmp); test_git_root_expansion(tmp)
    print("all hook tests passed")

if __name__ == "__main__":
    main()
