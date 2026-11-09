#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Assert that bin/check_construct_graphs.py catches a Construct reading the whole store.

Run from inside a generated package directory; `check:construct:case` does that.

A generated package has no build project, so its own `check:offline` passes whatever the checker
does. This drives the rendered package's `bin/check_construct_graphs.py` over small project exports
written here: a Construct on a Knowledge Graph input naming its graph, and one on an in-memory and
one on an RDF file input naming none, must pass; a Construct on a Knowledge Graph input naming no
graph - fed by a dataset node or wired as the operator's input - must fail.

Exits non-zero with a one-line reason on the first failure.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path("bin") / "check_construct_graphs.py"
PLAIN = "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }"
NAMED = "# copies the source graph\nCONSTRUCT { ?s ?p ?o } WHERE { GRAPH <urn:source> { ?s ?p ?o } }"


def fail(message):
    print(f"check-construct-graphs: {message}", file=sys.stderr)
    sys.exit(1)


def package(root: Path, dataset_type: str, query: str, wired_as_input: bool) -> Path:
    """One project: a dataset of the given type feeding one Construct task into a target."""
    folder = root / "projects" / "copies"
    for sub in ("dataset", "custom", "workflow"):
        (folder / sub).mkdir(parents=True)
    (folder / "config.xml").write_text("<ProjectConfig/>")
    (folder / "dataset" / "source.xml").write_text(f'<Dataset id="source" type="{dataset_type}"/>')
    (folder / "dataset" / "target.xml").write_text('<Dataset id="target" type="eccencaDataPlatform"/>')
    (folder / "custom" / "copy.xml").write_text(
        f'<CustomTask id="copy" type="sparqlCopyOperator">'
        f'<Param name="query" xml:space="preserve"><![CDATA[{query}]]></Param></CustomTask>')
    source_outputs = "" if wired_as_input else "copy-node"
    copy_inputs = "source-node" if wired_as_input else ""
    (folder / "workflow" / "publish.xml").write_text(
        f'<Workflow id="publish">'
        f'<Dataset task="source" inputs="" outputs="{source_outputs}" id="source-node"/>'
        f'<Operator task="copy" inputs="{copy_inputs}" outputs="target-node" id="copy-node"/>'
        f'<Dataset task="target" inputs="copy-node" outputs="" id="target-node"/></Workflow>')
    return root


CASES = [
    ("a Knowledge Graph input naming its graph", "eccencaDataPlatform", NAMED, False, 0),
    ("an in-memory input naming no graph", "inMemory", PLAIN, False, 0),
    ("an RDF file input naming no graph", "file", PLAIN, False, 0),
    ("a Knowledge Graph input naming no graph", "eccencaDataPlatform", PLAIN, False, 1),
    ("a Knowledge Graph input wired to the operator, naming no graph", "eccencaDataPlatform", PLAIN, True, 1),
]


def main():
    if not SCRIPT.exists():
        fail(f"{SCRIPT} not found - run from inside a generated package")
    for name, dataset_type, query, wired, expected in CASES:
        with tempfile.TemporaryDirectory() as tmp:
            root = package(Path(tmp), dataset_type, query, wired)
            result = subprocess.run([str(SCRIPT.resolve()), str(root)], capture_output=True, text=True)
        if result.returncode != expected:
            fail(f"{name}: exit {result.returncode}, expected {expected}\n{result.stdout}{result.stderr}")
    print(f"check-construct-graphs: ok ({len(CASES)} cases)")


if __name__ == "__main__":
    main()
