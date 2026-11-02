#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Assert that one `task layout` satisfies `task layout:check`, wherever a sticky note was dropped.

Run from inside a generated package directory; `check:layout:case` does that.

A generated package has no build project, so nothing in its own checks lays out a workflow. This
drives the rendered package's layout script over a small export, a guarded migration with a
dependency chain and one sticky note, placed at each point of a grid: a single --write must leave
nothing for --check to report. A note anchors to the node nearest it on the old canvas, so a layout
that stops after one pass leaves a canvas the next pass changes again, and a package gating on
layout:check fails right after `task layout`.

Exits non-zero with a one-line reason on the first failure.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path("bin") / "layout_workflows.py"

# id, kind, data inputs, dependency inputs
NODES = [
    ("previous", "Dataset", "", ""),
    ("check", "Operator", "previous", ""),
    ("stop-unless-needed", "Operator", "check", ""),
    ("clear-backup", "Operator", "", "stop-unless-needed"),
    ("backup-cleared", "Dataset", "clear-backup", ""),
    ("back-up", "Operator", "previous", "backup-cleared"),
    ("backup", "Dataset", "back-up", ""),
    ("move", "Operator", "", "backup"),
    ("current", "Dataset", "move", ""),
    ("verify", "Operator", "current", ""),
    ("fail-on-difference", "Operator", "verify", ""),
]


def fail(message):
    print(f"check-layout-workflows: {message}", file=sys.stderr)
    sys.exit(1)


def project(root: Path, x: int, y: int) -> Path:
    folder = root / "projects" / "migration"
    (folder / "workflow").mkdir(parents=True)
    (folder / "dataset").mkdir()
    (folder / "config.xml").write_text("<ProjectConfig/>")
    for name in ("previous", "backup", "current"):
        (folder / "dataset" / f"{name}.xml").write_text(
            f'<Dataset id="{name}" type="eccencaDataPlatform"><Param name="graph">'
            f'<![CDATA[https://example.com/{name}/]]></Param></Dataset>')
    nodes = "".join(
        f'  <{kind} posX="0" posY="0" task="{"backup" if node.startswith("backup") else node}" '
        f'inputs="{inputs}" outputs="" errorOutputs="" id="{node}" configInputs="" dependencyInputs="{deps}"/>\n'
        for node, kind, inputs, deps in NODES)
    note = (f'<UiAnnotations><StickyNotes><StickyNote id="read-this" color="#ffd966"><Content>Read this</Content>'
            f'<Position x="{x}" y="{y}"/><Dimension width="600" height="160"/></StickyNote></StickyNotes></UiAnnotations>')
    (folder / "workflow" / "migrate.xml").write_text(
        f'<Workflow id="migrate" replaceableInputs="" replaceableOutputs="">\n{nodes}  {note}\n</Workflow>\n')
    return folder


def run(mode: str, folder: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["uv", "run", "--script", str(SCRIPT), mode, str(folder)], capture_output=True, text=True)


def main():
    if not SCRIPT.exists():
        fail(f"{SCRIPT} not found; run from inside a generated package")
    points = [(x, y) for x in range(-300, 3301, 450) for y in range(-400, 1601, 400)]
    for x, y in points:
        with tempfile.TemporaryDirectory() as tmp:
            folder = project(Path(tmp), x, y)
            written = run("--write", folder)
            if written.returncode:
                fail(f"--write failed for a note at {x},{y}: {written.stderr.strip()}")
            if run("--check", folder).returncode:
                fail(f"a note dropped at {x},{y} needs a second `task layout` before layout:check passes")
    print(f"check-layout-workflows: ok ({len(points)} note positions)")


main()
