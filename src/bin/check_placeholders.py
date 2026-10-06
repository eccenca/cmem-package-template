#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["rdflib"]
# ///
"""Check the shui:QueryPlaceholder declarations of a shape catalog.

A placeholder declares a named parameter of a shipped query: the query embeds the key
literally as ``{{key}}`` and the placeholder's value query supplies the choices offered in
the picker. Four things about that arrangement are easy to get wrong and impossible to see
by reading the Turtle, and all four are checked here.

1. **A key may be claimed by at most one placeholder per query.** Resolution is scoped by
   shui:QueryPlaceholder_usedInQuery, not by the key alone, which is what lets one key be
   declared many times — one shuiResource placeholder per class. Two placeholders sharing a
   key and both naming the same query leave that key ambiguous with nothing to break the tie.

2. **Every parameter a query actually uses wants a declaration naming that query.** Without
   one the parameter has to be pasted by hand in the query editor, and nothing records which
   query takes which parameter. For a **built-in** key — shuiResource, shuiMainResource,
   shuiGraph — this is a warning rather than a failure: the form renderer substitutes those
   from context whether or not a placeholder exists, so the declaration buys documentation
   and an editor fallback, not behaviour. For any other key it is a failure, because nothing
   will ever substitute a custom key that is not declared.

3. **A value query must contain no placeholder at all.** It is evaluated in order to produce
   values for a parameter, so a parameter of its own could never be resolved first. Name the
   graph literally.

4. **No placeholder key in braces inside a comment.** Substitution is a plain text replace
   over the whole query text, comments included, so a query that mentions a key that way in
   prose still gets substituted — and a value query mentioning its own key becomes circular.

Namespaces are read from the parsed graph; nothing here is specific to one package.

    check_placeholders.py config-shapes.ttl [more.ttl ...]

Exits non-zero on a failure.
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

from rdflib import Graph
from rdflib.namespace import RDF, Namespace

SHUI = Namespace("https://vocab.eccenca.com/shui/")

TOKEN = re.compile(r"\{\{\s*([^{}\s]+?)\s*\}\}")

# Keys the form renderer substitutes from context. A query using one of these works
# with no declaration at all, so a missing declaration is a warning: it costs only the
# ability to run the query from the query editor, which has no form context. A missing
# declaration for any OTHER key is a failure - nothing will ever substitute it.
BUILTIN_KEYS = {"shuiResource", "shuiMainResource", "shuiGraph"}


def local(term):
    """Readable short name for an IRI, without needing to know the namespace."""
    text = str(term)
    for sep in ("#", "/", ":"):
        head, found, tail = text.rpartition(sep)
        if found and tail:
            return tail
    return text


def query_texts(graph):
    """Every shipped query mapped to its text."""
    texts = {}
    for query in graph.subjects(RDF.type, SHUI.SparqlQuery):
        text = next(graph.objects(query, SHUI.queryText), None)
        if text is not None:
            texts[query] = str(text)
    return texts


def parameters(text):
    """The {{name}} tokens a query text uses, in first-appearance order."""
    seen = []
    for name in TOKEN.findall(text):
        if name not in seen:
            seen.append(name)
    return seen


def comment_tokens(text):
    """(line number, line, tokens) for every comment line carrying a {{name}} token."""
    hits = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.lstrip().startswith("#"):
            continue
        found = parameters(line)
        if found:
            hits.append((number, line.strip(), found))
    return hits


def check(paths):
    graph = Graph()
    for path in paths:
        graph.parse(path, format="turtle")

    texts = query_texts(graph)
    placeholders = sorted(graph.subjects(RDF.type, SHUI.QueryPlaceholder), key=str)
    value_queries = set(graph.objects(None, SHUI.QueryPlaceholder_valueQuery))
    driving = sorted(set(graph.objects(None, SHUI.valueQuery)), key=str)

    # (key, query) -> placeholders claiming it
    claims = defaultdict(list)
    failures = []
    warnings = []

    print(f"{len(placeholders)} placeholder(s), {len(texts)} shipped query/queries, "
          f"{len(driving)} query/queries driving a property shape")
    print()

    width = max([len(local(p)) for p in placeholders] + [12])
    print(f"{'placeholder':{width}}  {'key':16} {'valueQuery':10} {'usedInQuery'}")
    print("-" * (width + 42))
    for placeholder in placeholders:
        keys = [str(k) for k in graph.objects(placeholder, SHUI.QueryPlaceholder_key)]
        value_query = next(graph.objects(placeholder, SHUI.QueryPlaceholder_valueQuery), None)
        used = list(graph.objects(placeholder, SHUI.QueryPlaceholder_usedInQuery))
        key = keys[0] if keys else "<none>"
        print(f"{local(placeholder):{width}}  {key:16} "
              f"{('yes' if value_query is not None else 'NONE'):10} {len(used)}")
        if not keys:
            failures.append(f"{local(placeholder)} declares no shui:QueryPlaceholder_key")
        for one_key in keys:
            for query in used:
                claims[(one_key, query)].append(placeholder)

    # 1. a key claimed twice for the same query
    print()
    ambiguous = {pair: ps for pair, ps in claims.items() if len(ps) > 1}
    by_key = defaultdict(set)
    for key, query in claims:
        by_key[key].add(query)
    for key in sorted(by_key):
        dupes = [q for (k, q) in ambiguous if k == key]
        print(f"key '{key}': claims {len(by_key[key])} query/queries, "
              f"{len(dupes)} claimed more than once")
    for (key, query), ps in sorted(ambiguous.items(), key=lambda kv: str(kv[0])):
        failures.append(
            f"key '{key}' on {local(query)} claimed by "
            f"{', '.join(sorted(local(p) for p in ps))}")

    # 2. every parameter of a query-driven query covered for that query
    print()
    uncovered = 0
    for query in driving:
        text = texts.get(query)
        if text is None:
            failures.append(f"{local(query)} drives a property shape but ships no shui:queryText")
            continue
        params = parameters(text)
        missing = [p for p in params if not claims.get((p, query))]
        status = "ok" if not missing else "MISSING " + ", ".join(missing)
        print(f"  {local(query):58} params: {','.join(params) or '-':28} {status}")
        for param in missing:
            uncovered += 1
            if param in BUILTIN_KEYS:
                warnings.append(
                    f"{local(query)} uses {{{{{param}}}}} with no placeholder naming that "
                    f"query — it still resolves from form context, but the query cannot be "
                    f"run from the query editor without pasting a value")
            else:
                failures.append(
                    f"{local(query)} uses {{{{{param}}}}} with no placeholder naming that "
                    f"query — nothing substitutes a custom key that is not declared")
    print(f"  -> {uncovered} uncovered parameter(s) over "
          f"{len(driving)} query-driven query/queries")

    # 3. a value query must carry no parameter of its own
    print()
    print(f"{len(value_queries)} value query/queries")
    for query in sorted(value_queries, key=str):
        text = texts.get(query)
        if text is None:
            failures.append(f"value query {local(query)} ships no shui:queryText")
            continue
        params = parameters(text)
        print(f"  {local(query):58} {'ok' if not params else 'HAS ' + ','.join(params)}")
        for param in params:
            failures.append(
                f"value query {local(query)} uses {{{{{param}}}}} — a value query is "
                f"evaluated to produce values, so its own parameter can never be resolved")

    # 4. no key in braces inside a comment
    print()
    brace_hits = 0
    for query in sorted(texts, key=str):
        for number, line, found in comment_tokens(texts[query]):
            brace_hits += 1
            failures.append(
                f"{local(query)} line {number}: comment mentions "
                f"{', '.join('{{%s}}' % f for f in found)} — substitution rewrites comments too"
                f"\n       {line}")
    print(f"placeholder braces inside a comment: {brace_hits} over {len(texts)} query/queries")

    print()
    if warnings:
        for warning in warnings:
            print(f"  ~~ {warning}")
        print()
    if failures:
        print(f"FAIL: {len(failures)} problem(s)")
        for failure in failures:
            print(f"  !! {failure}")
        return 1
    if warnings:
        print(f"OK: nothing broken ({len(warnings)} undeclared built-in key(s) noted above)")
    else:
        print("OK: placeholders unambiguous, parameters covered, "
              "value queries and comments clean")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    absent = [p for p in sys.argv[1:] if not Path(p).exists()]
    if absent:
        sys.exit(f"no such file: {', '.join(absent)}")
    sys.exit(check(sys.argv[1:]))
