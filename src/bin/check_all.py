#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["rdflib"]
# ///
"""Run every offline check in this toolkit over a Corporate Memory package directory.

The four checks answer questions that a SHACL validation run cannot, because the catalog has
to be installed before validation can say anything — and two of these mistakes make the
install itself useless: a dangling reference turns every graph's validation into an HTTP 500,
and a path that matches nothing turns every constraint on its row into a no-op that reports
success. Running them from the working tree catches both before an install.

    check_all.py <package-dir> [--quiet]

The Turtle files are classified by what they contain rather than by name, so no file naming
convention is assumed:

* a **shape catalog** declares a shacl:NodeShape or a shui:ShapeCatalog;
* a **vocabulary** declares an owl:Class or an owl:*Property.

A graph-description-only file — a data or integration graph shipped holding just its own
metadata — matches neither and is skipped.

Every check here is driven by a shape catalog, so a package holding none — a vocabulary
package, or one whose catalog is not written yet — passes with a note. This runs as a build
gate, and a package with nothing to answer for has not failed anything.

A file no parser accepts is the exception: that fails, because `cmemc package build` ignores
RDF syntax entirely and such a graph installs only as an error.

Exits non-zero if any check fails.
"""

import subprocess
import sys
from pathlib import Path

from rdflib import Graph
from rdflib.namespace import OWL, RDF, Namespace

SH = Namespace("http://www.w3.org/ns/shacl#")
SHUI = Namespace("https://vocab.eccenca.com/shui/")

BIN = Path(__file__).resolve().parent

# A shui:SparqlQuery counts as a shape catalog here even with no shape beside
# it. A package can ship nothing but queries, and classifying such a file as
# neither left audit_queries and check_placeholders - the two checks that are
# entirely about queries - never running over the one package built to hold
# them.
SHAPE_MARKERS = (SH.NodeShape, SH.PropertyShape, SHUI.ShapeCatalog,
                 SHUI.SparqlQuery, SHUI.SparqlOperation)
VOCAB_MARKERS = (OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty, RDF.Property)


def classify(path):
    """"shapes", "vocab", "both" or None, from what the file actually declares."""
    graph = Graph()
    try:
        graph.parse(path, format="turtle")
    except Exception as error:  # noqa: BLE001 - a broken file is a finding, not a crash
        return f"unparseable: {error}"
    types = set(graph.objects(None, RDF.type))
    is_shapes = bool(types & set(SHAPE_MARKERS))
    is_vocab = bool(types & set(VOCAB_MARKERS))
    if is_shapes and is_vocab:
        return "both"
    if is_shapes:
        return "shapes"
    if is_vocab:
        return "vocab"
    return None


def run(script, files, quiet):
    """Run one check as a subprocess; return (exit code, output)."""
    command = [sys.executable, str(BIN / script), *[str(f) for f in files]]
    result = subprocess.run(command, capture_output=True, text=True)
    output = result.stdout + result.stderr
    if not quiet:
        print(output.rstrip())
    return result.returncode, output


def check(directory, quiet=False):
    root = Path(directory)
    turtle = sorted(p for p in root.rglob("*.ttl") if p.is_file())
    if not turtle:
        print(f"{root}")
        print("OK: no .ttl file here, so there is nothing to check")
        return 0

    shapes, vocab, skipped, unparseable = [], [], [], []
    print(f"{root}")
    for path in turtle:
        kind = classify(path)
        print(f"  {path.relative_to(root)}: {kind or 'no shapes or vocabulary terms — skipped'}")
        if kind in ("shapes", "both"):
            shapes.append(path)
        if kind in ("vocab", "both"):
            vocab.append(path)
        if kind is None:
            skipped.append(path)
        if kind and kind.startswith("unparseable"):
            unparseable.append(path)

    # A file no parser accepts is a certain install failure that `package
    # build` does not catch - it checks the manifest against the directory and
    # ignores RDF syntax entirely. Fail here, and before the no-catalog pass
    # below, so a package whose only catalog is unparseable cannot slip through
    # as "nothing to check".
    if unparseable:
        print()
        names = ", ".join(str(p.relative_to(root)) for p in unparseable)
        print(f"FAIL: {len(unparseable)} file(s) no parser accepts: {names}")
        return 1

    if not shapes:
        # Every check here is driven by a shape catalog, so a package without
        # one - a plain vocabulary package, or one not yet written - has
        # nothing to answer for. This runs as a build gate, so that is a pass.
        print()
        print("OK: no shape catalog found, so there is nothing to check")
        return 0

    plan = [
        ("check_dangling.py", shapes),
        ("check_placeholders.py", shapes),
        ("check_paths.py", shapes + vocab),
        ("audit_queries.py", shapes),
    ]

    results = []
    for script, files in plan:
        if not quiet:
            print()
            print("=" * 100)
            print(f"== {script}  {' '.join(f.name for f in files)}")
            print("=" * 100)
        code, _ = run(script, files, quiet)
        results.append((script, code))

    print()
    print("=" * 100)
    print("== combined summary")
    print("=" * 100)
    width = max(len(s) for s, _ in results)
    for script, code in results:
        print(f"  {script:{width}}  {'PASS' if code == 0 else 'FAIL'}")
    if not vocab:
        print("  note: no vocabulary file found, so every shacl:path was unjudgeable")
    if skipped:
        print(f"  note: {len(skipped)} file(s) skipped as neither shapes nor vocabulary")

    failed = [s for s, code in results if code != 0]
    print()
    if failed:
        print(f"FAIL: {len(failed)} of {len(results)} checks failed: {', '.join(failed)}")
        return 1
    print(f"OK: all {len(results)} checks passed")
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = [a for a in sys.argv[1:] if a.startswith("-")]
    if len(args) != 1:
        sys.exit(__doc__)
    if not Path(args[0]).is_dir():
        sys.exit(f"not a directory: {args[0]}")
    sys.exit(check(args[0], quiet="--quiet" in flags or "-q" in flags))
