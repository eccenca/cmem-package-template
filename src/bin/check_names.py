#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["rdflib"]
# ///
"""Check that the package's own attributes are named the way the vocabulary skill says.

An attribute - an owl:DatatypeProperty - is named as a noun for the value it holds, and
the name says its kind where a kind has a form of its own:

* no ``has``/``is``/``was`` prefix on an attribute that is not yes/no: ``title``, not
  ``hasTitle`` - the verb belongs to relations, so the name tells a reader which of the
  two a property is;
* a yes/no attribute (``xsd:boolean``) starts with ``is`` or ``has``: ``isSigned``;
* a date or a point in time (``xsd:date``, ``xsd:dateTime``, ``xsd:time``) ends in
  ``Date`` or ``Time``: ``acquisitionDate``, ``startTime``;
* a name ending in ``Count`` is an integer.

Only what a name's spelling decides is checked. Whether a name is a noun, and whether a
relation reads as a sentence from its domain to its range, stay with review.

Only the package's own properties are judged: those in a namespace the manifest registers
as a vocabulary graph, or every declared property where no manifest is found. A package
that mirrors a published vocabulary unchanged (FOAF, a W3C schema) keeps its publisher's
names and switches the check off with an empty ``.claude/no-naming-check`` in its project.

    check_names.py vocab.ttl [more.ttl ...]

Exits non-zero when a name breaks a rule.
"""

import json
import re
import sys
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

VERB = re.compile(r"^(has|is|was)[A-Z0-9]")
YES_NO = re.compile(r"^(is|has)[A-Z0-9]")
TEMPORAL = {XSD.date, XSD.dateTime, XSD.dateTimeStamp, XSD.time}
INTEGER = {XSD.integer, XSD.int, XSD.long, XSD.short, XSD.nonNegativeInteger,
           XSD.positiveInteger, XSD.unsignedInt, XSD.unsignedLong}


def local(term):
    """The name after the namespace."""
    return re.split(r"[/#:]", str(term))[-1]


def project_root(path):
    """The generated project a file lies in, or None."""
    for folder in (path.resolve().parent, *path.resolve().parents):
        if (folder / ".copier-answers.yml").is_file():
            return folder
    return None


def own_namespaces(path):
    """The vocabulary graph IRIs of the manifest beside or above the file, or None."""
    for folder in (path.resolve().parent, *path.resolve().parents):
        manifest = folder / "cpa-manifest.json"
        if manifest.is_file():
            files = json.loads(manifest.read_text()).get("files", [])
            return {f["graph_iri"] for f in files
                    if f.get("register_as_vocabulary") and f.get("graph_iri")}
        if (folder / ".copier-answers.yml").is_file():
            return None
    return None


def problems(prop, ranges):
    """Each rule the attribute's name breaks."""
    name = local(prop)
    found = []
    if XSD.boolean in ranges:
        if not YES_NO.match(name):
            found.append("a yes/no attribute starts with is or has, as isSigned does")
    elif VERB.match(name):
        found.append("an attribute is a noun - has/is/was belongs to relations "
                     f"({VERB.sub(lambda m: m.group(0)[-1].lower(), name)})")
    if ranges & TEMPORAL and not re.search(r"(Date|Time)$", name):
        found.append("a date or time ends in Date or Time, as acquisitionDate does")
    if name.endswith("Count") and ranges and not ranges & INTEGER:
        found.append("a name ending in Count is an integer")
    return found


def check(paths):
    root = project_root(paths[0])
    if root is not None and (root / ".claude" / "no-naming-check").exists():
        print("OK: .claude/no-naming-check - the names are the publisher's, not checked")
        return 0
    graph = Graph()
    for path in paths:
        graph.parse(path, format="turtle")
    namespaces = own_namespaces(paths[0])

    def own(prop):
        return namespaces is None or any(str(prop).startswith(ns) for ns in namespaces)

    attributes = sorted(p for p in set(graph.subjects(RDF.type, OWL.DatatypeProperty))
                        if isinstance(p, URIRef) and own(p))
    failures = []
    for prop in attributes:
        ranges = set(graph.objects(prop, RDFS.range))
        failures += [(prop, text) for text in problems(prop, ranges)]

    print(f"{len(attributes)} attribute(s) of the package judged")
    if failures:
        print()
        print(f"FAIL: {len(failures)} name(s) break the vocabulary skill's naming rules")
        for prop, text in failures:
            print(f"  !! {local(prop)}: {text}")
        return 1
    print("OK: every attribute's name follows the naming rules")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    absent = [p for p in sys.argv[1:] if not Path(p).exists()]
    if absent:
        sys.exit(f"no such file: {', '.join(absent)}")
    sys.exit(check([Path(p) for p in sys.argv[1:]]))
