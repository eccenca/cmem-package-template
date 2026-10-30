#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Assert that bin/check_workflow_datasets.py catches what it is for.

Run from inside a generated package directory; `check:datasets:case` does that.

A generated package has no build project, so its own `check:offline` passes whatever the checker
does. This drives the rendered package's checker over small exports written here: an Update writing
the graph of its clearing output passes; one naming only another graph fails; a variable graph is
not judged; a staging dataset in a workflow with a replaceable input, and a dataset nothing uses,
warn.

Exits non-zero with a one-line reason on the first failure.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path("bin") / "check_workflow_datasets.py"


def fail(message):
    print(f"check-workflow-datasets: {message}", file=sys.stderr)
    sys.exit(1)


def dataset(folder, name, kind="eccencaDataPlatform", graph="", clear="false"):
    template = f'<Template name="graph"><![CDATA[{graph}]]></Template>' if graph else ""
    (folder / "dataset" / f"{name}.xml").write_text(
        f'<Dataset id="{name}" type="{kind}"><Param name="clearGraphBeforeExecution">'
        f'<![CDATA[{clear}]]></Param>{template}</Dataset>')


def package(root: Path, query: str, payload: bool = False, extra: bool = False) -> Path:
    folder = root / "projects" / "orders"
    for sub in ("dataset", "custom", "workflow"):
        (folder / sub).mkdir(parents=True)
    (folder / "config.xml").write_text("<ProjectConfig/>")
    dataset(folder, "orders", graph="{{project.ordersGraph}}", clear="true")
    if extra:
        dataset(folder, "leftover")
    (folder / "custom" / "label.xml").write_text(
        f'<CustomTask id="label" type="sparqlUpdateOperator"><Param name="sparqlUpdateTemplate">'
        f'<![CDATA[{query}]]></Param></CustomTask>')
    replaceable = 'replaceableInputs="orders-in"' if payload else 'replaceableInputs=""'
    (folder / "workflow" / "load.xml").write_text(
        f'<Workflow id="load" {replaceable} replaceableOutputs="">'
        f'<Dataset task="orders" inputs="" outputs="label" id="orders-in"/>'
        f'<Operator task="label" inputs="orders-in" outputs="orders-out" id="label"/>'
        f'<Dataset task="orders" inputs="label" outputs="" id="orders-out"/></Workflow>')
    return root


WRITES = "INSERT { GRAPH <{{ project.ordersGraph }}> { ?s a ?c } } WHERE { ?s a ?c }"
OTHER = "INSERT { GRAPH <https://example.org/labels/> { ?s a ?c } } WHERE { ?s a ?c }"
VARIABLE = "INSERT { GRAPH ?g { ?s a ?c } } WHERE { GRAPH ?g { ?s a ?c } }"
CASES = [
    ("an update writing the graph of its clearing output", WRITES, {}, 0, None),
    ("an update naming only another graph", OTHER, {}, 1, "never names that graph"),
    ("an update writing a variable graph", VARIABLE, {}, 0, None),
    ("staging in a workflow with a replaceable input", WRITES, {"payload": True}, 0, "its runs overlap"),
    ("a dataset nothing uses", WRITES, {"extra": True}, 0, "in no workflow"),
]


def main():
    if not SCRIPT.exists():
        fail(f"{SCRIPT} not found - run from inside a generated package")
    for name, query, options, code, expected in CASES:
        with tempfile.TemporaryDirectory() as tmp:
            root = package(Path(tmp), query, **options)
            result = subprocess.run([str(SCRIPT.resolve()), str(root)], capture_output=True, text=True)
        if result.returncode != code or (expected and expected not in result.stdout):
            fail(f"{name}: exit {result.returncode}, expected {code} and {expected!r}\n{result.stdout}{result.stderr}")
    print(f"check-workflow-datasets: ok ({len(CASES)} cases)")


if __name__ == "__main__":
    main()
