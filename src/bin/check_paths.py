#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["rdflib"]
# ///
"""Check that every property shape's shacl:path is type-correct against the vocabulary.

A property shape on a node shape targeting class C reaches its values along shacl:path p,
forwards or — with shui:inversePath true — backwards. For the row to mean what it says, the
vocabulary has to agree:

* forwards, ``rdfs:domain`` of p must be C or one of C's superclasses;
* backwards, ``rdfs:range`` of p must be C or one of C's superclasses.

Getting this wrong does not produce an error. **It silently disables validation**: a path
that matches nothing leaves shacl:class, shacl:nodeKind and every cardinality with nothing
to check, so a wrong assertion on that row survives indefinitely. The same goes for the
blunter version of the mistake, ``shacl:path <urn:path>`` as a stand-in on a query-driven
row, which is reported here as a failure in its own right.

Where the property has no declared domain (forwards) or range (backwards) the claim cannot
be judged, so that is a warning rather than a failure — common and fine for the standard
annotation properties a catalog reuses.

A shape carrying ``shacl:maxCount 0`` is skipped: it asserts that the row is always empty —
"not applicable for this subclass" — so a path outside the target class's domain is the point
of the shape rather than a mistake.

Pass the shape catalog and the vocabulary; order does not matter, and any number of files is
accepted, since both are parsed into one graph.

    check_paths.py config-shapes.ttl config-vocab.ttl

Exits non-zero on a genuine mismatch or a placeholder path.
"""

import sys
from pathlib import Path

from rdflib import BNode, Graph, URIRef
from rdflib.namespace import RDFS, Namespace

SH = Namespace("http://www.w3.org/ns/shacl#")
SHUI = Namespace("https://vocab.eccenca.com/shui/")

# Local names that mark a path as a stand-in rather than a real property, in any namespace.
PLACEHOLDER_NAMES = {"path", "todo", "tbd", "placeholder", "none", "unknown"}


def local(term):
    """Readable short name for an IRI, without needing to know the namespace."""
    text = str(term)
    for sep in ("#", "/", ":"):
        head, found, tail = text.rpartition(sep)
        if found and tail:
            return tail
    return text


def is_placeholder_path(path):
    """A shacl:path that names no real property — <urn:path> and friends."""
    if not isinstance(path, URIRef):
        return False
    text = str(path)
    if text.startswith("urn:") or text.startswith("tag:"):
        return True
    return local(path).lower() in PLACEHOLDER_NAMES


def ancestors(graph, cls):
    """cls plus every rdfs:subClassOf ancestor, transitively."""
    seen = set()
    todo = [cls]
    while todo:
        current = todo.pop()
        if current in seen:
            continue
        seen.add(current)
        todo.extend(graph.objects(current, RDFS.subClassOf))
    return seen


def check(paths):
    graph = Graph()
    for path in paths:
        graph.parse(path, format="turtle")

    rows = []
    for node_shape in sorted(graph.subjects(SH.targetClass, None), key=str):
        for target in graph.objects(node_shape, SH.targetClass):
            family = ancestors(graph, target)
            for shape in sorted(graph.objects(node_shape, SH.property), key=str):
                path = next(graph.objects(shape, SH.path), None)
                inverse = next(graph.objects(shape, SHUI.inversePath), None)
                inverse = inverse is not None and bool(inverse)
                driven = next(graph.objects(shape, SHUI.valueQuery), None) is not None
                max_count = next(graph.objects(shape, SH.maxCount), None)
                forbids = max_count is not None and int(max_count) == 0
                rows.append(judge(graph, target, family, node_shape, shape,
                                  path, inverse, driven, forbids))

    report(rows)
    failures = [r for r in rows if r["verdict"] == "FAIL"]
    warnings = [r for r in rows if r["verdict"] == "WARN"]

    print()
    print(f"{len(rows)} property shape/node shape pairing(s), "
          f"{sum(1 for r in rows if r['driven'])} of them query-driven")
    print(f"  {sum(1 for r in rows if r['verdict'] == 'OK'):3} type-correct")
    print(f"  {sum(1 for r in rows if r['verdict'] == 'n/a'):3} asserting absence "
          f"(shacl:maxCount 0)")
    print(f"  {len(warnings):3} unjudgeable (no domain/range declared)")
    print(f"  {len(failures):3} mismatched")

    if failures:
        print()
        print(f"FAIL: {len(failures)} path(s) not type-correct")
        for row in failures:
            print(f"  !! {local(row['target'])} / {local(row['shape'])}")
            print(f"     path {local(row['path'])} {row['direction']}: {row['note']}")
        return 1
    print()
    print("OK: every shacl:path is a real property whose domain/range admits its target class")
    return 0


def judge(graph, target, family, node_shape, shape, path, inverse, driven, forbids):
    row = dict(target=target, node_shape=node_shape, shape=shape, path=path,
               direction="inverse" if inverse else "forward", driven=driven,
               verdict="OK", note="")

    if forbids:
        # shacl:maxCount 0 asserts the row is always empty — "not applicable for this
        # subclass". An out-of-domain path is then the point of the shape, not a mistake.
        row.update(verdict="n/a", note="shacl:maxCount 0 — asserts absence, domain not judged")
        return row
    if path is None:
        row.update(verdict="FAIL", note="no shacl:path at all", path=URIRef("urn:missing"))
        return row
    if isinstance(path, BNode):
        row.update(verdict="WARN",
                   note="blank-node path (sequence/alternative) — not judged; "
                        "Corporate Memory expects a plain property here")
        return row
    if is_placeholder_path(path):
        row.update(verdict="FAIL",
                   note="placeholder path — carries no semantics and disables validation")
        return row

    axiom = RDFS.range if inverse else RDFS.domain
    declared = set(graph.objects(path, axiom))
    if not declared:
        row.update(verdict="WARN",
                   note=f"no rdfs:{local(axiom)} declared — cannot be judged")
        return row
    if declared & family:
        return row

    row.update(verdict="FAIL",
               note=f"rdfs:{local(axiom)} is "
                    f"{', '.join(sorted(local(d) for d in declared))}, "
                    f"which is not {local(target)} nor a superclass of it "
                    f"({', '.join(sorted(local(f) for f in family))})")
    return row


def report(rows):
    if not rows:
        print("no node shape carries a shacl:targetClass — nothing to check")
        return
    tw = max([len(local(r["target"])) for r in rows] + [len("target class")])
    sw = max([len(local(r["shape"])) for r in rows] + [len("property shape")])
    pw = max([len(local(r["path"])) for r in rows] + [len("path")])
    print(f"{'target class':{tw}}  {'property shape':{sw}}  {'path':{pw}}  "
          f"{'dir':7} {'q':1} verdict")
    print("-" * (tw + sw + pw + 24))
    for row in sorted(rows, key=lambda r: (str(r["target"]), str(r["shape"]))):
        print(f"{local(row['target']):{tw}}  {local(row['shape']):{sw}}  "
              f"{local(row['path']):{pw}}  {row['direction']:7} "
              f"{'q' if row['driven'] else ' '} {row['verdict']}"
              + (f"  {row['note']}" if row["verdict"] != "OK" else ""))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    absent = [p for p in sys.argv[1:] if not Path(p).exists()]
    if absent:
        sys.exit(f"no such file: {', '.join(absent)}")
    sys.exit(check(sys.argv[1:]))
