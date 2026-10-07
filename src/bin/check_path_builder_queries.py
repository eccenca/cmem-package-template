#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["rdflib"]
# ///
"""Classify every path builder query row and check the subclass splits.

A property shape with shui:valueQuery takes its values from a path builder query. The shapes
skill (references/path-builder-queries.md) knows seven uses of one, and this check puts every such
row into one of them by what can be seen without data:

    1  subclass split           editable, several rows with the same path on one node shape
    2  enriched stored relation editable, forward, alone on its path
   2/3 stored or derived        read only and forward - which of the two needs a count over data
    4  back-link listing        shui:inversePath, read only
    5  read-only split          read only, several rows with the same path on one node shape
    6  computed link            a stand-in path rdfs:seeAlso on a read-only row     (anti-pattern)
    7  embedded widget          a stand-in path rdfs:value, or the header hidden     (anti-pattern)

For every subclass split (1) it then checks what keeps the rows and their queries in line. It
**fails** where

* a row lacks its path builder query (shui:valueQuery) or selectable resources query (shui:uiQuery);
* a query does not mention the row's shacl:path;
* the path builder query tests no class, or the row's shacl:class is that class itself rather than
  the range it belongs to - with the leaf as shacl:class every row would reject its siblings' values;
* the path builder query does not bind ?graph through FROM NAMED and a GRAPH block;
* the rows of the split do not share one shacl:group, or another row of the node shape sits in it;
* the vocabulary is among the files and a leaf class of the path's range has no row.

It **warns** where a split row allows inline creation (no shui:denyNewResources - a created resource
lands in the form's graph), a selectable resources query does not exclude the values a row already
holds (FILTER NOT EXISTS), and on every row of use case 6 or 7.

Pass the shape catalog and, if there is one, the vocabulary:

    check_path_builder_queries.py config-shapes.ttl config-vocab.ttl

Exits non-zero on a failure.
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS, Namespace

SH = Namespace("http://www.w3.org/ns/shacl#")
SHUI = Namespace("https://vocab.eccenca.com/shui/")
TRUE = {"true", "1"}

PREFIX_LINE = re.compile(r"^\s*PREFIX\s+([\w-]*):\s*<([^>]*)>", re.IGNORECASE | re.MULTILINE)
TYPE_TEST = re.compile(r"\s(?:a|rdf:type|<http://www\.w3\.org/1999/02/22-rdf-syntax-ns#type>)\s+(<[^>]+>|[\w-]*:[\w-]+)")


def local(term):
    text = str(term)
    return re.split(r"[#/:]", text.rstrip("/"))[-1]


def flag(graph, subject, predicate):
    value = graph.value(subject, predicate)
    return value is not None and str(value).lower() in TRUE


def query_text(graph, query):
    value = graph.value(query, SHUI.queryText) if query is not None else None
    return str(value) if value is not None else ""


def expand(token, text):
    """A class token from a query as a full IRI, using the query's own PREFIX lines."""
    if token.startswith("<"):
        return URIRef(token[1:-1])
    prefix, name = token.split(":", 1)
    namespaces = dict(PREFIX_LINE.findall(text))
    return URIRef(namespaces[prefix] + name) if prefix in namespaces else None


def mentions(text, iri):
    """Whether a query mentions an IRI, written in full or with a prefix."""
    if f"<{iri}>" in text:
        return True
    for prefix, namespace in PREFIX_LINE.findall(text):
        if str(iri).startswith(namespace) and re.search(rf"\b{re.escape(prefix)}:{re.escape(str(iri)[len(namespace):])}\b", text):
            return True
    return False


def use_case(graph, shape, siblings):
    path = graph.value(shape, SH.path)
    read_only = flag(graph, shape, SHUI.readOnly)
    if str(path).endswith(("#value", ":value")) or flag(graph, shape, SHUI.valueQueryHideHeader):
        return "7"
    if path == RDFS.seeAlso and read_only:
        return "6"
    if siblings > 1:
        return "5" if read_only else "1"
    if flag(graph, shape, SHUI.inversePath) and read_only:
        return "4"
    if read_only:
        return "2/3"
    return "2"


def leaves(graph, cls):
    """The classes below cls that have no subclass of their own."""
    below = set(graph.transitive_subjects(RDFS.subClassOf, cls)) - {cls}
    return {c for c in below if not any(s != c for s in graph.subjects(RDFS.subClassOf, c))}


def check(paths):
    graph = Graph()
    for path in paths:
        graph.parse(path, format="turtle")
    has_vocabulary = any(graph.triples((None, RDF.type, OWL.Class)))
    failures, warnings, rows = [], [], []

    for node in sorted(set(graph.subjects(RDF.type, SH.NodeShape))):
        shapes = list(graph.objects(node, SH.property))
        by_path = defaultdict(list)
        for shape in shapes:
            if graph.value(shape, SHUI.valueQuery) is not None:
                by_path[(graph.value(shape, SH.path), flag(graph, shape, SHUI.inversePath))].append(shape)
        for (path, inverse), group in sorted(by_path.items(), key=lambda kv: str(kv[0][0])):
            kinds = {use_case(graph, s, len(group)) for s in group}
            for shape in group:
                kind = use_case(graph, shape, len(group))
                rows.append((local(node), local(shape), local(path), kind))
                if kind in ("6", "7"):
                    warnings.append(f"{local(shape)}: use case {kind}, a catalogued anti-pattern - move it to a widget")
            if kinds != {"1"}:
                continue
            fail = lambda msg: failures.append(f"{local(node)} / {local(path)}: {msg}")
            tested = set()
            for shape in group:
                value_query = graph.value(shape, SHUI.valueQuery)
                choice_query = graph.value(shape, SHUI.uiQuery)
                vq, cq = query_text(graph, value_query), query_text(graph, choice_query)
                if not vq:
                    fail(f"{local(shape)} has no path builder query text")
                    continue
                if choice_query is None:
                    fail(f"{local(shape)} has no selectable resources query (shui:uiQuery)")
                for name, text in (("path builder", vq), ("selectable resources", cq)):
                    if text and not mentions(text, path):
                        fail(f"{local(shape)}: the {name} query does not mention the row's path {local(path)}")
                if "FROM NAMED" not in vq.upper() or not re.search(r"GRAPH\s+\?graph", vq):
                    fail(f"{local(shape)}: the path builder query does not bind ?graph through FROM NAMED and GRAPH ?graph")
                classes = [c for c in (expand(t, vq) for t in TYPE_TEST.findall(" " + vq)) if c is not None]
                if not classes:
                    fail(f"{local(shape)}: the path builder query tests no class - which leaf is this row?")
                    continue
                leaf = classes[-1]
                tested.add(leaf)
                row_class = graph.value(shape, SH["class"])
                if row_class == leaf:
                    fail(f"{local(shape)}: shacl:class is the leaf {local(leaf)}; use the range, or every row rejects its siblings' values")
                elif has_vocabulary and row_class is not None and row_class not in graph.transitive_objects(leaf, RDFS.subClassOf):
                    fail(f"{local(shape)}: shacl:class {local(row_class)} is no superclass of the leaf {local(leaf)}")
                if not flag(graph, shape, SHUI.denyNewResources):
                    warnings.append(f"{local(shape)}: allows inline creation; a created resource lands in the form's graph")
                if cq and "FILTER NOT EXISTS" not in cq.upper():
                    warnings.append(f"{local(shape)}: the selectable resources query offers values the row already holds")
            groups = {graph.value(s, SH.group) for s in group}
            if len(groups) != 1 or None in groups:
                fail("the rows of the split do not share one shacl:group")
            else:
                (split_group,) = groups
                others = [s for s in shapes if s not in group and graph.value(s, SH.group) == split_group]
                if others:
                    fail(f"other rows sit in the split's group: {', '.join(local(s) for s in others)}")
            if has_vocabulary:
                ranges = [r for r in graph.objects(path, RDFS.range)]
                for rng in ranges:
                    missing = leaves(graph, rng) - tested
                    for cls in sorted(missing):
                        fail(f"the leaf {local(cls)} of the range {local(rng)} has no row")

    print("node shape       row                                      path                 use case")
    print("-" * 100)
    for node, shape, path, kind in rows:
        print(f"{node[:16]:16} {shape[:40]:40} {path[:20]:20} {kind}")
    print()
    for message in warnings:
        print(f"  ~~ {message}")
    for message in failures:
        print(f"  !! {message}")
    if not has_vocabulary:
        print("note: no vocabulary among the files, so leaf coverage and superclasses were not judged")
    if failures:
        print(f"FAIL: {len(failures)} problem(s) in subclass splits")
        return 1
    print(f"OK: {len(rows)} path builder query row(s) classified, the subclass splits hold")
    return 0


if __name__ == "__main__":
    files = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not files:
        sys.exit(__doc__)
    missing = [f for f in files if not Path(f).is_file()]
    if missing:
        sys.exit(f"not a file: {', '.join(missing)}")
    sys.exit(check(files))
