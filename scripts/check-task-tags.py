#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Assert that bin/task_tags.py holds a register to the tag axes of the build-projects skill.

Run from inside a generated package directory; `check:tags:case` does that.

A generated package has no build project, so its own `task tags:check` passes whatever the checker
does. This drives the rendered package's `bin/task_tags.py` over registers written here - one that
keeps every rule and one planted fault per rule - against a small
project export in a temporary directory.

Exits non-zero with a one-line reason on the first failure.
"""

import importlib.util
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
    for name in ("terms", "staged", "scratch"):
        (folder / "dataset" / f"{name}.xml").write_text("<Dataset/>")
    (folder / "workflow").mkdir()
    (folder / "workflow" / "load.xml").write_text(
        '<Workflow id="load"><Operator task="map" inputs="terms" outputs="staged-node" id="map"/>'
        '<Dataset task="staged" id="staged-node"/></Workflow>')
    return {"translations": folder}


PACKAGE = {
    "project-tags": {"translations": ["demo-pkg", "operational", "from-repository"]},
    "roles": {"training": "data for training people; never runs in production"},
    "topics": {"localization": "everything about translations"},
    "graph-roles": {"translations/staged": "entity"},
    "systems": ["kafka"],
    "projects": {"translations": {
        "terms": ["source", "master-data", "localization"],
        "staged": ["target", "training-data"],
        "scratch": ["temporary"],
        "load": ["by-schedule", "consume", "kafka", "training", "writes-entity"],
    }},
}
def planted(base: dict, change) -> dict:
    import copy
    spec = copy.deepcopy(base)
    change(spec)
    return spec


FAULTS = [
    ("a package project without a role",
     PACKAGE, lambda s: s["project-tags"].__setitem__("translations", ["demo-pkg", "from-repository"]),
     "exactly one role"),
    ("a role nobody declared",
     PACKAGE, lambda s: s["projects"]["translations"]["load"].append("rehearsal"), "rehearsal is on no axis"),
    ("a subject on a workflow",
     PACKAGE, lambda s: s["projects"]["translations"]["load"].append("localization"),
     "a subject belongs on a dataset"),
    ("a role without its use case",
     PACKAGE, lambda s: s["roles"].__setitem__("training", " "), "needs a one-line use case"),
    ("a graph role that is no writes- role",
     PACKAGE, lambda s: s["graph-roles"].__setitem__("translations/staged", "products"), "graph role products"),
]


WRITES_FAULT = ("a workflow writing into a placeholder without its writes-",
                lambda s: s["projects"]["translations"]["load"].remove("writes-entity"),
                "lacks writes-entity")


def main():
    if not SCRIPT.is_file():
        fail(f"{SCRIPT} does not exist - the template did not ship it")
    tags = load()
    with tempfile.TemporaryDirectory() as tmp:
        projects = export(Path(tmp))
        for name, spec in (("package", PACKAGE),):
            errors = tags.axis_errors(spec, projects) + tags.writes_errors(spec, projects)
            if errors:
                fail(f"the good {name} register was refused: {errors[0]}")
        for name, base, change, expected in FAULTS:
            errors = tags.axis_errors(planted(base, change), projects)
            if not any(expected in e for e in errors):
                fail(f"{name} passed (expected an error with \"{expected}\", got {errors})")
        name, change, expected = WRITES_FAULT
        errors = tags.writes_errors(planted(PACKAGE, change), projects)
        if not any(expected in e for e in errors):
            fail(f"{name} passed (expected \"{expected}\", got {errors})")
    print(f"check-task-tags: ok (a package register passes, {len(FAULTS) + 1} planted faults "
          "caught)")


if __name__ == "__main__":
    main()
