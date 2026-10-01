---
name: catalog-queries
description: Write and document the SPARQL queries a shape catalog ships - path builder queries behind a form row, value queries behind a picker, and the header comment, projection and placeholders each one needs. Use when a query is added to or edited in the catalog, when a form row shows the wrong column, or when a picker does not fill.
---

# Queries inside a shape catalog

A shipped query is a `shui:SparqlQuery` in the shape catalog, carrying its
`shui:queryText`. It drives a form row (`shui:valueQuery`), a widget, or a
parameter picker. The SPARQL is the smaller half of the job: Corporate Memory
reads the *shape* of the projection, and a reader of the catalog has only the
comments to go on.

`task check:offline` reports all of what follows, but fails the build only on
the findings where something is actually broken - a capitalised projection
variable, a placeholder key written inside a comment, a value query carrying a
parameter, a query a shape points at that ships no text. The documentation
conventions print as warnings: worth fixing, not worth stopping a build.

## Which column carries the value

**Corporate Memory picks the column carrying the value as a variable named
`?resource`, or the first variable of the query when `?resource` is absent.**
Everything else is an extra column.

On a path builder query that makes the **left-most projected variable the
target of the path**, which is why the projection order is part of the query's
contract and not a matter of taste.

**Projection variables are lower camel case, never capitalised** -
`?conjunctiveCondition`, not `?Condition`. This is a correctness rule, not a
style preference: a capitalised projection variable has defeated that column
selection in production, rendering the wrong value in the row, and renaming the
variable fixed it. Where the obvious name is already bound in the body, qualify
it rather than reuse it - an `AS` alias may not rebind a variable already in
scope.

## Documenting a query

Every shipped query carries a header comment that maps it, and inline comments
on the blocks of its body:

```sparql
# Computes an instance count facet for each resource.
#
# ?resource: the resource whose instances are counted
# ?instanceCount: number of instances of the resource and its subclasses
#
# Note: SELECT must be exactly ?resource and ?instanceCount.
# No rebinding, aliases, or expressions allowed in the projection.
SELECT ?resource (COUNT(?instance) AS ?instanceCount) {

  # Get all instances of the resource and its subclasses
  ?instance rdf:type/rdfs:subClassOf* ?resource .

  # Restrict bindings to context-relevant resources
  {{VALUES}}

# Count instances for each resource
} GROUP BY ?resource
```

- One opening line saying what the query **computes**.
- One `# ?var: …` line per **projected** variable, in projection order. On a
  path builder query the first of them is the target of the path, so this is
  where that fact gets written down.
- A `# Note:` only for a constraint that would silently break the query if a
  later editor changed it - a required projection, a forbidden alias, a
  contract with the caller.
- A short comment on each block of the body, saying why the block is there
  rather than restating the triple pattern.

**The longer explanation of why the query exists goes in `dcterms:description`
on the query resource, not in the query text** - why the relation is expressed
this way, what the claim does and does not assert, which hops a path
abbreviates. In the query text it only clutters what an editor reads while
working on the SPARQL.

So: `rdfs:label` is the catalog name, `dcterms:description` is the rationale,
and the header comment is the map of the query itself.

**Never write a placeholder key in braces inside any comment.** Substitution is
a plain text replace over the whole query text, comments included - see
`references/placeholders.md`.

## Extra columns are plain strings

**The form renderer honours no markup datatype.** Typing a column with
`STRDT(…, rdf:HTML)` or `STRDT(…, sysont:Markdown)` does nothing: the value is
rendered as text either way. Project the plain string.

The tell that this has been believed is a separator that only makes sense as
markup - a `SEPARATOR=' <br> '` was never a line break and shows as a literal
`<br>` the moment the typing comes off. If a separator reads as a tag, the
column was written against a renderer that does not exist.

Two things to clean up whenever a typing comes off, both of which otherwise
mislead the next reader:

- **The `rdfs:Datatype` declaration.** Catalogs declare their datatypes at the
  top so `shacl:datatype` has something typed to point at. Once nothing uses
  one, the declaration is dead - check what `shacl:datatype` actually
  references first, and remove only the unreferenced ones.
- **The now-dead `PREFIX` lines.** A `PREFIX sysont:` line implies the query
  uses Markdown typing when nothing does. Detect them per query by stripping
  the `PREFIX` block and searching the remaining body - **comments included**,
  so a prefix mentioned only in prose counts as used and stays. Removing them
  must not change the triple count.

## Going further

- `references/placeholders.md` - `shui:QueryPlaceholder`, the built-in keys,
  value queries and the traps in each
- `references/graph-column.md` - the `?graph` column of a path builder query,
  and when to compute it rather than echo the context graph back
