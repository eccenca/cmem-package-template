#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["rdflib"]
# ///
"""Audit shipped SPARQL queries against the "Documenting a query" convention.

Every shui:SparqlQuery in a shape catalog carries three separate pieces of prose, and the
convention is about keeping them apart:

* ``rdfs:label`` is the catalog name;
* ``dcterms:description`` is the rationale — why the relation is expressed this way, what the
  claim does and does not assert, which hops a path abbreviates;
* the **header comment** of the query text is the map of the query: one opening line saying
  what it computes, then one ``# ?var: …`` line per projected variable **in projection
  order**, then a ``# Note:`` only for a constraint a later editor could silently break.

The projection order matters beyond tidiness: on a path builder query the left-most projected
variable is the target of the path and the rest are extra columns, so the header is where that
fact gets written down. A query whose header does not list its projection leaves the next
editor to work that out from the SPARQL.

The body then wants a short comment on each block, saying why the block is there rather than
restating the triple pattern.

Projection variables are also checked for capitalisation, which is a correctness rule rather
than a style preference: Corporate Memory picks the column carrying the value as *a variable
named ``?resource``, or the first variable of the query when ``?resource`` is absent*, and a
capitalised projection variable has defeated that selection in production — a row projecting
``?Condition`` rendered the condition in place of the results.

Verdicts:

* **FAIL** — a projected variable whose name starts with a capital. This is the one finding
  here that names something broken rather than something unwritten, so it is the only one
  that stops a build.
* **WARN** — no dcterms:description; a header whose ``# ?var:`` lines are not exactly the
  outer projection in order; no comment anywhere in the body; or a header long enough that
  the rationale has probably leaked into the query text.

The documentation findings warn rather than fail because this runs as a build gate over
every generated package. Measured over the eccenca package fleet, failing on them turned 7
of 8 catalogs red — one of them with nothing actually wrong — which buries the findings that
do name a fault.

The projection is read with a paren-aware parser, so aliases and sub-SELECTs do not confuse
it: only top-level ``?var`` tokens and the ``AS ?var`` of a top-level expression count.

    audit_queries.py config-shapes.ttl [more.ttl ...]

Exits non-zero when a query fails.
"""

import re
import sys
from pathlib import Path

from rdflib import Graph
from rdflib.namespace import RDF, Namespace

SHUI = Namespace("https://vocab.eccenca.com/shui/")
DCTERMS = Namespace("http://purl.org/dc/terms/")

# Header budget: the template needs an opening line, a blank, one line per projected
# variable and a blank, so ~3 + n. The slack covers a Note block and a wrapped opening.
HEADER_SLACK = 8


def local(term):
    """Readable short name for an IRI, without needing to know the namespace."""
    text = str(term)
    for sep in ("#", "/", ":"):
        head, found, tail = text.rpartition(sep)
        if found and tail:
            return tail
    return text


def strip_comments(text):
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def outer_projection(text):
    """Top-level projection of the FIRST select, paren-aware.

    Variables inside an alias expression or a sub-SELECT are not part of the projection, so
    the scan tracks parenthesis depth and only takes bare ?vars at depth 0 plus the ?var of
    each top-level ``(… AS ?var)``.
    """
    body = strip_comments(text)
    match = re.search(r"\bSELECT\b\s+(?:DISTINCT\s+|REDUCED\s+)?", body, re.I)
    if not match:
        return []
    index = match.end()
    depth = 0
    out = []
    token = ""
    while index < len(body):
        char = body[index]
        if char == "(":
            depth += 1
            token += char
        elif char == ")":
            depth -= 1
            token += char
            if depth == 0:
                alias = re.search(r"AS\s+\?(\w+)\s*\)\s*$", token, re.I)
                if alias:
                    out.append(alias.group(1))
                token = ""
        elif depth == 0 and re.match(r"[\s]", char):
            if token.strip().startswith("?"):
                out.append(token.strip()[1:])
            token = ""
            rest = body[index:].lstrip()
            if re.match(r"\b(FROM|WHERE)\b|\{", rest, re.I):
                break
        else:
            token += char
        index += 1
    if token.strip().startswith("?"):
        out.append(token.strip()[1:])
    seen = set()
    return [v for v in out if not (v in seen or seen.add(v))]


def split_header(text):
    """The leading comment block, and the line index where the body starts."""
    lines = text.splitlines()
    header = []
    for index, line in enumerate(lines):
        if line.startswith("#"):
            header.append(line)
        elif not line.strip():
            if header:
                return header, index
        else:
            return header, index
    return header, len(lines)


def audit_one(graph, query):
    text = str(next(graph.objects(query, SHUI.queryText), ""))
    header, body_start = split_header(text)
    body = text.splitlines()[body_start:]
    projection = outer_projection(text)
    documented = re.findall(r"^#\s*\?(\w+)\s*:", "\n".join(header), re.M)

    row = dict(
        name=local(query),
        description=next(graph.objects(query, DCTERMS.description), None) is not None,
        projection=projection,
        documented=documented,
        header_len=len(header),
        header_budget=len(projection) + HEADER_SLACK,
        body_comments=sum(1 for ln in body if ln.lstrip().startswith("#")),
        capitalised=[v for v in projection if v[:1].isupper()],
    )
    row["fails"] = []
    row["warns"] = []
    # Only the capitalisation finding fails. It names something that is broken
    # - Corporate Memory renders the wrong column - while a missing description
    # or an unmapped header names prose that was never written. Both are worth
    # reporting and neither should stop a build: measured over the package
    # fleet, failing on them turned 7 of 8 catalogs red, one of them with
    # nothing actually wrong.
    if row["capitalised"]:
        row["fails"].append(
            f"capitalised projection variable(s) "
            f"{', '.join('?' + v for v in row['capitalised'])} — Corporate Memory takes the "
            f"first projected variable as the resource column when ?resource is absent, and a "
            f"capital defeats that selection; use lower camel case")
    if not row["description"]:
        row["warns"].append("no dcterms:description — the rationale has nowhere to live")
    if documented != projection:
        row["warns"].append(
            f"header documents {documented or ['nothing']} but the outer projection is "
            f"{projection or ['nothing']} — on a path builder query the left-most variable "
            f"is the target of the shacl:path, so the header is where that gets recorded")
    if row["body_comments"] == 0:
        row["warns"].append("no comment anywhere in the body")
    if row["header_len"] > row["header_budget"]:
        row["warns"].append(
            f"header is {row['header_len']} lines for {len(projection)} projected "
            f"variable(s) — rationale belongs in dcterms:description")
    return row


def check(paths):
    graph = Graph()
    for path in paths:
        graph.parse(path, format="turtle")

    queries = sorted(set(graph.subjects(RDF.type, SHUI.SparqlQuery)), key=str)
    if not queries:
        print("no shui:SparqlQuery found — nothing to audit")
        return 0

    rows = [audit_one(graph, query) for query in queries]
    width = max([len(r["name"]) for r in rows] + [len("query")])

    print(f"{len(rows)} shipped query/queries")
    print()
    print(f"{'query':{width}}  {'desc':4} {'outer projection':38} "
          f"{'documented':16} {'hdr':>5} {'body#':>5}  ")
    print("-" * (width + 76))
    for row in rows:
        verdict = "FAIL" if row["fails"] else ("WARN" if row["warns"] else "ok")
        print(f"{row['name']:{width}}  {'yes' if row['description'] else 'NO':4} "
              f"{','.join(row['projection'])[:37]:38} "
              f"{(','.join(row['documented']) or '-')[:15]:16} "
              f"{row['header_len']:>5} {row['body_comments']:>5}  {verdict}")

    total = len(rows)
    print()
    print("--- summary ---")
    print(f"missing dcterms:description  : {sum(1 for r in rows if not r['description'])}/{total}")
    print(f"projection undocumented      : "
          f"{sum(1 for r in rows if r['documented'] != r['projection'])}/{total}")
    print(f"no comments in body          : "
          f"{sum(1 for r in rows if r['body_comments'] == 0)}/{total}")
    print(f"header over its budget       : "
          f"{sum(1 for r in rows if r['header_len'] > r['header_budget'])}/{total}")
    print(f"capitalised projection var   : {sum(1 for r in rows if r['capitalised'])}/{total}")

    failing = [r for r in rows if r["fails"]]
    warning = [r for r in rows if r["warns"]]
    if warning:
        print()
        for row in warning:
            for note in row["warns"]:
                print(f"  ~~ {row['name']}: {note}")
    if failing:
        print()
        print(f"FAIL: {len(failing)}/{total} query/queries would render the wrong column")
        for row in failing:
            for note in row["fails"]:
                print(f"  !! {row['name']}: {note}")
        return 1
    print()
    if warning:
        print(f"OK: no query projects a capitalised variable "
              f"({len(warning)}/{total} carry documentation warnings above)")
    else:
        print("OK: every query carries a rationale and a header mapping its projection")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    absent = [p for p in sys.argv[1:] if not Path(p).exists()]
    if absent:
        sys.exit(f"no such file: {', '.join(absent)}")
    sys.exit(check(sys.argv[1:]))
