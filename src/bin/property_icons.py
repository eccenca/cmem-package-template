#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["rdflib"]
# ///
"""Give the package's properties icons that say what they mean, embedded in the vocabulary.

    property_icons.py [--check] <project-dir>

The Business Knowledge Editor draws a property's foaf:depiction on its box, so a drawing of the
model shows what each relation and attribute is about instead of one built-in icon for all.

* A **relation** shows its kind and its direction: an arrow into a glyph of the shared set
  (``part-of``, ``located-in``, ``supplied-by``, ...), or - for ``range`` - the range class's own
  icon behind the arrow. Its colour is the range class's colour. A relation not mapped keeps
  Corporate Memory's built-in icon.
* An **attribute** shows its meaning and never an arrow (``email``, ``due-date``, ``quantity``,
  ...). Every attribute gets one: where the mapping names none, the kind of its value stands in,
  read from its declared range - ``text``, ``number``, ``date``, ``time``, ``year``, ``yes-no``,
  ``link``, ``location`` (and ``count`` for a name ending in Count). Its colour is the domain
  class's colour, so a class and its attributes read as one unit.

A colour is read off the class's own foaf:depiction; without one it is neutral grey.

The mapping is ``icons/property-icons.json`` in the project, owned by the package::

    {"relations": {"https://.../isPartOf": "part-of", "https://.../hasSupplier": "range"},
     "attributes": {"https://.../email": "email"}}

Without it the script does nothing. Glyphs are looked up in the project's own
``icons/glyphs/{relations,attributes}/<name>.svg`` first - a domain glyph a package draws itself
- then in the shared set beside this script. Every glyph must be drawing only (the element
allowlist of the countries package's flag check, no event handler, no reference outside the SVG),
or nothing is written.

Each icon goes into the property's block in the vocabulary file that declares it, as one line
``foaf:depiction <data:image/svg+xml;base64,...> ; # property-icons: <glyph>``; only lines with that
comment are written or replaced, and a property whose depiction was drawn by hand keeps it and
gets none from here. ``--check`` writes nothing
and exits 1 when an icon is missing, stale or not drawing only. Only the package's own properties
get icons: those in a namespace the manifest registers as a vocabulary.
"""

import base64
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

from rdflib import Graph, URIRef
from rdflib.namespace import FOAF, OWL, RDF, RDFS, XSD

HERE = Path(__file__).resolve().parent
SHARED = HERE / "glyphs"
MAPPING = Path("icons") / "property-icons.json"
GREY = "#1c2329"
ARROW = "M2 12 H8.6 M6.2 9.4 L8.8 12 L6.2 14.6"  # into the glyph on its right
MARK = "# property-icons:"
OWN = 'class="property-icon"'  # tells an icon this script wrote from one drawn by hand
SVG = "http://www.w3.org/2000/svg"
ALLOWED = {"svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "use",
           "defs", "clipPath", "mask", "linearGradient", "radialGradient", "stop", "marker",
           "title", "desc"}
GEO_WKT = URIRef("http://www.opengis.net/ont/geosparql#wktLiteral")
KINDS = [  # value kind of an attribute without a mapped glyph, by declared range
    ({XSD.boolean}, "yes-no"),
    ({XSD.date, XSD.dateTime, XSD.dateTimeStamp}, "date"),
    ({XSD.time}, "time"),
    ({XSD.gYear, XSD.gYearMonth}, "year"),
    ({XSD.anyURI}, "link"),
    ({GEO_WKT}, "location"),
    ({XSD.integer, XSD.int, XSD.long, XSD.short, XSD.nonNegativeInteger, XSD.positiveInteger,
      XSD.decimal, XSD.double, XSD.float}, "number"),
]

ET.register_namespace("", SVG)


def problems(svg):
    """Everything in an SVG that is not drawing: the countries package's flag check."""
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as error:
        return [f"not well-formed: {error}"]
    found = []
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag not in ALLOWED:
            found.append(f"element <{tag}>")
        for name, value in el.attrib.items():
            local = name.split("}")[-1]
            if local.lower().startswith("on"):
                found.append(f"event handler {local}")
            if local == "href" and not value.startswith("#"):
                found.append(f"reference {value[:40]}")
            for target in re.findall(r"url\(([^)]*)\)", value):
                if not target.strip("'\" ").startswith("#"):
                    found.append(f"external url in {local}")
    return found


def glyph(root, kind, name):
    """The glyph's SVG text from the project's own set, else the shared one; None if neither."""
    for base in (root / "icons" / "glyphs", SHARED):
        path = base / kind / f"{name}.svg"
        if path.is_file():
            return path.read_text()
    return None


def inner(svg):
    """The drawing inside an SVG's root element."""
    root = ET.fromstring(svg)
    return "".join(ET.tostring(child, encoding="unicode") for child in root)


def depiction_svg_of(value):
    """The SVG of an embedded depiction, or None for anything else."""
    text = str(value)
    if text.startswith("data:image/svg+xml;base64,"):
        return base64.b64decode(text.split(",", 1)[1]).decode()
    if text.startswith("data:image/svg+xml,"):
        return unquote(text.split(",", 1)[1])
    return None


def depiction_svg(graph, cls):
    """The SVG of a class's embedded foaf:depiction, or None."""
    for value in graph.objects(cls, FOAF.depiction):
        svg = depiction_svg_of(value)
        if svg is not None:
            return svg
    return None


def colour(graph, cls):
    """The first colour a class's icon is drawn in; neutral grey without one."""
    svg = depiction_svg(graph, cls) if cls is not None else None
    if svg:
        for value in re.findall(r'(?:fill|stroke)="(#[0-9a-fA-F]{3,6})"', svg):
            if value.lower() not in ("#fff", "#ffffff"):
                return value
    return GREY


def value_kind(prop, ranges):
    """The glyph standing in for an attribute's meaning: the kind of its value."""
    if str(prop).endswith("Count"):
        return "count"
    for types, name in KINDS:
        if ranges & types:
            if name == "date" and str(prop).endswith("Time"):
                return "time"
            return name
    return "text"


def recolour(svg, value):
    return svg.replace("currentColor", value)


def relation_icon(root, graph, prop, name):
    target = graph.value(prop, RDFS.range)
    paint = colour(graph, target)
    if name == "range":
        svg = depiction_svg(graph, target)
        if svg is None:
            raise ValueError(f"{prop}: 'range' needs an icon on its range class {target}")
        return (f'<svg xmlns="{SVG}" {OWN} viewBox="0 0 24 24"><path fill="none" stroke="{paint}" '
                f'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" d="{ARROW}"/>'
                f'<g transform="translate(9.6 5.4) scale(0.55)">{inner(svg)}</g></svg>')
    svg = glyph(root, "relations", name)
    if svg is None:
        raise ValueError(f"{prop}: no relation glyph '{name}'")
    arrow = (f'<path fill="none" stroke="{paint}" stroke-width="1.6" stroke-linecap="round" '
             f'stroke-linejoin="round" d="{ARROW}"/>')
    return f'<svg xmlns="{SVG}" {OWN} viewBox="0 0 24 24">{arrow}{inner(recolour(svg, paint))}</svg>'


def attribute_icon(root, graph, prop, name):
    svg = glyph(root, "attributes", name)
    if svg is None:
        raise ValueError(f"{prop}: no attribute glyph '{name}'")
    paint = colour(graph, graph.value(prop, RDFS.domain))
    return f'<svg xmlns="{SVG}" {OWN} viewBox="0 0 24 24">{inner(recolour(svg, paint))}</svg>'


def own_namespaces(root):
    namespaces = set()
    for manifest in root.glob("*/cpa-manifest.json"):
        for entry in json.loads(manifest.read_text()).get("files", []):
            if entry.get("register_as_vocabulary") and entry.get("graph_iri"):
                namespaces.add(entry["graph_iri"])
    return namespaces


def vocabulary_files(root):
    files = []
    for path in sorted(root.glob("*/**/*.ttl")):
        if "/." in str(path.relative_to(root)) or path.parts[len(root.parts)] in ("bin", "tests"):
            continue
        text = path.read_text()
        if "owl:ObjectProperty" in text or "owl:DatatypeProperty" in text or "#ObjectProperty>" in text:
            files.append(path)
    return files


def subject_tokens(text, prop):
    """The ways a property may open its block in a Turtle file: <IRI> and prefix:local."""
    tokens = [f"<{prop}>"]
    for prefix, namespace in re.findall(r"@prefix\s+([\w-]*):\s*<([^>]*)>", text):
        if str(prop).startswith(namespace) and re.fullmatch(r"[\w-]+", str(prop)[len(namespace):]):
            tokens.append(f"{prefix}:{str(prop)[len(namespace):]}")
    return tokens


def code(line):
    """A Turtle line without its trailing comment (good enough for block ends: no '#' in IRIs here)."""
    return re.sub(r'\s+#[^"<>]*$', "", line).rstrip()


def place(text, prop, uri, name):
    """The file with the property's icon line written or replaced; None if the block is not found."""
    lines = text.split("\n")
    tokens = subject_tokens(text, prop)
    start = next((i for i, line in enumerate(lines)
                  if any(line.startswith(t + " ") or line == t for t in tokens)), None)
    if start is None:
        return None
    end = next((i for i in range(start, len(lines)) if code(lines[i]).endswith(".")), None)
    if end is None or end == start and not code(lines[start]).endswith(";"):
        return None
    predicate = "foaf:depiction" if re.search(r"@prefix\s+foaf:\s*<http://xmlns.com/foaf/0.1/>", text) \
        else "<http://xmlns.com/foaf/0.1/depiction>"
    body = lines[start:end + 1]
    marked = [i for i, line in enumerate(body) if MARK in line]
    if marked:
        i = marked[0]
        last = code(body[i]).endswith(".")
        body[i] = f"  {predicate} <{uri}> {'.' if last else ';'} {MARK} {name}"
    else:
        after = next((i for i, line in enumerate(body) if "rdfs:isDefinedBy" in line), 0)
        if code(body[after]).endswith("."):
            body[after] = re.sub(r"\s*\.(\s*(#.*)?)$", r" ;\1", body[after], count=1)
            body.insert(after + 1, f"  {predicate} <{uri}> . {MARK} {name}")
        else:
            body.insert(after + 1, f"  {predicate} <{uri}> ; {MARK} {name}")
    return "\n".join(lines[:start] + body + lines[end + 1:])


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    check = "--check" in sys.argv[1:]
    if len(args) != 1:
        sys.exit(__doc__)
    root = Path(args[0]).resolve()
    for folder in (root, *root.parents):  # accept the package directory as well as the project
        if (folder / MAPPING).is_file() or (folder / ".copier-answers.yml").is_file():
            root = folder
            break
    if not (root / MAPPING).is_file():
        print(f"property icons: no {MAPPING} - nothing to do")
        return 0
    mapping = json.loads((root / MAPPING).read_text())
    files = vocabulary_files(root)
    graph = Graph()
    for path in files:
        graph.parse(path, format="turtle")
    namespaces = own_namespaces(root)

    def own(prop):
        return not namespaces or any(str(prop).startswith(ns) for ns in namespaces)

    def by_hand(prop):
        """A depiction this script did not write: it stays, and the property gets no second one."""
        return any(OWN not in (depiction_svg_of(value) or "") for value in graph.objects(prop, FOAF.depiction))

    wanted, failures = {}, []
    for iri, name in mapping.get("relations", {}).items():
        prop = URIRef(iri)
        if (prop, RDF.type, OWL.ObjectProperty) not in graph:
            failures.append(f"{iri}: no relation of the vocabulary")
        elif not own(prop):
            failures.append(f"{iri}: not a property of this package - its icon belongs to its owner")
        elif not by_hand(prop):
            try:
                wanted[prop] = (relation_icon(root, graph, prop, name), name)
            except ValueError as error:
                failures.append(str(error))
    attributes = mapping.get("attributes", {})
    for prop in sorted(set(graph.subjects(RDF.type, OWL.DatatypeProperty)), key=str):
        if not isinstance(prop, URIRef) or not own(prop) or by_hand(prop):
            continue
        name = attributes.get(str(prop)) or value_kind(prop, set(graph.objects(prop, RDFS.range)))
        try:
            wanted[prop] = (attribute_icon(root, graph, prop, name), name)
        except ValueError as error:
            failures.append(str(error))
    for iri in attributes:
        if (URIRef(iri), RDF.type, OWL.DatatypeProperty) not in graph:
            failures.append(f"{iri}: no attribute of the vocabulary")
    for prop, (svg, name) in wanted.items():
        failures += [f"{prop} ({name}): {p}" for p in problems(svg)]
    if failures:
        print("FAIL: property icons not written")
        for line in failures:
            print(f"  !! {line}")
        return 1

    stale = 0
    for path in files:
        text = original = path.read_text()
        declared = set(Graph().parse(path, format="turtle").subjects(RDF.type, None))
        for prop, (svg, name) in wanted.items():
            if prop not in declared:
                continue
            uri = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
            placed = place(text, prop, uri, name)
            if placed is None:
                print(f"FAIL: {prop}: its block in {path.name} could not be found to write the icon into")
                return 1
            text = placed
        if text != original:
            stale += 1
            if not check:
                Graph().parse(data=text, format="turtle")  # never write a file no parser accepts
                path.write_text(text)
    if check and stale:
        print(f"FAIL: property icons out of date in {stale} file(s) - run task icons")
        return 1
    verb = "up to date" if check else "written"
    print(f"OK: {len(wanted)} property icons {verb}, every one drawing only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
