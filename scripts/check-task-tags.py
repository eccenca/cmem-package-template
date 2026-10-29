#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Assert that bin/task_tags.py holds a register to the axes it declares.

Run from inside a generated package directory; `check:tags:case` does that.

A generated package has no build project, so its own `task tags:check` passes whatever the checker
does. This drives the rendered package's `bin/task_tags.py` over registers written here - one that
declares its axes, partly through an included preset, and one planted fault per rule - against a
small project export in a temporary directory.

Exits non-zero with a one-line reason on the first failure.
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

SCRIPT = Path("bin") / "task_tags.py"


def fail(message):
    print(f"check-task-tags: {message}", file=sys.stderr)
    sys.exit(1)


def load():
    spec = importlib.util.spec_from_file_location("task_tags", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def export(root: Path) -> dict[str, Path]:
    """One project with three datasets: a source, a placeholder, and a temporary one."""
    folder = root / "projects" / "translations"
    (folder / "dataset").mkdir(parents=True)
    (folder / "config.xml").write_text("<ProjectConfig/>")
    for name in ("terms", "staged"):
        (folder / "dataset" / f"{name}.xml").write_text("<Dataset/>")
    (folder / "workflow").mkdir()
    (folder / "workflow" / "load.xml").write_text(
        '<Workflow id="load"><Operator task="map" inputs="terms" outputs="staged-node" id="map"/>'
        '<Dataset task="staged" id="staged-node"/></Workflow>')
    return {"translations": folder}


PRESET = {"axes": {
    "position": {"use": "find what a build reads or writes", "on": ["dataset"], "several": True,
                 "values": {"source": "read by a build", "target": "written by a build"}},
    "started by": {"use": "know who runs it", "on": ["workflow"],
                   "values": {"by-schedule": "a scheduler starts it"}},
}}

PACKAGE = {
    "include": ["preset.json"],
    "axes": {"package": {"use": "group a package's projects", "on": ["project"],
                         "values": {"demo-pkg": "the demo package"}}},
    "project-tags": {"translations": ["demo-pkg"]},
    "projects": {"translations": {
        "terms": ["source"],
        "staged": ["source", "target"],
        "load": ["by-schedule"],
    }},
}


def planted(base: dict, change) -> dict:
    import copy
    spec = copy.deepcopy(base)
    change(spec)
    return spec


FAULTS = [
    ("a tag declared on no axis",
     lambda s: s["projects"]["translations"]["load"].append("rehearsal"), "rehearsal is declared on no axis"),
    ("a tag on an axis that does not tag workflows",
     lambda s: s["projects"]["translations"]["load"].append("source"), "which tags no workflow"),
    ("two tags on an axis that allows one",
     lambda s: s["axes"]["package"]["values"].__setitem__("other-pkg", "x")
     or s["project-tags"]["translations"].append("other-pkg"), "two tags on the package axis"),
    ("a value without its use case",
     lambda s: s["axes"]["package"]["values"].__setitem__("demo-pkg", " "), "needs a one-line use case"),
    ("a value added to a preset axis that tags no project",
     lambda s: s["axes"].__setitem__("position", {"values": {"read-back": "read again later"}})
     or s["project-tags"]["translations"].append("read-back"), "which tags no project"),
    ("an axis without its use case",
     lambda s: s["axes"]["package"].__setitem__("use", ""), "needs \"use\""),
]


def main():
    if not SCRIPT.is_file():
        fail(f"{SCRIPT} does not exist - the template did not ship it")
    tags = load()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        projects = export(root)
        (root / "preset.json").write_text(json.dumps(PRESET))
        errors = tags.axis_errors(PACKAGE, projects, root)
        if errors:
            fail(f"the good register was refused: {errors[0]}")
        for name, change, expected in FAULTS:
            errors = tags.axis_errors(planted(PACKAGE, change), projects, root)
            if not any(expected in e for e in errors):
                fail(f"{name} passed (expected an error with \"{expected}\", got {errors})")
    print(f"check-task-tags: ok (a register with an included preset passes, {len(FAULTS)} planted faults "
          "caught)")


if __name__ == "__main__":
    main()
