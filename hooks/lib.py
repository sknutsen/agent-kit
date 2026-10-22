#!/usr/bin/env python3
"""Shared policy evaluation for Cursor and Claude Code hooks."""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HOOKS_DIR = Path(__file__).resolve().parent
POLICY_PATH = HOOKS_DIR / "policy.json"
READ_CONTENT_LIMIT = 256 * 1024
MALFORMED = "Blocked: hook received malformed or empty JSON."

PATH_KEYS = ("path", "file_path", "target_notebook", "target_directory")
PATCH_PATH_RE = re.compile(
    r"^\*\*\* (?:Add|Update|Delete|Rename) File: (.+)$",
    re.MULTILINE,
)
GIT_DIR_RE = re.compile(r"^gitdir:\s*(.+)\s*$", re.IGNORECASE | re.MULTILINE)
SHELL_REDIRECT_RE = re.compile(
    r"(?:(?:^|[\s\d])>>?\s*|tee(?:\s+-[aA])?\s+)(?P<path>[^\s'\"|&;<>]+|'[^']+'|\"[^\"]+\")",
    re.IGNORECASE,
)
SHELL_COPY_DEST = {"cp", "mv", "install", "copy-item", "move-item", "cpi", "mi"}


@dataclass
class Decision:
    permission: str  # allow | ask | deny
    user_message: str = ""
    agent_message: str = ""


class PayloadError(ValueError):
    pass


def read_stdin() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        raise PayloadError("empty stdin")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PayloadError(str(exc)) from exc
    if not isinstance(data, dict):
        raise PayloadError("JSON root is not an object")
    return data


def load_policy() -> dict[str, Any]:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")


def emit_cursor(decision: Decision) -> None:
    body: dict[str, Any] = {"permission": decision.permission}
    if decision.user_message:
        body["user_message"] = decision.user_message
    if decision.agent_message:
        body["agent_message"] = decision.agent_message
    emit(body)


def emit_claude(decision: Decision, event: str = "PreToolUse") -> None:
    if decision.permission == "allow":
        emit({})
        return
    reason = decision.user_message or decision.agent_message or "blocked by agent-kit"
    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": event,
                "permissionDecision": decision.permission,
                "permissionDecisionReason": reason,
            }
        }
    )


def malformed_decision() -> Decision:
    return Decision("deny", MALFORMED, MALFORMED)


def first_match(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            return pattern
    return None


def posix_path(raw: str) -> str:
    return raw.replace("\\", "/")


def _resolve(path: Path) -> Path:
    try:
        return path.expanduser().resolve()
    except OSError:
        return path.expanduser()


def git_common_dir(start: Path) -> Path | None:
    current = _resolve(start)
    if current.is_file():
        current = current.parent
    for folder in [current, *current.parents]:
        git = folder / ".git"
        try:
            if git.is_file():
                text = git.read_text(encoding="utf-8", errors="ignore")
                match = GIT_DIR_RE.search(text)
                if not match:
                    return None
                raw = match.group(1).strip()
                gitdir = Path(raw)
                if not gitdir.is_absolute():
                    gitdir = folder / gitdir
                gitdir = _resolve(gitdir)
                common = gitdir / "commondir"
                if common.is_file():
                    rel = common.read_text(encoding="utf-8", errors="ignore").strip()
                    return _resolve(gitdir / rel)
                return gitdir
            if git.is_dir():
                common = git / "commondir"
                if common.is_file():
                    rel = common.read_text(encoding="utf-8", errors="ignore").strip()
                    return _resolve(git / rel)
                return git
        except OSError:
            continue
    return None


def git_work_tree(start: Path) -> Path | None:
    current = _resolve(start)
    if current.is_file():
        current = current.parent
    for folder in [current, *current.parents]:
        git = folder / ".git"
        try:
            if git.is_dir() or git.is_file():
                return folder
        except OSError:
            continue
    return None


def cursor_project_slug(root: Path) -> str:
    normalized = posix_path(str(_resolve(root))).rstrip("/")
    if os.name == "nt":
        normalized = normalized.replace(":", "")
    return normalized.lstrip("/").replace("/", "-")


def cursor_project_dirs(roots: list[Path], payload: dict[str, Any] | None = None) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        path = _resolve(path)
        key = posix_path(str(path)).rstrip("/").lower()
        if key in seen:
            return
        seen.add(key)
        found.append(path)

    payload = payload or {}
    for key in ("transcript_path", "transcriptPath"):
        raw = payload.get(key)
        if not isinstance(raw, str) or not raw.strip():
            continue
        parts = Path(raw).expanduser().parts
        for i, part in enumerate(parts):
            if part == ".cursor" and i + 2 < len(parts) and parts[i + 1] == "projects":
                add(Path(*parts[: i + 3]))
                break

    projects = Path.home() / ".cursor" / "projects"
    if projects.is_dir():
        for root in roots:
            candidate = projects / cursor_project_slug(root)
            if candidate.is_dir():
                add(candidate)

    return found


def workspace_roots(payload: dict[str, Any], policy: dict[str, Any] | None = None) -> list[Path]:
    roots: list[Path] = []
    seen: set[str] = set()

    def add(raw: Any) -> None:
        if isinstance(raw, Path):
            path = _resolve(raw)
        elif isinstance(raw, str) and raw.strip():
            path = _resolve(Path(raw))
        else:
            return
        key = posix_path(str(path)).rstrip("/").lower()
        if key in seen:
            return
        seen.add(key)
        roots.append(path)

    for root in payload.get("workspace_roots") or []:
        add(root)

    env_root = os.environ.get("CURSOR_PROJECT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root:
        add(env_root)

    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        cwd_path = _resolve(Path(cwd))
        if not roots:
            add(cwd)
        else:
            cwd_git = git_common_dir(cwd_path)
            if cwd_git is not None and any(git_common_dir(root) == cwd_git for root in roots):
                add(cwd)

    write = (policy or load_policy()).get("write") or {}
    if write.get("expand_git_root", True):
        for root in list(roots):
            tree = git_work_tree(root)
            if tree is not None:
                add(tree)

    if write.get("include_cursor_project_dir", True):
        for path in cursor_project_dirs(list(roots), payload):
            add(path)

    return roots


def resolve_path(raw: str, cwd: str | None) -> Path | None:
    if not raw or not isinstance(raw, str):
        return None
    cleaned = raw.strip().strip("'\"")
    if not cleaned:
        return None
    path = Path(cleaned).expanduser()
    if not path.is_absolute():
        base = Path(cwd).expanduser() if cwd else Path.cwd()
        path = base / path
    return _resolve(path)


def resolve_write_path(raw: str, cwd: str | None, roots: list[Path]) -> Path | None:
    """Resolve a write target, preferring a path that lands under a workspace root."""
    primary = resolve_path(raw, cwd)
    if primary is None:
        return None
    if any(is_under(primary, root) for root in roots):
        return primary
    cleaned = raw.strip().strip("'\"")
    path = Path(cleaned).expanduser()
    if path.is_absolute():
        return primary
    for root in roots:
        candidate = _resolve(root / path)
        if any(is_under(candidate, bound) for bound in roots):
            return candidate
    return primary


def is_under(path: Path, root: Path) -> bool:
    try:
        path_r = _resolve(path)
        root_r = _resolve(root)
        path_r.relative_to(root_r)
        return True
    except ValueError:
        p = posix_path(str(_resolve(path)))
        r = posix_path(str(_resolve(root))).rstrip("/")
        if os.name == "nt":
            p, r = p.lower(), r.lower()
        return p == r or p.startswith(r + "/")
    except OSError:
        return False


def split_shell_segments(command: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    quote = ""
    i = 0
    while i < len(command):
        ch = command[i]
        if quote:
            buf.append(ch)
            if ch == quote and (i == 0 or command[i - 1] != "\\"):
                quote = ""
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            buf.append(ch)
            i += 1
            continue
        rest = command[i:]
        if rest.startswith("&&") or rest.startswith("||"):
            parts.append("".join(buf).strip())
            buf = []
            i += 2
            continue
        if ch in ";\n" or (ch == "|" and not rest.startswith("||")):
            parts.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    parts.append("".join(buf).strip())
    return [p for p in parts if p]


def tokenize(segment: str) -> list[str]:
    try:
        tokens = shlex.split(segment, posix=True)
    except ValueError:
        tokens = segment.split()
    return tokens


def strip_wrappers(tokens: list[str], wrappers: list[str]) -> list[str]:
    wrapped = {w.lower() for w in wrappers}
    i = 0
    while i < len(tokens):
        name = Path(tokens[i]).name.lower()
        if name.endswith(".exe"):
            name = name[:-4]
        if name in wrapped:
            i += 1
            while i < len(tokens) and tokens[i].startswith("-"):
                i += 1
            continue
        break
    return tokens[i:]


def flag_names(token: str) -> set[str]:
    if token.startswith("--"):
        body = token[2:].split("=", 1)[0].lower()
        return {body}
    if token.startswith("-") and len(token) > 1 and not token[1].isdigit():
        letters = {ch.lower() for ch in token[1:] if ch.isalpha()}
        return letters
    return set()


def looks_like_root_wipe(target: str) -> bool:
    t = posix_path(target.strip().strip("\"'"))
    if not t:
        return False
    lowered = t.lower()
    if t in {"/", "~", "~/", "c:", "c:/"}:
        return True
    if re.match(r"^[a-zA-Z]:/?$", t):
        return True
    if lowered in {"/users", "/home"}:
        return True
    if lowered.startswith("/users/") or lowered.startswith("/home/"):
        return True
    return False


def exe_name(token: str) -> str:
    name = Path(token).name.lower()
    if name.endswith(".exe"):
        name = name[:-4]
    return name.lstrip("&")


def is_rm_recursive_force(tokens: list[str]) -> tuple[bool, list[str]]:
    if not tokens or exe_name(tokens[0]) != "rm":
        return False, []
    flags: set[str] = set()
    targets: list[str] = []
    for token in tokens[1:]:
        if token.startswith("-"):
            names = flag_names(token)
            if names & {"recursive", "r"} or "R" in token[1:]:
                flags.add("r")
            if names & {"force", "f"}:
                flags.add("f")
            continue
        targets.append(token)
    return ("r" in flags and "f" in flags), targets


def is_remove_item_recurse(tokens: list[str]) -> tuple[bool, list[str]]:
    if not tokens:
        return False, []
    name = exe_name(tokens[0])
    if name not in {"remove-item", "ri"}:
        return False, []
    flags: set[str] = set()
    targets: list[str] = []
    i = 1
    while i < len(tokens):
        low = tokens[i].lower()
        if low in {"-recurse", "-r"}:
            flags.add("recurse")
        elif low in {"-force", "-f"}:
            flags.add("force")
        elif not tokens[i].startswith("-"):
            targets.append(tokens[i])
        i += 1
    return "recurse" in flags, targets


def strip_shell_path_token(raw: str) -> str:
    return raw.strip().strip("'\"")


def extract_shell_write_targets(command: str) -> list[str]:
    found: list[str] = []
    for match in SHELL_REDIRECT_RE.finditer(command or ""):
        path = strip_shell_path_token(match.group("path") or "")
        if path and path not in {">", ">>"}:
            found.append(path)
    for segment in split_shell_segments(command or ""):
        tokens = tokenize(segment)
        if not tokens:
            continue
        exe = exe_name(tokens[0])
        if exe in SHELL_COPY_DEST:
            dests = [t for t in tokens[1:] if not t.startswith("-")]
            if dests:
                found.append(strip_shell_path_token(dests[-1]))
    seen: set[str] = set()
    out: list[str] = []
    for item in found:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def root_labels(roots: list[Path]) -> str:
    if not roots:
        return "(none)"
    return ", ".join(str(root) for root in roots)


def outside_workspace_mode(policy: dict[str, Any]) -> str:
    write = policy.get("write") or {}
    mode = write.get("outside_workspace")
    if isinstance(mode, str) and mode.strip():
        value = mode.strip().lower()
        if value in {"allow", "ask", "deny"}:
            return value
    if write.get("deny_outside_workspace", True):
        return "deny"
    return "allow"


def decide_shell(
    command: str,
    policy: dict[str, Any] | None = None,
    *,
    cwd: str | None = None,
    roots: list[Path] | None = None,
) -> Decision:
    command = command or ""
    if not command.strip():
        return Decision("allow")
    policy = policy or load_policy()
    shell = policy.get("shell") or {}
    wrappers = list(shell.get("wrappers") or [])
    network = {n.lower() for n in (shell.get("network") or [])}
    bound_roots = list(roots or [])
    mode = outside_workspace_mode(policy)

    if first_match(shell.get("deny_regex") or [], command):
        return Decision(
            "deny",
            "Blocked a destructive shell command.",
            "A safety hook denied this command. Do not wrap it to evade the hook.",
        )

    for segment in split_shell_segments(command):
        tokens = strip_wrappers(tokenize(segment), wrappers)
        if not tokens:
            continue
        rm_rf, targets = is_rm_recursive_force(tokens)
        if rm_rf:
            if any(looks_like_root_wipe(t) for t in targets) or not targets:
                return Decision(
                    "deny",
                    "Blocked a destructive shell command.",
                    "A safety hook denied this command. Do not wrap it to evade the hook.",
                )
            return Decision(
                "ask",
                f"Approve this shell command?\n{command}",
                "A safety hook requires approval (force-push, destructive delete, or outbound network).",
            )
        recurse, ps_targets = is_remove_item_recurse(tokens)
        if recurse:
            if any(looks_like_root_wipe(t) for t in ps_targets):
                return Decision(
                    "deny",
                    "Blocked a destructive shell command.",
                    "A safety hook denied this command. Do not wrap it to evade the hook.",
                )
            return Decision(
                "ask",
                f"Approve this shell command?\n{command}",
                "A safety hook requires approval (force-push, destructive delete, or outbound network).",
            )
        exe = exe_name(tokens[0])
        if exe in network:
            return Decision(
                "ask",
                f"Approve this shell command?\n{command}",
                "A safety hook requires approval (force-push, destructive delete, or outbound network).",
            )

    if first_match(shell.get("ask_regex") or [], command):
        return Decision(
            "ask",
            f"Approve this shell command?\n{command}",
            "A safety hook requires approval (force-push, destructive delete, or outbound network).",
        )

    if mode != "allow" and bound_roots:
        for raw in extract_shell_write_targets(command):
            path = resolve_write_path(raw, cwd, bound_roots)
            if path is None:
                continue
            if is_protected_write(path, policy):
                return Decision(
                    "deny",
                    f"Blocked shell write to hook configuration: {path}",
                    "Do not modify hook adapters or disableAllHooks. Edit hooks/policy.json in agent-kit instead.",
                )
            if not any(is_under(path, root) for root in bound_roots):
                label = root_labels(bound_roots)
                if mode == "deny":
                    return Decision(
                        "deny",
                        f"Blocked shell write outside the repo workspace: {path}\nBound to: {label}",
                        "Do not use shell redirects or scripts to write outside the opened repo. "
                        "Ask the user to approve an outside-repo path, or open the correct folder.",
                    )
                return Decision(
                    "ask",
                    f"Approve shell write outside the repo?\nTarget: {path}\nBound to: {label}\nCommand:\n{command}",
                    "This shell write leaves the opened repo. Approval is tied to this workspace.",
                )

    return Decision("allow")


def peek_file(path: Path) -> str:
    try:
        with path.open("rb") as handle:
            data = handle.read(READ_CONTENT_LIMIT)
        return data.decode("utf-8", errors="replace")
    except OSError:
        return ""


def decide_read(
    file_path: str,
    content: str = "",
    policy: dict[str, Any] | None = None,
    *,
    inspect_disk: bool = False,
    cwd: str | None = None,
) -> Decision:
    path = posix_path(file_path or "")
    read = (policy or load_policy()).get("read") or {}
    if first_match(read.get("deny_path_regex") or [], path):
        return Decision("deny", f"Blocked read of secret path: {file_path}")
    body = content or ""
    if inspect_disk and not body and file_path:
        resolved = resolve_path(file_path, cwd)
        if resolved is not None and resolved.is_file():
            body = peek_file(resolved)
    if first_match(read.get("deny_content_regex") or [], body):
        return Decision(
            "deny",
            f"Blocked read; file looks like a private key or encrypted secret: {file_path}",
        )
    if first_match(read.get("allow_path_regex") or [], path):
        return Decision("allow")
    if first_match(read.get("ask_path_regex") or [], path):
        return Decision(
            "deny",
            f"Blocked read of likely secret file: {file_path}. "
            "If this is intentional, copy only the needed non-secret values into the prompt.",
        )
    return Decision("allow")


def extract_tool_paths(tool_input: Any) -> list[str]:
    if not isinstance(tool_input, dict):
        return []
    found: list[str] = []
    for key in PATH_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            found.append(value)
    files = tool_input.get("files")
    if isinstance(files, list):
        for item in files:
            if isinstance(item, str) and item.strip():
                found.append(item)
            elif isinstance(item, dict):
                for key in PATH_KEYS:
                    value = item.get(key)
                    if isinstance(value, str) and value.strip():
                        found.append(value)
    patch = tool_input.get("patch")
    if isinstance(patch, str):
        found.extend(match.strip() for match in PATCH_PATH_RE.findall(patch) if match.strip())
    seen: set[str] = set()
    out: list[str] = []
    for item in found:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def extract_tool_path(tool_input: Any) -> str | None:
    paths = extract_tool_paths(tool_input)
    return paths[0] if paths else None


def is_protected_write(path: Path, policy: dict[str, Any]) -> bool:
    write = policy.get("write") or {}
    candidates = {posix_path(str(path))}
    try:
        candidates.add(posix_path(str(_resolve(path))))
    except OSError:
        pass
    # Also check the unresolved home-relative form for ~/.cursor/hooks symlinks.
    for candidate in list(candidates):
        if first_match(write.get("deny_path_regex") or [], candidate):
            return True
    return False


def decide_write(
    raw_path: str,
    cwd: str | None,
    roots: list[Path],
    policy: dict[str, Any] | None = None,
) -> Decision:
    policy = policy or load_policy()
    write = policy.get("write") or {}
    path = resolve_write_path(raw_path, cwd, roots)
    if path is None:
        return Decision("deny", "Blocked write; could not resolve the target path.")
    # Protect hook config using both raw and resolved forms.
    raw_resolved = resolve_path(raw_path, cwd)
    if is_protected_write(path, policy) or (
        raw_resolved is not None and is_protected_write(raw_resolved, policy)
    ):
        return Decision(
            "deny",
            f"Blocked write to hook configuration: {path}",
            "Do not modify hook adapters or disableAllHooks. Edit hooks/policy.json in agent-kit instead.",
        )
    # Also catch writes addressed via ~/.cursor/hooks even when resolved into a linked kit.
    raw_posix = posix_path(raw_path.strip().strip("'\""))
    if first_match(write.get("deny_path_regex") or [], raw_posix):
        return Decision(
            "deny",
            f"Blocked write to hook configuration: {raw_path}",
            "Do not modify hook adapters or disableAllHooks. Edit hooks/policy.json in agent-kit instead.",
        )
    mode = outside_workspace_mode(policy)
    if mode == "allow":
        return Decision("allow")
    if not roots:
        return Decision(
            "deny",
            f"Blocked write to {path}; no workspace root was provided.",
            "Stay inside the opened project.",
        )
    if any(is_under(path, root) for root in roots):
        return Decision("allow")
    label = root_labels(roots)
    if mode == "deny":
        return Decision(
            "deny",
            f"Blocked write outside the workspace: {path}\nBound to: {label}",
            "Work only inside the opened project, or ask the user to open the correct folder.",
        )
    return Decision(
        "ask",
        f"Approve write outside the repo?\nTarget: {path}\nBound to: {label}",
        "This write leaves the opened repo. Approval is tied to this workspace.",
    )


def decide_writes(
    paths: list[str],
    cwd: str | None,
    roots: list[Path],
    policy: dict[str, Any] | None = None,
    *,
    require_path: bool = True,
) -> Decision:
    if not paths:
        if require_path:
            return Decision("deny", "Blocked write; no target path was provided.")
        return Decision("allow")
    for raw in paths:
        decision = decide_write(raw, cwd, roots, policy)
        if decision.permission != "allow":
            return decision
    return Decision("allow")


def event_name(payload: dict[str, Any]) -> str:
    return str(
        payload.get("hook_event_name")
        or payload.get("hookEventName")
        or payload.get("event")
        or ""
    )


def disable_all_hooks_requested(payload: dict[str, Any]) -> bool:
    settings = payload.get("settings")
    if isinstance(settings, dict) and settings.get("disableAllHooks") is True:
        return True
    compact = re.sub(r"\s+", "", json.dumps(payload, ensure_ascii=False))
    return bool(re.search(r'"disableAllHooks":true', compact, flags=re.IGNORECASE))


def decide_config_change(payload: dict[str, Any], policy: dict[str, Any] | None = None) -> Decision:
    policy = policy or load_policy()
    if disable_all_hooks_requested(payload):
        return Decision(
            "deny",
            "Blocked a settings change that would disable hooks.",
            "Hook policy is required. Do not set disableAllHooks.",
        )
    raw = (
        extract_tool_path(payload.get("tool_input") or {})
        or payload.get("file_path")
        or payload.get("path")
        or ""
    )
    if isinstance(raw, str) and raw.strip():
        cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None
        path = resolve_path(raw, cwd)
        if path is not None and is_protected_write(path, policy):
            return Decision(
                "deny",
                f"Blocked write to hook configuration: {path}",
                "Do not modify hook adapters from a session.",
            )
    return Decision("allow")
