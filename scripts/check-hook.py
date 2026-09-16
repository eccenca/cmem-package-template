#!/usr/bin/env python3
"""Smoke test the Stop hook a generated package ships.

Run from inside a generated package directory; `check:hook:case` does that.

This is a blocking hook, so both directions matter and both are asserted here:
it must speak when a template owned file was edited, and it must stay silent on
a clean tree and whenever `stop_hook_active` is set. An earlier version of this
check asserted silence twice against a clean tree, where the hook is silent
either way - so a permanently mute hook passed it, and so would deleting the
loop guard.

Markers go to a throwaway temp directory. The hook fires at most once per
session id and records that in the system temp directory, so a reused id would
make a genuine regression fail once and then pass forever.

What this cannot tell you is whether the hook fires on the *right* evidence in a
real repository. That is still a hand run.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(".claude") / "hooks" / "template-feedback.py"

# Template owned, present in every generated package, and harmless to dirty.
VICTIM = Path("Taskfile.yaml")


def run(session: str, *, stop_hook_active: bool, tmpdir: str) -> str:
    """Invoke the hook with one payload and return what it printed."""
    payload = json.dumps(
        {
            "hook_event_name": "Stop",
            "session_id": session,
            "stop_hook_active": stop_hook_active,
        }
    )
    environment = dict(os.environ, TMPDIR=tmpdir)
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    if result.returncode != 0:
        fail(f"the hook exited {result.returncode}; it must always exit 0\n{result.stderr}")
    return result.stdout.strip()


def fail(message: str) -> None:
    """Report one reason and stop."""
    print(f"check-hook: {message}")
    sys.exit(1)


def restore() -> None:
    """Undo the edit this check makes."""
    subprocess.run(["git", "checkout", "--", str(VICTIM)], check=False)


def main() -> None:
    """Assert the hook is quiet when it should be and loud when it should be."""
    if not HOOK.is_file():
        fail(f"{HOOK} is missing")

    with tempfile.TemporaryDirectory() as tmpdir:
        quiet = run("clean-tree", stop_hook_active=False, tmpdir=tmpdir)
        if quiet:
            fail(f"spoke on a clean tree: {quiet}")

        with VICTIM.open("a", encoding="utf-8") as handle:
            handle.write("\n# provoke the template feedback hook\n")
        try:
            loud = run("edited-owned-file", stop_hook_active=False, tmpdir=tmpdir)
            if not loud:
                fail(f"stayed silent after {VICTIM} was edited")
            try:
                spoken = json.loads(loud)
            except json.JSONDecodeError:
                fail(f"printed something that is not JSON: {loud}")
            if spoken.get("decision") != "block" or not spoken.get("reason"):
                fail(f"printed JSON without a blocking reason: {loud}")
            if str(VICTIM) not in spoken["reason"]:
                fail(f"blocked without naming {VICTIM}: {spoken['reason']}")

            guarded = run("loop-guard", stop_hook_active=True, tmpdir=tmpdir)
            if guarded:
                fail(f"ignored stop_hook_active with a dirty tree: {guarded}")
        finally:
            restore()

    print("check-hook: ok (quiet when clean, blocks on a template owned edit, respects the loop guard)")


if __name__ == "__main__":
    main()
