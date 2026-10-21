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
- the layout follows the query: its triple patterns in the order written, left to right - subject class,
  property box, object class, next property (a property path `a/b` is two steps); a second pattern on
  the same variable starts a row below; a datatype property ends its row;
- a term is placed once; positions are fixed by the query, so the output only changes when a question
  or the vocabulary does.

The visualisation's context graph is the vocabulary the manifest registers that defines most of the
question's terms. --write also declares the graph in cpa-manifest.json when it is missing; --check
writes nothing and exits 1 when the graph is missing, stale or undeclared, or a question names no
vocabulary term. A hand-made visualisation belongs in a graph of its own: this script owns the file.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph, URIRef, Variable
from rdflib.paths import InvPath, SequencePath
from rdflib.plugins.sparql import prepareQuery

SHUI = "https://vocab.eccenca.com/shui/"
COL, ROW = 320, 110  # px between columns and rows
QUESTIONS = Path("requirements") / "questions"
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
        elif isinstance(p, URIRef):
            out.append((s, p, o))
    return out


def written_at(query: str, term: URIRef) -> int:
    """Where the query text first names a term - full IRI or prefixed name; rdflib reorders patterns."""
    spots = [query.find(f"<{term}>")]
    for prefix, ns in re.findall(r"PREFIX\s+([\w-]*):\s*<([^>]*)>", query, re.I):
        if str(term).startswith(ns):
            local = str(term)[len(ns):]
            spots += [m.start() for m in re.finditer(rf"(?<![\w:]){re.escape(prefix)}:{re.escape(local)}(?![\w-])", query)]
    spots = [i for i in spots if i >= 0]
    return min(spots) if spots else len(query)


def layout(query: str, vocab: Graph) -> list[tuple[URIRef, int, int]]:
    algebra = prepareQuery(query).algebra
    def first_iri(path):
        while isinstance(path, (SequencePath, InvPath)):
            path = path.args[0] if isinstance(path, SequencePath) else path.arg
        return path if isinstance(path, URIRef) else None

    patterns = bgp_triples(algebra)
    ordered = sorted(patterns, key=lambda t: (written_at(query, first_iri(t[1])) if first_iri(t[1]) is not None else len(query),
                                              patterns.index(t)))
    all_steps = steps(ordered)  # a path's steps stay together, in the order the query writes the paths
    typed = {s: o for s, p, o in all_steps if p == RDF.type and isinstance(o, URIRef)}
    datatype = set(vocab.subjects(RDF.type, OWL.DatatypeProperty))

    def cls(node, prop, end):
        if isinstance(node, URIRef):
            return node
        if node in typed:
            return typed[node]
        found = [c for c in vocab.objects(prop, end) if isinstance(c, URIRef)]
        return found[0] if len(found) == 1 else None

    placed: dict[URIRef, tuple[int, int]] = {}
    var_pos: dict = {}
    next_row = 0

    def put(term, col, row):
        if term is not None and term not in placed:
            placed[term] = (col, row)

    for s, p, o in all_steps:
        if p == RDF.type:
            continue
        if s in var_pos:
            col, row = var_pos[s]
            if var_pos.get(("used", s)):
                row = next_row  # a second pattern on the same subject: a row below
            var_pos[("used", s)] = True
        else:
            col, row = 0, next_row
            var_pos[s] = (col, row)
            var_pos[("used", s)] = True
            put(cls(s, p, RDFS.domain), col, row)
        put(p, col + 1, row)
        next_row = max(next_row, row + 1)
        if p in datatype or (o not in var_pos and not isinstance(o, (Variable, URIRef))):
            continue
        if o not in var_pos:
            var_pos[o] = (col + 2, row)
        put(cls(o, p, RDFS.range), *var_pos[o])
    for c in typed.values():  # a class the query types but never reaches through a property
        if c not in placed:
            put(c, 0, next_row)
            next_row += 1
    return [(t, x * COL, y * ROW) for t, (x, y) in placed.items()]


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
    problems = []
    out = [
        "# Generated by bin/question_visualizations.py from requirements/questions/ and the vocabulary - do not edit;",
        "# run `task visualizations`. One Business Knowledge Editor visualisation per competency question.",
        "",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        f"@prefix shui: <{SHUI}> .",
        "@prefix void: <http://rdfs.org/ns/void#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
        f"<{graph_iri}> a void:Dataset ;",
        '    rdfs:label "Competency questions: visualisations"@en ;',
        '    rdfs:comment "One Business Knowledge Editor visualisation per competency question of the package - the part of the model that answers it, in the order the question asks."@en .',
        "",
    ]
    for path in questions:
        text = path.read_text()
        try:
            placements = layout(text, union)
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
                f'    rdfs:comment "Competency question {path.name}"@en ;',
                f"    shui:hasContextGraph <{context}> ;",
                "    shui:hasVizNodePlacement " + ",\n        ".join(names) + " .", ""]
        for (t, x, y), n in zip(placements, names):
            out += [f"{n} a shui:VizNodePlacement ;", f'    shui:hasLocatedResource "{t}" ;',
                    f'    shui:hasXPosition "{x}"^^xsd:int ;', f'    shui:hasYPosition "{y}"^^xsd:int .', ""]
    text = "\n".join(out)
    output = package / OUTPUT
    declared = any(f.get("file_path") == OUTPUT for f in files)
    if mode == "--check":
        if not output.exists() or output.read_text() != text:
            problems.append(f"{OUTPUT}: stale or missing - run `task visualizations`")
        if not declared:
            problems.append(f"{OUTPUT}: not declared in cpa-manifest.json - run `task visualizations`")
    else:
        output.parent.mkdir(exist_ok=True)
        if not output.exists() or output.read_text() != text:
            output.write_text(text)
            print(f"wrote {OUTPUT} ({len(questions)} question(s))")
        if not declared:
            files.append({"file_path": OUTPUT, "file_type": "graph", "graph_iri": graph_iri,
                          "import_into": [], "register_as_vocabulary": False})
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
            print(f"declared {OUTPUT} in cpa-manifest.json")
    for p in problems:
        print(p, file=sys.stderr)
    if problems and mode == "--check":
        sys.exit(1)


if __name__ == "__main__":
    main()
