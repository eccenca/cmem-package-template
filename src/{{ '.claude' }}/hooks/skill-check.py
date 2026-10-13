#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Make sure the skills that cover a file are loaded before the file is changed.

This is a Claude Code hook for two events, registered in ``.claude/settings.json``
and run directly, not through a task, because stdout is the hook's JSON channel.

``PreToolUse`` (Edit, Write, NotebookEdit, Bash)
    An edit of a file that a rule in ``.claude/skill-map.json`` or the project's own
    ``.claude/skill-map.custom.json`` maps to a skill is denied until the session has
    loaded that skill - invoked it (Skill tool or ``/name``) or read its ``SKILL.md``.
    The reason names the skill, so the agent loads it and retries. A shell command
    that changes files of the project by hand - ``sed -i``, a redirect or ``tee`` into
    the repository, an inline Python script that writes files - is denied as well, so
    that every edit goes through the file tools and their check. Writing into
    ``data/``, ``dist/`` or a temporary directory, and running the project's own
    scripts and tasks, stay allowed.

``Stop``
    The backstop: files changed during the session - also by a script the first part
    could not see into - whose skills the session never loaded block the end of the
    session once, naming them.

A hand run needs a payload on stdin::

    echo '{"hook_event_name": "Stop", "session_id": "x"}' | python3 .claude/hooks/skill-check.py

It belongs to the template - see ``.claude/rules/copier-template.md``. Project
specific rules go into ``.claude/skill-map.custom.json``, which the template never
writes.

Three rules govern everything below, as in ``template-feedback.py``. Print nothing
unless there is something to say. Always exit 0. And when a fact cannot be
established - an unreadable transcript, a command the tokenizer cannot split, a
target behind a shell variable - let the action pass: a false refusal stalls a
session, a missed one is caught by the ``Stop`` check or a review.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# The template's rules and the project's own, both relative to the project root.
MAPS = (Path(".claude") / "skill-map.json", Path(".claude") / "skill-map.custom.json")

# Where a shell command may still write inside the project: git-ignored output and git itself.
WRITABLE = ("data/", "dist/", ".git/")
TEMP = (tempfile.gettempdir(), "/tmp", "/private/tmp", "/private/var/folders", "/var/folders", "/dev")

FILE_TOOLS = ("Edit", "Write", "NotebookEdit")


def project_root(event: dict) -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()).resolve()


def rules(root: Path) -> list[dict]:
    found = []
    for name in MAPS:
        path = root / name
        if path.is_file():
            found.extend(json.loads(path.read_text(encoding="utf-8")).get("rules", []))
    return found


def skill_exists(root: Path, skill: str) -> bool:
    """A skill can be loaded only if the project or the user has it."""
    return any(
        (base / skill / "SKILL.md").is_file()
        for base in (root / ".claude" / "skills", Path.home() / ".claude" / "skills")
    )


def required(root: Path, relative: str, text: str) -> list[str]:
    """The skills a file needs: every rule whose path glob or content pattern matches."""
    skills = []
    for rule in rules(root):
        by_path = any(fnmatch.fnmatch(relative, pattern) for pattern in rule.get("paths", []))
        by_content = bool(text) and any(re.search(pattern, text) for pattern in rule.get("content", []))
        skill = rule.get("skill", "")
        if (by_path or by_content) and skill not in skills and skill_exists(root, skill):
            skills.append(skill)
    return skills


def transcript_entries(event: dict) -> list[dict]:
    path = Path(event.get("transcript_path") or "")
    if not path.is_file():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue
    return entries


def tool_uses(entries: list[dict]):
    for entry in entries:
        content = entry.get("message", {}).get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    yield block.get("name"), block.get("input") or {}


def loaded(entries: list[dict]) -> set[str]:
    """Skills the session invoked, or whose SKILL.md it read."""
    names = set()
    for tool, tool_input in tool_uses(entries):
        if tool == "Skill":
            names.add(str(tool_input.get("skill", "")).split(":")[-1])
        elif tool == "Read":
            match = re.search(r"/skills/([^/]+)/SKILL\.md$", str(tool_input.get("file_path", "")))
            if match:
                names.add(match.group(1))
    for entry in entries:
        content = entry.get("message", {}).get("content")
        text = content if isinstance(content, str) else json.dumps(content or "")
        for name in re.findall(r"<command-name>/?([\w:-]+)</command-name>", text):
            names.add(name.split(":")[-1])
    return names


def relative_to(path: Path, root: Path) -> str | None:
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return None


def deny(reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))


def check_file_edit(event: dict, root: Path) -> None:
    tool_input = event.get("tool_input", {})
    raw = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    relative = relative_to(Path(raw).expanduser(), root) if raw else None
    if relative is None:
        return
    text = "\n".join(str(tool_input.get(k, "")) for k in ("content", "new_string", "new_source"))
    missing = [s for s in required(root, relative, text) if s not in loaded(transcript_entries(event))]
    if missing:
        deny(f"{relative} is covered by the skill(s) {', '.join(missing)}, which this session has not "
             f"loaded. Load {' and '.join(missing)} with the Skill tool, apply what they say to this edit, "
             "then retry it. (Rules: .claude/skill-map.json and .claude/skill-map.custom.json)")


def inside_project(target: str, cwd: Path, root: Path) -> bool:
    """Whether a shell write target is a file of the project that must go through the file tools."""
    if "$" in target or "`" in target or target.startswith("&"):
        return False  # resolved only at run time: unknown, so let it pass
    path = Path(os.path.expanduser(target))
    path = path if path.is_absolute() else cwd / path
    if str(path).startswith(TEMP) or str(path.resolve()).startswith(TEMP):
        return False
    relative = relative_to(path, root)
    return relative is not None and not relative.startswith(WRITABLE)


def shell_edit(command: str, cwd: Path, root: Path) -> str | None:
    """What makes the command a hand edit of project files, or None."""
    if re.search(r"\b(sed|perl)\b[^|;&]*\s-[a-zA-Z]*i", command):
        return "an in-place sed/perl edit"
    if re.search(r"\b(python3?|uv run[^|;&]*python3?)\s+(-c\b|-\s*<<)", command) and re.search(
        r"write_text\(|write_bytes\(|open\([^)]*['\"][wax]\+?b?['\"]|\.write\(|json\.dump\(|"
        r"shutil\.(copy|move)|os\.(rename|replace|remove)|\.unlink\(", command
    ):
        return "an inline Python script that writes files"
    # Heredoc bodies are data, not shell: drop them before tokenizing.
    bare = re.sub(r"<<-?\s*['\"]?(\w+)['\"]?\n.*?\n\1\b", "", command, flags=re.S)
    try:
        lexer = shlex.shlex(bare, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return None  # unbalanced quotes: cannot tell, let it pass
    here = cwd
    for index, token in enumerate(tokens):
        following = tokens[index + 1] if index + 1 < len(tokens) else ""
        if token == "cd" and following and not following.startswith("-"):
            here = (here / os.path.expanduser(following)).resolve()
        elif token in (">", ">>", ">|") and following and inside_project(following, here, root):
            return f"a redirect into {following}"
        elif token == "tee":
            targets = [t for t in tokens[index + 1:] if t not in ("-a", "--append")]
            if targets and inside_project(targets[0], here, root):
                return f"tee into {targets[0]}"
    return None


def check_shell(event: dict, root: Path) -> None:
    command = event.get("tool_input", {}).get("command", "")
    cwd = Path(event.get("cwd") or os.getcwd())
    what = shell_edit(command, cwd, root)
    if what:
        deny(f"This command changes files of the project through the shell ({what}). Edit them with the "
             "Edit or Write tool, so that the skill check of .claude/hooks/skill-check.py applies. Writing "
             "into data/, dist/ or a temporary directory, and running the project's own scripts and tasks, "
             "stay allowed.")


def session_start(entries: list[dict]) -> float | None:
    for entry in entries:
        stamp = entry.get("timestamp")
        if stamp:
            try:
                return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
            except ValueError:
                continue
    return None


def changed_files(root: Path, since: float) -> list[str]:
    """Files of the working tree that differ from git and were written during the session."""
    result = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=root,
                            capture_output=True, text=True, check=False)
    files = []
    for line in result.stdout.splitlines():
        name = line[3:].split(" -> ")[-1].strip('"')
        path = root / name
        if path.is_file() and path.stat().st_mtime >= since:
            files.append(name)
    return files


def check_stop(event: dict, root: Path) -> None:
    if event.get("stop_hook_active"):
        return
    session = re.sub(r"[^\w-]", "", str(event.get("session_id")))
    marker = Path(tempfile.gettempdir()) / f"skill-check-{session}"
    if marker.exists():
        return
    entries = transcript_entries(event)
    since = session_start(entries)
    if since is None:
        return
    have = loaded(entries)
    gaps = {}
    for relative in changed_files(root, since):
        try:
            text = (root / relative).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        for skill in required(root, relative, text):
            if skill not in have:
                gaps.setdefault(skill, []).append(relative)
    if gaps:
        marker.touch()
        listing = "; ".join(f"{skill}: {', '.join(files[:5])}" for skill, files in sorted(gaps.items()))
        print(json.dumps({"decision": "block",
                          "reason": "This session changed files whose skills it never loaded - " + listing +
                                    ". Load each skill, check the changes against it, and fix what departs."}))


def main() -> None:
    event = json.load(sys.stdin)
    root = project_root(event)
    if event.get("hook_event_name") == "Stop":
        check_stop(event, root)
    elif event.get("tool_name") in FILE_TOOLS:
        check_file_edit(event, root)
    elif event.get("tool_name") == "Bash":
        check_shell(event, root)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - a broken hook must never stall a session
        pass
