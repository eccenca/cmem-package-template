#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
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

Both run through `bin/check_all.py` by path, exactly as `task check:offline`
does, which also exercises the `uv run --script` header, the executable bits
and the subprocess hand-off to the individual checkers. Two more cases: a
checker that cannot be run must fail with one line rather than a traceback,
and a broken `.claude/skill-map.custom.json` must fail the check by name, while
a sound one passes.

Exits non-zero with a one-line reason on the first failure.
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

BIN = Path("bin")

CHECKERS = (
    "audit_queries.py",
    "check_all.py",
    "check_dangling.py",
    "check_paths.py",
    "check_placeholders.py",
    "check_skill_map.py",
)

CUSTOM_MAP = Path(".claude") / "skill-map.custom.json"

# tests/ lives beside scripts/ in the template repository, not in the rendered
# package, so resolve it from this file rather than from the working directory.
FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def fail(message):
    print(f"check-offline: {message}", file=sys.stderr)
    sys.exit(1)


def run_checks(target, bin_dir=BIN):
    """Run the package's own check_all.py over a directory by path; return (code, output)."""
    result = subprocess.run(
        [str(bin_dir / "check_all.py"), str(target)],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout + result.stderr


def check_unrunnable():
    """A checker without its executable bit fails as one line, not a 20-line traceback."""
    with tempfile.TemporaryDirectory() as tmpdir:
        copy = Path(tmpdir) / "bin"
        shutil.copytree(BIN, copy)
        child = copy / "check_dangling.py"
        child.chmod(child.stat().st_mode & ~(stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
        code, output = run_checks(FIXTURES / "good", copy)
    if code == 0 or "Traceback" in output or "cannot run check_dangling.py" not in output:
        fail(f"an unrunnable checker did not fail with a plain line:\n{output}")


def check_custom_map():
    """A broken project skill map fails check:offline by name; a sound one passes."""
    if CUSTOM_MAP.exists():
        fail(f"{CUSTOM_MAP} already exists in the rendered case; the template must not write it")
    try:
        CUSTOM_MAP.write_text('{"rules": [{"skill": "package-content", "content": ["(unbalanced"]}]}')
        code, output = run_checks(Path("."))
        if code == 0 or "skill-map.custom.json" not in output or "check_skill_map.py" not in output:
            fail(f"a broken {CUSTOM_MAP} passed check:offline, or went unnamed:\n{output}")
        CUSTOM_MAP.write_text('{"rules": [{"skill": "package-content", "paths": ["setup/*.json"]}]}')
        code, output = run_checks(Path("."))
        if code != 0:
            fail(f"a sound {CUSTOM_MAP} failed check:offline:\n{output}")
    finally:
        CUSTOM_MAP.unlink(missing_ok=True)


def check_task_tags():
    """task_tags.py tags every kind of task an export holds - a dataset, a custom task and a workflow
    as one file, a transform and a linking task as a directory of their own - and --check then finds
    each one tagged."""
    meta = "<MetaData><Label>{0}</Label><Tags> </Tags></MetaData>"
    with tempfile.TemporaryDirectory() as tmpdir:
        project = Path(tmpdir) / "package" / "projects" / "demo"
        files = {
            "config.xml": f"<ProjectConfig>{meta.format('demo')}</ProjectConfig>",
            "dataset/books.xml": f"<Dataset id=\"books\">{meta.format('books')}</Dataset>",
            "transform/books-to-library/rules.xml":
                f"<TransformSpec>{meta.format('books to library')}<Rule>{meta.format('')}</Rule></TransformSpec>",
            "linking/link-authors/linkSpec.xml": f"<LinkSpec>{meta.format('link authors')}</LinkSpec>",
        }
        for name, text in files.items():
            (project / name).parent.mkdir(parents=True, exist_ok=True)
            (project / name).write_text(text)
        register = Path(tmpdir) / "task-tags.json"
        register.write_text(json.dumps({
            "project-tags": {"demo": ["demo", "from-repository"]}, "systems": [],
            "projects": {"demo": {"books": ["source", "demo-data"], "books-to-library": ["generated"],
                                  "link-authors": ["generated"]}}}))
        tool = [str(BIN / "task_tags.py")]
        write = subprocess.run(tool + ["--write", str(Path(tmpdir) / "package"), str(register)],
                               capture_output=True, text=True)
        check = subprocess.run(tool + ["--check", str(Path(tmpdir) / "package"), str(register)],
                               capture_output=True, text=True)
        if write.returncode != 0 or check.returncode != 0:
            fail(f"task_tags.py did not tag every kind of task:\n{write.stderr}{check.stderr}")
        for name in ("transform/books-to-library/rules.xml", "linking/link-authors/linkSpec.xml"):
            text = (project / name).read_text()
            if "urn:silkframework:tag:generated" not in text.split("</MetaData>")[0]:
                fail(f"task_tags.py --write left {name} untagged")


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
        if not os.access(BIN / name, os.X_OK):
            fail(f"{BIN / name} is not executable; check_all.py and the Taskfile run it by path")

    for kind in ("good", "bad"):
        if not (FIXTURES / kind).is_dir():
            fail(f"fixture directory {FIXTURES / kind} is missing")

    check_task_tags()

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
                 "audit_queries.py"):
        if f"  {name:21}  FAIL" not in output and f"{name}  FAIL" not in output:
            fail(f"{name} did not report its planted fault in the bad fixture:\n{output}")

    # The package as generated has no catalog, which is a pass with a note
    # rather than a failure - otherwise every new package starts red.
    code, output = run_checks(Path("."))
    if code != 0:
        fail(f"the generated package itself failed the offline checks:\n{output}")

    check_unrunnable()
    check_custom_map()

    print("check-offline: ok (good fixture passes, every checker catches its fault, "
          "an unrunnable checker and a broken skill map fail by name)")


if __name__ == "__main__":
    main()
