#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["rdflib>=7"]
# ///
"""Assert that the question visualisations a generated package ships keep their layout rules.

Run from inside a generated package directory; `check:visualizations:case` does that.

A generated package has no competency questions, so `task visualizations:check`
passes over it whatever the generator does. This drives the *rendered*
package's own `bin/question_visualizations.py` over
`tests/fixtures/visualizations` instead - two small vocabularies and fifteen
questions covering every rule of the vocabulary skill's "Competency questions,
drawn", five of them arranged by hand by a reviewer:

* the committed drawings must still be what the generator writes, so a layout
  change shows up as a diff of the fixture to review, not as a surprise in a
  customer's Business Knowledge Editor (`--bless` rewrites them after review);
* the graph carries the shared "Competency questions" row on Corporate Memory's
  class forms and is imported into the shape catalog, so a class's page lists
  its questions;
* every drawing must keep the rules - no crossing, no edge longer than the range,
  hierarchies top-down, each relation box in the L or on the line, attributes on
  the free side and closer than any relation - and each hand arrangement the
  properties `arrangements.json` lists for it, box by box, so a rule that fixes
  one drawing by breaking another fails;
* three planted faults must be caught: a drawing edited by hand (drift), a box
  on an edge (the fault counter), and a fault no placement avoids (named by
  `--check`, not dropped).

Exits non-zero with a one-line reason on the first failure.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph, Namespace, URIRef

GENERATOR = Path("bin") / "question_visualizations.py"
FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "visualizations"
SHUI = Namespace("https://vocab.eccenca.com/shui/")
SH = Namespace("http://www.w3.org/ns/shacl#")
ROW = 60


def fail(message):
    print(f"check-visualizations: {message}", file=sys.stderr)
    sys.exit(1)


def run(mode, root):
    result = subprocess.run([str(GENERATOR.resolve()), mode, "package"], cwd=root, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def load_generator():
    spec = importlib.util.spec_from_file_location("question_visualizations", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def drawings(path):
    g = Graph().parse(path)
    for viz in g.subjects(RDF.type, SHUI.Visualization):
        yield str(g.value(viz, RDFS.label)), [
            (URIRef(str(g.value(p, SHUI.hasLocatedResource))), int(g.value(p, SHUI.hasXPosition)),
             int(g.value(p, SHUI.hasYPosition)))
            for p in g.objects(viz, SHUI.hasVizNodePlacement)]


def rule_breaks(placements, vocab, qv):
    """Each placement that breaks a rule of the vocabulary skill's "Competency questions, drawn"."""
    pos = {t: (x, y) for t, x, y in placements}
    short = lambda t: str(t).rsplit("/", 1)[-1].rsplit("#", 1)[-1]
    breaks = []
    edges = qv.drawn_edges(pos, vocab)
    datatype = {t for t in pos if (t, RDF.type, OWL.DatatypeProperty) in vocab}
    # range: no edge across the drawing
    for a, b in edges:
        if abs(pos[a][0] - pos[b][0]) > 3 * 380 or abs(pos[a][1] - pos[b][1]) > 8 * ROW:
            breaks.append(f"{short(a)} -> {short(b)} longer than the range")
    # hierarchy top-down: a superclass above its subclass, a parent above its child
    for sub in pos:
        for sup in vocab.objects(sub, RDFS.subClassOf):
            if sup in pos and pos[sup][1] >= pos[sub][1]:
                breaks.append(f"{short(sup)} not above its subclass {short(sub)}")
    for p in pos:
        direction = qv.hierarchy(p, vocab) if p not in datatype else None
        d, r = vocab.value(p, RDFS.domain), vocab.value(p, RDFS.range)
        if direction is not None and d in pos and r in pos:
            parent, child = (r, d) if direction == "up" else (d, r)
            between = pos[parent][0] == pos[p][0] == pos[child][0] and pos[parent][1] < pos[p][1] < pos[child][1]
            corner = pos[parent][1] < pos[child][1] and pos[p][1] in (pos[d][1], pos[r][1]) and \
                pos[p][0] in (pos[d][0], pos[r][0])
            if not (between or corner):  # on the line, or at the corner of the L where the bond gives way (Q197)
                breaks.append(f"{short(p)} neither on the line nor at the corner between {short(parent)} above and {short(child)}")
    # the L or the line: a relation box in its domain's row and its range class's column, or on the line
    for p in pos:
        if (p, RDF.type, OWL.ObjectProperty) not in vocab or qv.hierarchy(p, vocab) is not None:
            continue
        d, r = vocab.value(p, RDFS.domain), vocab.value(p, RDFS.range)
        if d not in pos or r not in pos:
            continue
        (bx, by), (dx, dy), (rx, ry) = pos[p], pos[d], pos[r]
        line = (dy == ry and min(dx, rx) < bx < max(dx, rx) and abs(by - dy) <= 2 * ROW) or \
            (dx == rx == bx and min(dy, ry) < by < max(dy, ry))
        corner = by == dy and bx == rx
        if not (line or corner):
            breaks.append(f"{short(p)} neither at the corner of the L nor on the line between {short(d)} and {short(r)}")
    # attributes: on the left unless an edge arrives there, and closer than every relation of their class
    for a in datatype:
        c = vocab.value(a, RDFS.domain)
        if c not in pos:
            continue
        arriving = [o for x, y in edges for o, k in ((x, y), (y, x)) if k == c and o not in datatype]
        left_used = any(pos[o][0] < pos[c][0] and abs(pos[o][1] - pos[c][1]) < 90 for o in arriving)
        if not (pos[a][0] < pos[c][0]) and not left_used:
            breaks.append(f"attribute {short(a)} not left of {short(c)}, whose left is free")
        rel = [qv.gap(pos[c], pos[o]) for o in arriving if (o, RDF.type, OWL.ObjectProperty) in vocab]
        if rel and min(rel) <= qv.gap(pos[c], pos[a]):
            breaks.append(f"attribute {short(a)} as far from {short(c)} as a relation")
    return breaks


def arrangement_breaks(placements, expected):
    """Each property of a hand arrangement the drawing does not have."""
    pos = {str(t).rsplit("/", 1)[-1]: (x, y) for t, x, y in placements}
    breaks = []
    for kind, *names in expected:
        missing = [n for n in [names[0]] + (names[1] if kind == "centred" else names[1:]) if n not in pos]
        if missing:
            breaks.append(f"{kind} {names}: {missing} not drawn")
            continue
        if kind == "above" and not pos[names[0]][1] < pos[names[1]][1]:
            breaks.append(f"{names[0]} not above {names[1]}")
        elif kind == "column" and pos[names[0]][0] != pos[names[1]][0]:
            breaks.append(f"{names[0]} not in the column of {names[1]}")
        elif kind == "row" and pos[names[0]][1] != pos[names[1]][1]:
            breaks.append(f"{names[0]} not in the row of {names[1]}")
        elif kind == "left" and not pos[names[0]][0] < pos[names[1]][0]:
            breaks.append(f"{names[0]} not left of {names[1]}")
        elif kind == "centred":
            xs = [pos[n][0] for n in names[1]]
            if abs(pos[names[0]][0] - sum(xs) / len(xs)) > 1:
                breaks.append(f"{names[0]} not centred over {', '.join(names[1])}")
        elif kind == "between":
            (bx, by), (ax, ay), (cx, cy) = pos[names[0]], pos[names[1]], pos[names[2]]
            row = ay == cy and min(ax, cx) < bx < max(ax, cx) and abs(by - ay) <= 2 * ROW
            col = ax == cx == bx and min(ay, cy) < by < max(ay, cy)
            if not (row or col):
                breaks.append(f"{names[0]} not on the line between {names[1]} and {names[2]}")
    return breaks


def main():
    if not GENERATOR.is_file():
        fail(f"{GENERATOR} does not exist - the template did not ship the generator")
    if not FIXTURE.is_dir():
        fail(f"fixture directory {FIXTURE} is missing")
    bless = "--bless" in sys.argv[1:]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "fixture"
        shutil.copytree(FIXTURE, root)
        if bless:
            code, output = run("--write", root)
            shutil.copy(root / "package" / "graphs" / "competency-questions.ttl",
                        FIXTURE / "package" / "graphs" / "competency-questions.ttl")
            shutil.copy(root / "package" / "cpa-manifest.json", FIXTURE / "package" / "cpa-manifest.json")
            print(f"blessed the fixture drawings - review the diff:\n{output}")
            return

        code, output = run("--check", root)
        if code != 0:
            fail(f"the fixture drawings differ from what the generator writes (review, then --bless):\n{output}")

        qv = load_generator()
        vocab = Graph()
        for path in sorted((root / "package" / "graphs").glob("vocab*.ttl")):
            vocab.parse(path)
        arrangements = json.loads((root / "arrangements.json").read_text())
        slugs = {qv.question_of((root / "requirements" / "questions" / f"{slug}.rq").read_text(), slug): slug
                 for slug in (p.stem for p in (root / "requirements" / "questions").glob("*.rq"))}
        count = 0
        for label, placements in drawings(root / "package" / "graphs" / "competency-questions.ttl"):
            count += 1
            crossed = qv.crossings(placements, vocab)
            if crossed:
                fail(f"{label}: crossing - {crossed[0]}")
            breaks = rule_breaks(placements, vocab, qv)
            breaks += arrangement_breaks(placements, arrangements.get(slugs.get(label), []))
            if breaks:
                fail(f"{label}: {breaks[0]}")
        # the class-form row ships with the drawings, and the graph is imported where Explore finds it
        drawn_graph = Graph().parse(root / "package" / "graphs" / "competency-questions.ttl")
        row = URIRef("https://vocab.eccenca.com/shared-shapes/Class-competencyQuestions")
        for form in ("OwlClassNodeShape", "RdfsClassNodeShape"):
            if (URIRef(f"https://vocab.eccenca.com/shacl/{form}"), SH.property, row) not in drawn_graph:
                fail(f"the competency-question row is not attached to {form}")
        entry = next(f for f in json.loads((root / "package" / "cpa-manifest.json").read_text())["files"]
                     if f["file_path"] == "graphs/competency-questions.ttl")
        if qv.SHAPE_CATALOG not in entry.get("import_into", []):
            fail("the drawings' graph is not imported into the shape catalog, so no class page lists its questions")
        questions = len(list((root / "requirements" / "questions").glob("*.rq")))
        if count != questions:
            fail(f"{count} drawing(s) for {questions} question(s)")

        # planted: a drawing edited by hand
        drawn = root / "package" / "graphs" / "competency-questions.ttl"
        original = drawn.read_text()
        edited = original.replace('shui:hasXPosition "0"^^xsd:int', 'shui:hasXPosition "40"^^xsd:int', 1)
        if edited == original:
            fail("the planted edit found no x position 0 in the fixture drawings")
        drawn.write_text(edited)
        code, output = run("--check", root)
        if code == 0:
            fail("a hand-edited drawing passed --check")
        drawn.write_text(original)

    # planted: a box on an edge must be counted
    product, has_supplier, supplier, agent = (URIRef(f"https://example.com/fixture/{n}")
                                              for n in ("Product", "hasSupplier", "Supplier", "Agent"))
    planted = [(product, 0, 0), (has_supplier, 380, 0), (supplier, 380, 240), (agent, 380, 120)]
    if not qv.crossings(planted, vocab):
        fail("the fault counter missed a box on the edge has supplier -> Supplier")

    # planted: a fault no placement avoids is returned, so --check names it
    qv.layered = lambda query, vocab: (planted, [], [])
    if not qv.planar_layout("", vocab)[2]:
        fail("a fault no placement avoids was dropped instead of reported")
    print(f"check-visualizations: {count} fixture drawings keep their rules, {len(arrangements) - 1} hand arrangements "
          f"their properties; 3 planted faults caught")


if __name__ == "__main__":
    main()
