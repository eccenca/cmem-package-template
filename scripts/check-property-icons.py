#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["rdflib>=7"]
# ///
"""Assert that the property icons a generated package ships are drawn, coloured and checked as described.

Run from inside a generated package directory; `check:icons:case` does that.

A generated package maps no property to an icon, so its own `task icons:check` passes whatever
`bin/property_icons.py` does. This drives the rendered package's script over a copy of
`tests/fixtures/icons` instead - two classes with icons of their own, relations with a shared glyph,
with "range" and without a mapping, attributes with a mapped glyph, a glyph of the package's own and
none, one depiction drawn by hand:

* written, every icon is in the vocabulary, the check passes, and a second run changes nothing;
* a relation is drawn in its range class's colour with the arrow, an attribute in its domain
  class's colour without one; an unmapped relation and the hand-drawn depiction are left alone;
* an attribute without a mapped glyph shows the kind of its value (date, yes/no, count);
* an icon edited by hand fails the check, a glyph that is not drawing only is refused, and a
  property of another namespace in the mapping is refused.

Exits non-zero with a one-line reason on the first failure.
"""

import base64
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import FOAF

SCRIPT = Path("bin") / "property_icons.py"
FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "icons"
EX = "https://example.org/icons/"
BAND, VENUE = "#b8325a", "#2a7f62"
ARROW = "M2 12 H8.6"


def fail(message):
    print(f"check-property-icons: {message}", file=sys.stderr)
    sys.exit(1)


def run(root, *args):
    result = subprocess.run([str(SCRIPT.resolve()), *args, str(root)], capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def icons(root):
    """Each property's embedded icon SVG, by local name."""
    graph = Graph().parse(root / "pkg" / "graphs" / "vocab.ttl")
    found = {}
    for prop, value in graph.subject_objects(FOAF.depiction):
        if str(prop).startswith(EX) and str(value).startswith("data:image/svg+xml;base64,"):
            found.setdefault(str(prop)[len(EX):], []).append(
                base64.b64decode(str(value).split(",", 1)[1]).decode())
    return found


def main():
    if not SCRIPT.is_file():
        fail(f"{SCRIPT} does not exist - the template did not ship it")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "fixture"
        shutil.copytree(FIXTURE, root)
        vocab = root / "pkg" / "graphs" / "vocab.ttl"

        code, output = run(root, "--check")
        if code == 0:
            fail(f"the check passed before any icon was written:\n{output}")
        code, output = run(root)
        if code != 0:
            fail(f"writing the icons failed:\n{output}")
        written = vocab.read_text()
        code, output = run(root, "--check")
        if code != 0:
            fail(f"the check failed right after writing:\n{output}")
        run(root)
        if vocab.read_text() != written:
            fail("a second run changed the vocabulary")

        drawn = icons(root)
        expect = {
            "isBasedAt": lambda s: VENUE in s and ARROW in s,
            "hasHomeVenue": lambda s: VENUE in s and ARROW in s and "translate(9.6 5.4)" in s,
            "email": lambda s: BAND in s and ARROW not in s,
            "foundingDate": lambda s: BAND in s and "M4 6 H20 V20.5 H4 Z" in s,
            "isTouring": lambda s: "M8 12.5 L11 15.5 L16.5 9" in s,
            "memberCount": lambda s: "M4 15 L20 9" in s,
            "capacity": lambda s: VENUE in s and "M6 9 A2 2" in s,
        }
        for name, test in expect.items():
            if len(drawn.get(name, [])) != 1 or not test(drawn[name][0]):
                fail(f"{name}: icon missing, doubled or not drawn as described")
        if "supports" in drawn:
            fail("an unmapped relation got an icon; it keeps the built-in one")
        if len(drawn.get("stageName", [])) != 1 or 'class="property-icon"' in drawn["stageName"][0]:
            fail("the depiction drawn by hand was replaced or doubled")

        # planted: an icon edited by hand
        start = written.index("# property-icons: email")
        line_start = written.rindex("\n", 0, start) + 1
        tampered = written[:line_start] + written[line_start:start].replace("base64,", "base64,PHN2Zy8+", 1) \
            + written[start:]
        vocab.write_text(tampered)
        if run(root, "--check")[0] == 0:
            fail("an icon edited by hand passed the check")
        vocab.write_text(written)

        # planted: a glyph that is not drawing only
        glyph = root / "icons" / "glyphs" / "attributes" / "audience.svg"
        glyph.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
                         '<script>alert(1)</script></svg>')
        code, output = run(root)
        if code == 0 or "element <script>" not in output or vocab.read_text() != written:
            fail(f"a glyph with a script was not refused, or something was written:\n{output}")
        shutil.copy(FIXTURE / "icons" / "glyphs" / "attributes" / "audience.svg", glyph)

        # planted: a property of another namespace
        mapping = root / "icons" / "property-icons.json"
        data = json.loads(mapping.read_text())
        data["relations"]["https://example.org/other/sponsor"] = "supplied-by"
        mapping.write_text(json.dumps(data))
        code, output = run(root)
        if code == 0 or "not a property of this package" not in output:
            fail(f"an icon on another namespace's property was not refused:\n{output}")

    print(f"check-property-icons: ok ({len(expect)} icons drawn as described, hand-drawn and unmapped "
          "left alone, 3 planted faults caught)")


if __name__ == "__main__":
    main()
