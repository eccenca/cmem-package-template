#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["rdflib>=7"]
# ///
"""Generate one Business Knowledge Editor visualisation per competency question of a package.

  question_visualizations.py [--write | --check] <package-dir>

A competency question is a SPARQL query in `requirements/questions/<slug>.rq` (beside the package
directory) whose header comment states the question: `# question: Which suppliers ...?`. For each one
this writes a `shui:Visualization` into `graphs/competency-questions.ttl`, showing the part of the
vocabulary that answers it, drawn the way the BKE draws a model - classes and properties as boxes, the
arrows taken by the BKE from the vocabulary itself. A saved BKE visualisation is nothing but a named
`shui:Visualization` with one `shui:VizNodePlacement` (term IRI, x, y) per box, so the terms and their
positions are all this script decides:

- the terms are the classes the query states (`?x a <Class>`) and the properties it uses, plus each
  property's domain and range class, so every box is connected;
- the rules, in order (the vocabulary skill's "Competency questions, drawn" explains them): 0 no edge
  across the drawing - a relation within three columns of its class; 1 nothing crosses - faults()
  counts edges through boxes and labels, labels on boxes, edges leaving a box together, boxes on
  boxes; 2 hierarchies top-down, a hierarchy property on the line between parent and child, a walk
  within one class named instead of drawn; 3 the L - a relation box in its domain's row, its range
  class in the box's column, on the line where the two are aligned; 4 one bound parent straight
  above; 5 a parent centred over its bound children; 6 the question's first class top left; 7 the
  shortest edges. Attributes sit on their class's free side, left first, closer than any relation.
  layered() searches the class positions for the placement that keeps them best in this order,
  starting once from each class, and derives each relation box from its two classes;
- positions are fixed by the query, so the output only changes when a question or the vocabulary does.

The visualisation's context graph is the vocabulary the manifest registers that defines most of the
question's terms. The graph is labelled "<package name>: competency questions", the catalog the BKE's
Visualization catalog lists the drawings under. It also carries the "Competency questions" row on
Corporate Memory's class forms (CLASS_FORM_ROW): a class's page lists the questions whose drawing contains
it, each linked to the drawing in the BKE - so the graph is imported into the global shape catalog.
--write also declares the graph in cpa-manifest.json, imported into the shape catalog, when it is not; --check
writes nothing and exits 1 when the graph is missing, stale, undeclared or not imported into the shape
catalog, a question names no
vocabulary term, or a drawing keeps a fault no placement avoids. A hand-made visualisation belongs in a
graph of its own: this script owns the file.
"""
import hashlib
import math
import json
import re
import sys
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph, URIRef, Variable
from rdflib.paths import InvPath, MulPath, SequencePath
from rdflib.plugins.sparql import prepareQuery

SHUI = "https://vocab.eccenca.com/shui/"
COL, ROW = 380, 60  # px from a class to its attribute (a box of 240 px plus an edge label) and per half row: the
# BKE's Bezier curves and their labels need that much room between boxes
QUESTIONS = Path("requirements") / "questions"
SHAPE_CATALOG = "https://vocab.eccenca.com/shacl/"
# The "Competency questions" row on Corporate Memory's class forms (Q212, Q220): a class's page lists the
# questions whose drawing contains it, each linked to the drawing in the BKE. Every package writes these
# triples unchanged, so an instance shows one row and one Overview group however many packages ship them;
# the graph is imported into the global shape catalog for Explore to find them. Change them here only.
CLASS_FORM_ROW = r'''<https://vocab.eccenca.com/shacl/OwlClassNodeShape> shacl:property shared-shapes:Class-competencyQuestions .
<https://vocab.eccenca.com/shacl/RdfsClassNodeShape> shacl:property shared-shapes:Class-competencyQuestions .

shared-shapes:Class-competencyQuestions
  a shacl:PropertyShape ;
  shacl:name "Competency questions"@en, "Kompetenzfragen"@de ;
  rdfs:label "Class: Competency questions property shape"@en ;
  shacl:description "The questions the model has to answer whose drawing contains this class; a link opens the drawing in the Business Knowledge Editor - read only."@en, "Die Fragen, die das Modell beantworten muss und deren Zeichnung diese Klasse enthält; ein Verweis öffnet die Zeichnung im Business Knowledge Editor – schreibgeschützt."@de ;
  shacl:path rdfs:value ;
  shacl:group shared-shapes:Overview ;
  shacl:order 10 ;
  shui:readOnly true ;
  shui:valueQuery shared-shapes:Class-competencyQuestionsQuery ;
  shui:valueQueryHideHeader true ;
  shui:valueQueryHideFooter true .

shared-shapes:Overview a shacl:PropertyGroup ;
  rdfs:label "Overview"@en, "Übersicht"@de ;
  rdfs:comment "What the resource is used for and where it appears - questions, drawings, summaries; last on the form, read only."@en, "Wofür die Ressource verwendet wird und wo sie vorkommt – Fragen, Zeichnungen, Zusammenfassungen; zuletzt im Formular, schreibgeschützt."@de ;
  shacl:order 900 .

shared-shapes:Class-competencyQuestionsQuery a shui:SparqlQuery, shui:SparqlOperation ;
  rdfs:label "Class -> Competency questions" ;
  dcterms:description "Lists the competency questions whose drawing contains the class, each as a link to the drawing in the Business Knowledge Editor." ;
  shui:queryText """# Lists the competency questions whose drawing contains the class, each linked to the drawing.
#
# ?resource: the question as a Markdown link to the drawing in the Business Knowledge Editor
#
# A drawing is a shui:Visualization written by bin/question_visualizations.py (its comment starts with
# "Competency question"); a placement names its term as a string, so the class is compared by string.
# The link is relative, so it works on every host; graph is the drawing's context graph (the
# vocabulary), catalogGraphIri the graph that holds the drawing.
# Note: ?resource must stay left-most: it is the value the row shows. No FROM - the row is shared by
# every package that ships it, so it lists the drawings of all installed packages.

PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX shui: <https://vocab.eccenca.com/shui/>
PREFIX sysont: <http://ns.ontowiki.net/SysOnt/>

SELECT DISTINCT ?resource
WHERE {
  GRAPH ?catalog {
    ?viz a shui:Visualization ;
      rdfs:label ?question ;
      rdfs:comment ?comment ;
      shui:hasContextGraph ?context ;
      shui:hasVizNodePlacement ?placement .
    ?placement shui:hasLocatedResource ?located .
  }
  FILTER(STR(?located) = STR(<{{shuiResource}}>))
  FILTER(STRSTARTS(STR(?comment), "Competency question"))
  BIND(CONCAT("/default/bke/viz?graph=", ENCODE_FOR_URI(STR(?context)),
              "&vizIri=", ENCODE_FOR_URI(STR(?viz)),
              "&catalogGraphIri=", ENCODE_FOR_URI(STR(?catalog))) AS ?href)
  BIND(STRDT(CONCAT("[", STR(?question), "](", ?href, ")"), sysont:Markdown) AS ?resource)
}
ORDER BY ?question
""" ;
  dcterms:created "2026-10-22T00:00:00"^^xsd:dateTime ;
  dcterms:modified "2026-10-22T00:00:00"^^xsd:dateTime .
'''
OUTPUT = "graphs/competency-questions.ttl"


def h(text: str, n: int) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:n]


def bgp_triples(node) -> list[tuple]:
    """All triple patterns of the query's algebra, in the order they are written."""
    found = []
    if getattr(node, "name", None) == "BGP":
        found += list(node.get("triples", []))
    if hasattr(node, "items"):
        for value in node.values():
            for child in value if isinstance(value, list) else [value]:
                if hasattr(child, "name"):
                    found += bgp_triples(child)
    return found


def steps(triples) -> list[tuple]:
    """(subject, property, object) steps with property paths split; an inverse step is turned round."""
    out, fresh = [], 0
    for s, p, o in triples:
        if isinstance(p, SequencePath):
            nodes = [s]
            for _ in p.args[:-1]:
                fresh += 1
                nodes.append(Variable(f"_path{fresh}"))
            nodes.append(o)
            for i, part in enumerate(p.args):
                out += steps([(nodes[i], part, nodes[i + 1])])
        elif isinstance(p, InvPath):
            out += steps([(o, p.arg, s)])
        elif isinstance(p, MulPath):  # p* / p+ / p?: drawn like one step of p
            out += steps([(s, p.path, o)])
        elif isinstance(p, URIRef):
            out.append((s, p, o))
    return out


SKOS = "http://www.w3.org/2004/02/skos/core#"
GIST = "https://w3id.org/semanticarts/ns/ontology/gist/"
# Properties whose object is the parent (drawn above) or the child (drawn below) in a hierarchy.
UP = {str(RDFS.subClassOf), SKOS + "broader", SKOS + "broaderTransitive", GIST + "isPartOf", GIST + "isMemberOf",
      GIST + "isCategorizedBy"}
DOWN = {SKOS + "narrower", SKOS + "narrowerTransitive", GIST + "hasPart", GIST + "hasMember"}


def hierarchy(prop: URIRef, vocab: Graph) -> str | None:
    """'up' when the property's object is the parent, 'down' when it is the child, None otherwise."""
    if str(prop) in UP:
        return "up"
    if str(prop) in DOWN:
        return "down"
    linked = {str(o) for o in vocab.objects(prop, RDFS.seeAlso)} | {str(o) for o in vocab.objects(prop, RDFS.subPropertyOf)}
    if linked & UP:
        return "up"
    if linked & DOWN:
        return "down"
    if (prop, RDF.type, OWL.TransitiveProperty) in vocab:
        return "up"  # a transitive relation in a vocabulary is a part-of or broader-than: its object is the whole
    return None


def written_at(query: str, term: URIRef) -> int:
    """Where the query text first names a term - full IRI or prefixed name; rdflib reorders patterns."""
    spots = [query.find(f"<{term}>")]
    for prefix, ns in re.findall(r"PREFIX\s+([\w-]*):\s*<([^>]*)>", query, re.I):
        if str(term).startswith(ns):
            local = str(term)[len(ns):]
            spots += [m.start() for m in re.finditer(rf"(?<![\w:]){re.escape(prefix)}:{re.escape(local)}(?![\w-])", query)]
    spots = [i for i in spots if i >= 0]
    return min(spots) if spots else len(query)


def model(query: str, vocab: Graph):
    """What a question draws: classes, relations (source, property, range class), hierarchy relations
    (parent, property, child), subclass links between drawn classes, each class's attributes, notes."""
    algebra = prepareQuery(query).algebra

    def first_iri(path):
        while isinstance(path, (SequencePath, InvPath)):
            path = path.args[0] if isinstance(path, SequencePath) else path.arg
        return path if isinstance(path, URIRef) else None

    patterns = bgp_triples(algebra)
    ordered = sorted(patterns, key=lambda t: (written_at(query, first_iri(t[1])) if first_iri(t[1]) is not None else len(query),
                                              patterns.index(t)))
    all_steps = steps(ordered)
    typed = {s: o for s, p, o in all_steps if p == RDF.type and isinstance(o, URIRef)}
    datatype = set(vocab.subjects(RDF.type, OWL.DatatypeProperty))

    def declared(prop, end):
        found = [c for c in vocab.objects(prop, end) if isinstance(c, URIRef)]
        return found[0] if len(found) == 1 else None

    def cls(node, prop, end):
        if isinstance(node, URIRef):
            return node
        return typed.get(node) or declared(prop, end)

    def path_up(sub, sup):
        """The superclasses from sub up to sup, nearest first; None when sub is no subclass of sup."""
        paths = [[sub]]
        while paths:
            path = paths.pop(0)
            for nxt in vocab.objects(path[-1], RDFS.subClassOf):
                if nxt == sup:
                    return path[1:] + [nxt]
                if isinstance(nxt, URIRef) and nxt not in path and len(path) < 8:
                    paths.append(path + [nxt])
        return None

    def label_of(term):
        labels = [str(l) for l in vocab.objects(term, RDFS.label) if getattr(l, "language", None) in ("en", None)]
        return labels[0] if labels else str(term).rsplit("/", 1)[-1].rsplit("#", 1)[-1]

    classes: list = []
    subs: list = []  # (superclass, subclass), direct
    rels: list = []  # (source class, property, range class)
    hrels: list = []  # (parent, property, child)
    attrs: dict = {}
    notes: list = []

    def add(c):
        if c is not None and c not in classes:
            classes.append(c)

    def link(sub, sup):
        """sub and every level up to sup drawn, each direct subclass link once."""
        chain = path_up(sub, sup) or []
        add(sub)
        below = sub
        for c in chain:
            add(c)
            if (c, below) not in subs:
                subs.append((c, below))
            below = c

    def lifted(c, decl):
        """A property declared on a superclass of the class the query names leaves from that superclass."""
        if c is not None and decl is not None and c != decl and path_up(c, decl) is not None:
            link(c, decl)
            return decl
        return c if c is not None else decl

    for s, p, o in all_steps:
        if p == RDF.type:
            if isinstance(o, URIRef):
                add(o)
            continue
        s_cls = cls(s, p, RDFS.domain)
        if p in datatype:
            owner = lifted(s_cls, declared(p, RDFS.domain))
            if owner is not None:
                add(owner)
                if p not in attrs.setdefault(owner, []):
                    attrs[owner].append(p)
            continue
        o_cls = cls(o, p, RDFS.range)
        direction = hierarchy(p, vocab)
        if direction is not None:
            s_cls = lifted(s_cls, declared(p, RDFS.domain))
            o_cls = lifted(o_cls, declared(p, RDFS.range))
            parent, child = (o_cls, s_cls) if direction == "up" else (s_cls, o_cls)
            if parent is None or child is None or parent == child:
                of = parent or child
                what = f"the {label_of(of)} hierarchy" if of is not None else "a hierarchy"
                note = f"also walks {what} ({p.n3(vocab.namespace_manager)})"
                if note not in notes:
                    notes.append(note)
                continue
            add(parent), add(child)
            if all(h[1] != p for h in hrels):
                hrels.append((parent, p, child))
            continue
        src = lifted(s_cls, declared(p, RDFS.domain))
        tgt = lifted(o_cls, declared(p, RDFS.range))
        add(src), add(tgt)
        if all(r[1] != p for r in rels) and (src is not None or tgt is not None):
            rels.append((src, p, tgt))
    for c in list(classes):  # drawn classes related through the hierarchy: every level between them
        for a in list(classes):
            if a != c and path_up(c, a) is not None:
                link(c, a)
    return classes, subs, rels, hrels, attrs, notes


SX = 570  # px per placement column: a box (240), a relation's domain edge (330, Q203) - classes and relations sit on it
W, H = 240, 36  # a BKE box
LW, LH = 118, 26  # the label the BKE puts in the middle of every edge


def drawn_edges(terms, vocab: Graph) -> list[tuple]:
    """The edges the BKE draws between placed terms: domain, range, subClassOf."""
    return [(t, o) for t in terms for pred in (RDFS.domain, RDFS.range, RDFS.subClassOf)
            for o in vocab.objects(t, pred) if o in terms and o != t]


def _seg_rect(x1, y1, x2, y2, l, t, r, b) -> bool:
    """Whether the segment passes through the open rectangle (Liang-Barsky)."""
    dx, dy = x2 - x1, y2 - y1
    lo, hi = 0.0, 1.0
    for p, q in ((-dx, x1 - l), (dx, r - x1), (-dy, y1 - t), (dy, b - y1)):
        if p == 0:
            if q <= 0:
                return False
        else:
            u = q / p
            if p < 0:
                lo = max(lo, u)
            else:
                hi = min(hi, u)
            if lo >= hi:
                return False
    return True


def _cross(p1, p2, p3, p4) -> bool:
    d = lambda a, b, c: (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return d(p3, p4, p1) * d(p3, p4, p2) < 0 and d(p1, p2, p3) * d(p1, p2, p4) < 0


def faults(pos: dict, edges: list, limit: float = float("inf")) -> list[str]:
    """Rule 1 on a drawing: an edge through a box or a label, a label on a box or a label, two edges
    crossing, a box on a box. Each curve is taken as its chord; stops after `limit` findings."""
    short = lambda t: str(t).rsplit("/", 1)[-1].rsplit("#", 1)[-1]
    centre = {t: (x + W / 2, y + H / 2) for t, (x, y) in pos.items()}
    boxes = list(pos.items())
    labels = [((a, b), ((centre[a][0] + centre[b][0]) / 2, (centre[a][1] + centre[b][1]) / 2)) for a, b in edges]
    found = []

    def add(text):
        found.append(text)
        return len(found) >= limit

    for i, (s, (sx, sy)) in enumerate(boxes):
        for t, (tx, ty) in boxes[i + 1:]:
            if abs(sx - tx) < W - 4 and abs(sy - ty) < H + 4:
                if add(f"{short(s)} on {short(t)}"):
                    return found
    for a, b in edges:
        (x1, y1), (x2, y2) = centre[a], centre[b]
        for t, (bx, by) in boxes:
            if t not in (a, b) and _seg_rect(x1, y1, x2, y2, bx + 4, by + 2, bx + W - 4, by + H - 2):
                if add(f"{short(a)} -> {short(b)} passes {short(t)}"):
                    return found
    for (a, b), (lx, ly) in labels:
        for t, (bx, by) in boxes:
            if abs(lx - (bx + W / 2)) < (LW + W) / 2 - 4 and abs(ly - (by + H / 2)) < (LH + H) / 2 - 2:
                if add(f"label of {short(a)} -> {short(b)} on {short(t)}"):
                    return found
    for i, ((a, b), (lx, ly)) in enumerate(labels):
        for (c, d), (mx, my) in labels[i + 1:]:
            if abs(lx - mx) < LW - 4 and abs(ly - my) < LH - 2:
                if add(f"label of {short(a)} -> {short(b)} on label of {short(c)} -> {short(d)}"):
                    return found
    for a, b in edges:
        (x1, y1), (x2, y2) = centre[a], centre[b]
        for (c, d), (lx, ly) in labels:
            if {a, b} != {c, d} and _seg_rect(x1, y1, x2, y2, lx - LW / 2 + 4, ly - LH / 2 + 2, lx + LW / 2 - 4, ly + LH / 2 - 2):
                if add(f"{short(a)} -> {short(b)} passes the label of {short(c)} -> {short(d)}"):
                    return found
    for i, (a, b) in enumerate(edges):
        for c, d in edges[i + 1:]:
            shared = {a, b} & {c, d}
            if len(shared) == 1:  # two edges leaving one box almost together read as one
                o = shared.pop()
                u, v = (b if a == o else a), (d if c == o else c)
                ang = lambda q: math.atan2(centre[q][1] - centre[o][1], centre[q][0] - centre[o][0])
                diff = abs((ang(u) - ang(v) + math.pi) % (2 * math.pi) - math.pi)
                if diff < math.radians(4):
                    if add(f"{short(a)} -> {short(b)} runs along {short(c)} -> {short(d)}"):
                        return found
            if not {a, b} & {c, d} and _cross(centre[a], centre[b], centre[c], centre[d]):
                if add(f"{short(a)} -> {short(b)} crosses {short(c)} -> {short(d)}"):
                    return found
    return found


def crossings(placements, vocab: Graph) -> list[str]:
    """Rule 1 faults of a finished drawing, its edges taken from the vocabulary as the BKE takes them."""
    pos = {t: (x, y) for t, x, y in placements}
    return faults(pos, drawn_edges(pos, vocab))


def gap(a, b) -> float:
    """The visible length of an edge between two boxes placed at a and b (top left corners)."""
    gx, gy = max(0.0, abs(a[0] - b[0]) - W), max(0.0, abs(a[1] - b[1]) - H)
    return (gx * gx + gy * gy) ** 0.5


def layered(query: str, vocab: Graph):
    """The drawing (Q211): the classes searched on a grid of SX x ROW for the placement that keeps the
    rules best in their order; each relation box derived from its two classes - on the line where they
    are aligned, at the corner of the L otherwise (Q210); attributes on their class's free side (Q202).
    Returns (term, x, y) in BKE units, the notes and warnings."""
    classes, subs, rels, hrels, attrs, notes = model(query, vocab)
    hier = {p for _, p, _ in hrels}
    rels = [(s, p, t) for s, p, t in rels if p not in hier]
    bound = {}  # Q197: one bound parent per class - the hierarchy the question asks about first
    for parent, p, child in hrels:
        bound.setdefault(child, (parent, p))
    for sup, sub in subs:
        bound.setdefault(sub, (sup, None))
    kids_of = {}
    for child, (parent, _) in bound.items():
        kids_of.setdefault(parent, []).append(child)
    has_parent = set(bound)
    bundle = {}  # relations between the same two classes, stacked across their line
    for s, p, t in rels:
        bundle.setdefault(frozenset((s, t)), []).append(p)
    attr_of = {a: c for c in attrs for a in attrs[c]}
    terms = set(classes) | {p for _, p, _ in rels} | hier | set(attr_of)
    edges = drawn_edges(terms, vocab)
    start = classes[0] if classes else None
    links = [(s, p, t) for s, p, t in rels] + [(child, p, parent) for parent, p, child in hrels]

    def sign(v):
        return (v > 0) - (v < 0)

    def candidates(s, p, t, g):
        """Cells for a relation box, preferred first."""
        if s is None or t is None:
            c = g[s if s is not None else t]
            return [(c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 4), (c[0], c[1] - 4)]
        (dx, dy), (rx, ry) = g[s], g[t]
        out = []
        if p in hier:
            if dx == rx:
                out.append((dx, (dy + ry) // 2))
            out += [(rx, dy), (dx, ry)]
        elif dy == ry and abs(rx - dx) >= 2:
            mid = dx + sign(rx - dx) * (abs(rx - dx) // 2)
            out += [(mid, dy + o) for o in (0, -1, 1, -2, 2)]
        elif dx == rx and abs(ry - dy) >= 4:
            out.append((dx, (dy + ry) // 2))
        if rx != dx:
            out.append((rx, dy))  # the corner of the L: in the domain's row, the range class below or above
        side = sign(rx - dx) or 1
        out += [(dx + side, dy), (dx - side, dy), (dx + 2 * side, dy), (dx + side, dy + 2), (dx + side, dy - 2)]
        return out

    def boxes(g, choice):
        """Each relation box on its first free candidate cell (or the one `choice` picks)."""
        taken = {(x, y + o) for x, y in g.values() for o in (-1, 0, 1)}
        cells = {}
        for s, p, t in links:
            cands = [c for c in candidates(s, p, t, g) if c not in taken]
            if not cands:
                cands = candidates(s, p, t, g)
            cell = cands[min(choice.get(p, 0), len(cands) - 1)]
            cells[p] = cell
            taken |= {(cell[0], cell[1] + o) for o in (-1, 0, 1)} if p not in sum(bundle.values(), []) else {cell}
        return cells

    def place(g, cells):
        """Grid cells -> BKE positions, the attributes added on their class's free side (Q202)."""
        grid = {**g, **cells}
        pos = {n: (gx * SX, gy * ROW) for n, (gx, gy) in grid.items()}
        for c, its in attrs.items():
            if c not in pos:
                continue
            x, y = pos[c]
            used = set()
            for a, b in edges:
                if c in (a, b) and a not in attr_of and b not in attr_of:
                    ox, oy = pos[b if a == c else a]
                    used.add(("left" if ox < x else "right") if abs(oy - y) < 90 else ("above" if oy < y else "below"))
            free = [s for s in ("left", "below", "right", "above") if s not in used and (s != "above" or c not in has_parent)]
            side = free[0] if free else "left"
            n = len(its)
            for i, a in enumerate(its):
                pos[a] = {"left": (x - COL, y + i * ROW), "right": (x + COL, y + i * ROW),
                          "below": (x + round((i - (n - 1) / 2) * COL), y + 2 * ROW),
                          "above": (x + round((i - (n - 1) / 2) * COL), y - 2 * ROW)}[side]
        return pos

    def on_line(b, d, r):
        """Q210: the box on the line between two aligned classes, or at the corner of the L."""
        (bx, by), (dx, dy), (rx, ry) = b, d, r
        if dy == ry and min(dx, rx) < bx < max(dx, rx) and abs(by - dy) <= 2:
            return True
        if dx == rx and bx == dx and min(dy, ry) < by < max(dy, ry):
            return True
        return by == dy and bx == rx and bx != dx

    def cost(g, choice, best=None):
        """The rules of Q211 as a tuple, compared in order; None as soon as it cannot beat `best`."""
        out = []

        def worse(value):
            out.append(value)
            return best is not None and tuple(out) > tuple(best[:len(out)])

        cells = boxes(g, choice)
        grid = {**g, **cells}
        # 0 range (Q198): a box at most three columns from its domain, its range class one column beside it
        # - and no edge longer than that, across or down: an edge across the whole drawing reads as badly as a crossing
        far = sum(1 for s, p, t in rels if s is not None and abs(grid[p][0] - g[s][0]) * SX > 3 * COL)
        far += sum(1 for s, p, t in rels if t is not None and abs(grid[p][0] - g[t][0]) > 1)
        far += sum(1 for a, b in edges if a in grid and b in grid and
                   (abs(grid[a][0] - grid[b][0]) * SX > 3 * COL or abs(grid[a][1] - grid[b][1]) > 8))
        if worse(far):
            return None
        pos = place(g, cells)
        within = best is not None and out[0] == best[0]
        found = faults(pos, edges, best[1] + 1 if within else float("inf"))
        for c, its in attrs.items():  # Q203: an attribute's edge shorter than every relation edge of its class
            if c in pos and its:
                rel = [gap(pos[c], pos[p]) for s, p, t in links if c in (s, t)]
                if rel and min(rel) <= max(gap(pos[c], pos[a]) for a in its):
                    found.append(f"an attribute of {c} as far from it as a relation")
        if worse(len(found)):
            return None
        # 2 hierarchy top-down
        upside = sum(1 for sup, sub in subs if g[sup][1] >= g[sub][1])
        upside += sum(1 for parent, p, child in hrels if not g[parent][1] < g[child][1])
        if worse(upside):
            return None
        # 3 the L (Q210)
        bent = sum(1 for s, p, t in links if s is not None and t is not None and not on_line(grid[p], g[s], g[t]))
        if worse(bent):
            return None
        # 4 one bound parent straight above (Q197), 5 centred over several bound children
        loose = sum(abs(g[parent][0] - g[child][0]) for child, (parent, _) in bound.items() if len(kids_of[parent]) == 1)
        if worse(loose):
            return None
        off = sum(abs(g[parent][0] - sum(g[k][0] for k in kids) / len(kids)) for parent, kids in kids_of.items() if len(kids) > 1)
        if worse(off):
            return None
        # 6 the starting class top left (Q206), 7 the shortest edges
        top, left = min(y for _, y in grid.values()), min(x for x, _ in grid.values())
        if worse((g[start][1] - top, g[start][0] - left) if start else (0, 0)):
            return None
        out.append(round(sum(gap(pos[a], pos[b]) for a, b in edges)))
        return tuple(out)

    # first drawings the way the user draws one: from the starting class, each relation beside its
    # domain with its range class below the box (or, for a bundle, beside it), each superclass above
    def first(root, across):
        g, taken = {}, set()

        def put(n, cell):
            x, y = cell
            while (x, y) in taken:
                x += 1
            g[n] = (x, y)
            taken.update({(x, y), (x + 1, y)})

        todo = [root] + [c for c in classes if c != root]
        while todo:
            c = todo.pop(0)
            if c not in g:
                put(c, (0, 0) if not g else (max(x for x, _ in g.values()) + 2, 0))
            cx, cy = g[c]
            for sup, sub in subs:
                if sub == c and sup not in g:
                    put(sup, (cx, cy - 4))
                if sup == c and sub not in g:
                    put(sub, (cx, cy + 4))
            for parent, p, child in hrels:
                if child == c and parent not in g:
                    put(parent, (cx, cy - 8))
                if parent == c and child not in g:
                    put(child, (cx, cy + 8))
            for s, p, t in rels:
                if s == c and t is not None and t not in g:
                    put(t, (cx + 2, cy) if across or len(bundle[frozenset((s, t))]) > 1 else (cx + 1, cy + 4))
                if t == c and s is not None and s not in g:
                    put(s, (cx - 1, cy - 4))
            todo.sort(key=lambda n: n not in g)
        return g

    def improve(g, choice, best):
        for _ in range(12):
            improved = False
            for n in classes:  # one class at a time
                for dx in range(-4, 5):
                    for dy in range(-12, 13, 2):
                        if dx == dy == 0:
                            continue
                        trial = dict(g)
                        trial[n] = (g[n][0] + dx, g[n][1] + dy)
                        if len(set(trial.values())) < len(trial):
                            continue
                        c = cost(trial, choice, best)
                        if c is not None and c < best:
                            best, g, improved = c, trial, True
            for i, a in enumerate(classes):  # two classes swapped
                for b in classes[i + 1:]:
                    trial = dict(g)
                    trial[a], trial[b] = g[b], g[a]
                    c = cost(trial, choice, best)
                    if c is not None and c < best:
                        best, g, improved = c, trial, True
            for s, p, t in links:  # a relation box on another of its cells
                for k in range(8):
                    if k == choice.get(p, 0):
                        continue
                    trial = {**choice, p: k}
                    c = cost(g, trial, best)
                    if c is not None and c < best:
                        best, choice, improved = c, trial, True
            if not improved:
                break
        return best, g, choice

    # every class as the root of a first drawing, the best one improved: one search gets caught where a
    # single move cannot leave a placement, a few starts rarely all do
    best = g = choice = None
    for root in classes:
        for across in (False, True):
            start_g = first(root, across)
            result = improve(start_g, {}, cost(start_g, {}))
            if best is None or result[0] < best:
                best, g, choice = result
    pos = place(g, boxes(g, choice))
    left = min(x for x, _ in pos.values())
    top = min(y for _, y in pos.values())
    order = classes + [p for _, p, _ in links] + [a for c in attrs for a in attrs[c] if a in pos]
    warnings = []
    if len(classes) > 10:
        warnings.append(f"{len(classes)} classes - the question may be two questions")
    return [(t, pos[t][0] - left, pos[t][1] - top) for t in order], notes, warnings


def planar_layout(query: str, vocab: Graph):
    """The drawing, its notes, the rule-1 faults no placement avoided (--check names them) and
    warnings about a question that may be two."""
    placements, notes, warnings = layered(query, vocab)
    return placements, notes, crossings(placements, vocab), warnings


def question_of(text: str, slug: str) -> str:
    m = re.search(r"^#\s*question:\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else slug


def main() -> None:
    args = sys.argv[1:]
    mode = "--check" if "--check" in args else "--write"
    dirs = [a for a in args if not a.startswith("--")]
    if len(dirs) != 1:
        sys.exit(__doc__)
    package = Path(dirs[0])
    questions_dir = package.resolve().parent / QUESTIONS
    manifest_path = package / "cpa-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    files = manifest.get("files", [])
    vocabularies = [f for f in files if f.get("file_type") == "graph" and f.get("register_as_vocabulary")]
    questions = sorted(questions_dir.glob("*.rq")) if questions_dir.is_dir() else []
    if not questions:
        print(f"no competency questions in {QUESTIONS}/ - nothing to visualise")
        return
    if not vocabularies:
        sys.exit("competency questions found, but the manifest registers no vocabulary to draw them from")
    vocab_graphs = {f["graph_iri"]: Graph().parse(package / f["file_path"]) for f in vocabularies}
    union = Graph()
    for g in vocab_graphs.values():
        union += g
    graph_iri = vocabularies[0]["graph_iri"].rstrip("/#") + "/competency-questions/"
    # the BKE's Visualization catalog shows this label as the drawings' catalog (Q219)
    name = (manifest.get("metadata") or {}).get("name") or manifest.get("package_id", "Package")
    name = name.replace("\\", "\\\\").replace('"', '\\"')
    problems = []
    out = [
        "# Generated by bin/question_visualizations.py from requirements/questions/ and the vocabulary - do not edit;",
        "# run `task visualizations`. One Business Knowledge Editor visualisation per competency question.",
        "",
        "@prefix dcterms: <http://purl.org/dc/terms/> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix shacl: <http://www.w3.org/ns/shacl#> .",
        "@prefix shared-shapes: <https://vocab.eccenca.com/shared-shapes/> .",
        f"@prefix shui: <{SHUI}> .",
        "@prefix void: <http://rdfs.org/ns/void#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
        f"<{graph_iri}> a void:Dataset ;",
        f'    rdfs:label "{name}: competency questions"@en ;',
        '    rdfs:comment "One Business Knowledge Editor visualisation per competency question of the package - the part of the model that answers it - and the row that lists them on a class\'s page."@en .',
        "",
    ]
    for path in questions:
        text = path.read_text()
        try:
            placements, notes, crossed, warnings = planar_layout(text, union)
            for c in crossed:
                problems.append(f"{path.name}: crossing left - {c}")
            for w in warnings:
                print(f"{path.name}: {w}")
        except Exception as exc:  # a query rdflib cannot parse
            problems.append(f"{path.name}: not parsed ({exc.__class__.__name__}: {str(exc)[:80]})")
            continue
        own = [t for t, _, _ in placements if any((t, None, None) in g for g in vocab_graphs.values())]
        if not own:
            problems.append(f"{path.name}: names no term of the package's vocabulary - no visualisation")
            continue
        context = max(vocab_graphs, key=lambda iri: sum(1 for t in own if (t, None, None) in vocab_graphs[iri]))
        viz = f"{graph_iri}viz/{h(path.stem, 16)}"
        names = [f"<{viz}/{h(str(t), 12)}>" for t, _, _ in placements]
        label = question_of(text, path.stem).replace("\\", "\\\\").replace('"', '\\"')
        out += [f"<{viz}> a shui:Visualization ;", f'    rdfs:label "{label}"@en ;',
                f'    rdfs:comment "Competency question {path.name}' + "".join(f"; {n}" for n in notes).replace('"', '\\"') + '"@en ;',
                f"    shui:hasContextGraph <{context}> ;",
                "    shui:hasVizNodePlacement " + ",\n        ".join(names) + " .", ""]
        for (t, x, y), n in zip(placements, names):
            out += [f"{n} a shui:VizNodePlacement ;", f'    shui:hasLocatedResource "{t}" ;',
                    f'    shui:hasXPosition "{x}"^^xsd:int ;', f'    shui:hasYPosition "{y}"^^xsd:int .', ""]
    out.append(CLASS_FORM_ROW)
    text = "\n".join(out)
    output = package / OUTPUT
    entry = next((f for f in files if f.get("file_path") == OUTPUT), None)
    imported = entry is not None and SHAPE_CATALOG in (entry.get("import_into") or [])
    if mode == "--check":
        if not output.exists() or output.read_text() != text:
            problems.append(f"{OUTPUT}: stale or missing - run `task visualizations`")
        if entry is None:
            problems.append(f"{OUTPUT}: not declared in cpa-manifest.json - run `task visualizations`")
        elif not imported:
            problems.append(f"{OUTPUT}: not imported into the shape catalog {SHAPE_CATALOG}, so no class page "
                            "lists its questions - run `task visualizations`")
    else:
        output.parent.mkdir(exist_ok=True)
        if not output.exists() or output.read_text() != text:
            output.write_text(text)
            print(f"wrote {OUTPUT} ({len(questions)} question(s))")
        if entry is None:
            files.append({"file_path": OUTPUT, "file_type": "graph", "graph_iri": graph_iri,
                          "import_into": [SHAPE_CATALOG], "register_as_vocabulary": False})
            print(f"declared {OUTPUT} in cpa-manifest.json")
        elif not imported:
            entry["import_into"] = (entry.get("import_into") or []) + [SHAPE_CATALOG]
            print(f"imported {OUTPUT} into the shape catalog in cpa-manifest.json")
        if entry is None or not imported:
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    for p in problems:
        print(p, file=sys.stderr)
    if problems and mode == "--check":
        sys.exit(1)


if __name__ == "__main__":
    main()
