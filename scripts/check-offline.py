#!/usr/bin/env python3
"""Assert that the offline RDF checkers a generated package ships still bite.

Run from inside a generated package directory; `check:offline:case` does that.

The package's own content cannot answer this. A freshly generated package ships
one `example.ttl` that declares no shapes and no vocabulary terms, so every
check is a no-op over it and a checker that had stopped detecting anything
would look exactly as healthy as one that works. So this drives the *rendered*
package's own `bin/` over two fixtures instead:

* `tests/fixtures/good` - a small catalog and vocabulary that satisfy every
  check, so a checker that started reporting a false positive fails here;
* `tests/fixtures/bad` - one planted fault per checker, so a checker that
  stopped detecting its fault fails here.

Both run through `bin/check_all.py` exactly as `task check:offline` does,
which also exercises the `uv run --script` header and the subprocess hand-off
to the five individual checkers.

Exits non-zero with a one-line reason on the first failure.
"""

import re
import subprocess
import sys
from pathlib import Path

BIN = Path("bin")

CHECKERS = (
    "audit_queries.py",
    "check_all.py",
    "check_dangling.py",
    "check_paths.py",
    "check_placeholders.py",
    "check_path_builder_queries.py",
)

# tests/ lives beside scripts/ in the template repository, not in the rendered
# package, so resolve it from this file rather than from the working directory.
FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def fail(message):
    print(f"check-offline: {message}", file=sys.stderr)
    sys.exit(1)


def run_checks(target):
    """Run the package's own check_all.py over a directory; return (code, output)."""
    result = subprocess.run(
        ["uv", "run", str(BIN / "check_all.py"), str(target)],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout + result.stderr


def main():
    if not BIN.is_dir():
        fail(f"{BIN} does not exist - the template did not ship the checkers")

    missing = [name for name in CHECKERS if not (BIN / name).is_file()]
    if missing:
        fail(f"missing checker(s): {', '.join(missing)}")

    for name in CHECKERS:
        first = (BIN / name).read_text().splitlines()[0]
        if "uv run --script" not in first:
            fail(f"{BIN / name} lost its uv shebang: {first!r}")

    for kind in ("good", "bad"):
        if not (FIXTURES / kind).is_dir():
            fail(f"fixture directory {FIXTURES / kind} is missing")

    code, output = run_checks(FIXTURES / "good")
    if code != 0:
        fail(f"the good fixture failed, which it must not:\n{output}")

    code, output = run_checks(FIXTURES / "bad")
    if code == 0:
        fail(f"the bad fixture passed, so a checker stopped detecting:\n{output}")

    # Each checker has to be the one that caught its own planted fault. A
    # single checker failing on all four would satisfy the exit code above
    # while three others had quietly gone blind.
    for name in ("check_dangling.py", "check_placeholders.py", "check_paths.py",
                 "audit_queries.py", "check_path_builder_queries.py"):
        # The summary pads names to the longest checker name, so match the
        # line by name and verdict rather than by column width.
        if not re.search(rf"^\s+{re.escape(name)}\s+FAIL\s*$", output, re.MULTILINE):
            fail(f"{name} did not report its planted fault in the bad fixture:\n{output}")

    # The package as generated has no catalog, which is a pass with a note
    # rather than a failure - otherwise every new package starts red.
    code, output = run_checks(Path("."))
    if code != 0:
        fail(f"the generated package itself failed the offline checks:\n{output}")

    print("check-offline: ok (good fixture passes, every checker catches its fault)")


if __name__ == "__main__":
    main()
