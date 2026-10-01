#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["rdflib"]
# ///
"""Report dangling shape, group and query references in a SHACL shape catalog.

A dangling sh:property / sh:node / sh:group / sh:sparql reference makes Corporate Memory's
SHACL service answer HTTP 500 for *every* graph, with nothing in the response naming the
cause. This is the cheap offline check that catches it before an install.

Only references into the catalog's own namespace are checked: a reference to a term defined
in an imported vocabulary is not dangling, it is just not in this file.

    check_dangling.py config-shapes.ttl [more.ttl ...]

Exits non-zero when something dangles.
"""

import sys
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import Namespace

SH = Namespace("http://www.w3.org/ns/shacl#")
SHUI = Namespace("https://vocab.eccenca.com/shui/")

CHECKED = [
    ("sh:property", SH.property),
    ("sh:node", SH.node),
    ("sh:group", SH.group),
    ("sh:sparql", SH.sparql),
    ("shui:valueQuery", SHUI.valueQuery),
    ("shui:uiQuery", SHUI.uiQuery),
    ("shui:QueryPlaceholder_valueQuery", SHUI.QueryPlaceholder_valueQuery),
    ("shui:QueryPlaceholder_usedInQuery", SHUI.QueryPlaceholder_usedInQuery),
]


def catalog_namespaces(graph):
    """Namespaces this file defines terms in — the ones a reference can dangle within."""
    prefixed = {str(ns) for _, ns in graph.namespaces()}
    defined = set()
    for subject in graph.subjects():
        if not isinstance(subject, URIRef):
            continue
        for ns in prefixed:
            if str(subject).startswith(ns) and ns.startswith("http"):
                defined.add(ns)
    # keep only the most specific namespaces actually carrying subjects
    return {ns for ns in defined if not any(o != ns and o.startswith(ns) for o in defined)}


def check(paths):
    graph = Graph()
    for path in paths:
        graph.parse(path, format="turtle")

    own = catalog_namespaces(graph)
    subjects = {str(s) for s in graph.subjects() if isinstance(s, URIRef)}

    dangling = 0
    for label, predicate in CHECKED:
        targets = [o for o in graph.objects(None, predicate) if isinstance(o, URIRef)]
        ours = [t for t in targets if any(str(t).startswith(ns) for ns in own)]
        missing = sorted({t for t in ours if str(t) not in subjects})
        print(f"{label:34} {len(targets):4} refs  {len(ours):4} into catalog  {len(missing)} dangling")
        for target in missing:
            dangling += 1
            for source in sorted(graph.subjects(predicate, target)):
                print(f"     !! {source} -> {target}")

    print()
    if dangling:
        print(f"FAIL: {dangling} dangling reference(s)")
    else:
        print("OK: no dangling references")
    return 1 if dangling else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    missing = [p for p in sys.argv[1:] if not Path(p).exists()]
    if missing:
        sys.exit(f"no such file: {', '.join(missing)}")
    sys.exit(check(sys.argv[1:]))
