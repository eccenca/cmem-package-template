#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Smoke test the skill check hook a generated package ships.

Run from inside a generated package directory; `check:skillhook:case` does that.

The hook blocks edits, so both directions are asserted: it must deny an edit of a
mapped file while the skill is not loaded, and it must pass the same edit once the
transcript shows the skill loaded, pass a file no rule maps, and pass shell commands
that only look like writes (a `>` inside a quoted pattern, a write into a temporary
directory). The Stop part must stay silent without evidence and on the loop guard.

What this cannot tell you is whether the rules in skill-map.json cover the right files
in a real package. That is a hand read.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(".claude") / "hooks" / "skill-check.py"


def fail(message: str) -> None:
    print(f"check-skill-hook: {message}")
    sys.exit(1)


def run(payload: dict, tmpdir: str) -> str:
    environment = dict(os.environ, TMPDIR=tmpdir, CLAUDE_PROJECT_DIR=str(Path.cwd()))
    # by path, as settings.json runs it: through its uv shebang
    if not os.access(HOOK, os.X_OK):
        fail(f"{HOOK} is not executable in the rendered package; settings.json runs it by path")
    result = subprocess.run([str(HOOK)], input=json.dumps(payload), capture_output=True,
                            text=True, check=False, env=environment)
    if result.returncode != 0:
        fail(f"the hook exited {result.returncode}; it must always exit 0\n{result.stderr}")
    return result.stdout.strip()


def transcript(tmpdir: str, name: str, skills: list[str]) -> str:
    path = Path(tmpdir) / f"{name}.jsonl"
    lines = [{"timestamp": "2000-01-01T00:00:00Z", "message": {"role": "user", "content": "start"}}]
    for skill in skills:
        lines.append({"message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": skill}}]}})
    path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")
    return str(path)


def edit(path: str, transcript_path: str) -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": "Edit", "cwd": str(Path.cwd()),
            "transcript_path": transcript_path,
            "tool_input": {"file_path": str(Path.cwd() / path), "old_string": "a", "new_string": "b"}}


def shell(command: str, transcript_path: str) -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(Path.cwd()),
            "transcript_path": transcript_path, "tool_input": {"command": command}}


def denied(output: str) -> bool:
    if not output:
        return False
    try:
        decision = json.loads(output)["hookSpecificOutput"]["permissionDecision"]
    except (ValueError, KeyError):
        fail(f"printed something that is not a PreToolUse decision: {output}")
    return decision == "deny"


def main() -> None:
    if not HOOK.is_file():
        fail(f"{HOOK} is missing")
    manifests = list(Path(".").glob("*/cpa-manifest.json"))
    if not manifests:
        fail("no */cpa-manifest.json to test against")
    manifest = str(manifests[0])

    with tempfile.TemporaryDirectory() as tmpdir:
        empty = transcript(tmpdir, "empty", [])
        ready = transcript(tmpdir, "ready", ["package-content"])

        output = run(edit(manifest, empty), tmpdir)
        if not denied(output) or "package-content" not in output:
            fail(f"did not deny an edit of {manifest} without package-content: {output!r}")
        if run(edit(manifest, ready), tmpdir):
            fail(f"denied an edit of {manifest} with package-content loaded")
        if run(edit("TaskfileCustom.yaml", empty), tmpdir):
            fail("denied an edit of a file no rule maps")

        if not denied(run(shell("sed -i 's/a/b/' Taskfile.yaml", empty), tmpdir)):
            fail("did not deny sed -i on a project file")
        for hand_edit in ("echo x > README.md", "echo x | tee README.md", "cat > Taskfile.yaml <<'EOF'\nx\nEOF"):
            if not denied(run(shell(hand_edit, empty), tmpdir)):
                fail(f"did not deny a hand edit of a project file: {hand_edit}")
        for harmless in ("grep -n '<a>' README.md", f"echo x > {tmpdir}/out.txt", 'echo "$S" > "$TMPFILE"',
                         "task check:offline", f"cd {tmpdir} && cat >> notes.md <<'EOF'\nline\nEOF",
                         "python3 -c \"import re; print(re.findall(r'<x>/?(\\w+)</x>', 'y'))\""):
            if run(shell(harmless, empty), tmpdir):
                fail(f"denied a harmless command: {harmless}")

        stop = {"hook_event_name": "Stop", "session_id": "skill-hook-clean", "transcript_path": empty,
                "stop_hook_active": False}
        if run(dict(stop, stop_hook_active=True), tmpdir):
            fail("spoke despite stop_hook_active")

    print("check-skill-hook: ok (denies an unloaded skill's file, passes once loaded, passes harmless "
          "commands, respects the loop guard)")


if __name__ == "__main__":
    main()
