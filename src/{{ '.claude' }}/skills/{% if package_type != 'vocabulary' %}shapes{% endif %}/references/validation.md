# Validating a shape catalog

## Run the offline checks first

`task check:offline` needs no instance and no credentials, and it catches two
things that are invisible until after an install:

- **A dangling `sh:property` / `sh:node` / `sh:group` / `sh:sparql` reference
  makes the SHACL service answer HTTP 500 for every graph**, with nothing in
  the response naming the cause. Audit for these after any edit that removes or
  renames a shape.
- **A `shacl:path` that reaches nothing leaves every constraint on its row with
  nothing to check**, so validation passes and proves nothing. See
  `paths.md`.

## Validating against the instance

```sh
cmemc -c <connection> graph validation execute <graph-iri> --wait --inspect
```

Run this over every graph the change could touch after any edit to the
vocabulary or the catalog.

**Validate the graph that imports everything, never a part alone.** The
validator does not follow `owl:imports`, so a part validated on its own lacks
the vocabulary and the data its shapes refer to: in one package the rules graph
alone gave 4,366 violations over 909 of its 910 resources, the integration graph
none. Validate the integration graph, or whichever graph imports what the
shapes need. One exception: where that import closure is very large (around a
hundred thousand triples), validating through it can exhaust Explore's memory
for everyone on the instance - validate the package's own data graphs one by one
there instead.

**Data has to satisfy Corporate Memory's own system shapes too**, which a
package's catalog does not show:

- a graph's own `rdfs:label` and any `skos:hiddenLabel` must be language-tagged
  (`rdf:langString`); an untagged `skos:altLabel` gives a warning
- `1` is no `xsd:decimal` - write `1.0`
- a table report needs both `shui:TableReport_hideHeader` and
  `shui:TableReport_hideFooter` (see `widgets.md`)

**Take counts from `violationsCount` in `graph validation list --raw`.** The
`inspect` endpoint *streams* its results, so calling it twice on the same
finished run can return different lengths - which looks like the data changing
underneath you.

## A plain SHACL engine misreads a shui catalog

`shui:inversePath` and `shui:valueQuery` are Corporate Memory UI extensions. A
standard SHACL processor does not know them, so it evaluates the **forward**
path instead and invents violations - "venues in this city" gets checked as
"this city's `withinLocation` must be a Venue".

**Strip every property shape carrying `shui:inversePath` or `shui:valueQuery`
before validating.** What remains is exactly the set of real constraints. A
report full of violations that all name derived fields is this problem, not a
data problem.

## What `cmemc package build` does not check

A clean build proves the manifest matches the directory. It **ignores RDF syntax
errors entirely**, so a `.ttl` no parser accepts builds happily and fails at
install. `task check:offline` parses every graph and fails on one that no
parser accepts, which is the cheapest way to cover that gap.

## Property coverage is worth checking

Every predicate written on an instance should have a field on that class's node
shape. A predicate with no field means data nobody can see in the Explore UI -
it is in the graph, it is correct, and it is invisible.

Checking this across a package has found real gaps: `rdfs:comment` and
`skos:editorialNote` written on several classes with no field to show them,
fixed by adding one shared property shape to every node shape.

The check is mechanical - collect the predicates used per class from the data,
collect the paths of that class's property shapes, and report the difference.
Ignore `rdf:type`.

## Where a field went

When a field does not appear where expected, in order of likelihood:

1. the property shape has no `shacl:group`, or the group has no order
2. a widget has no `shui:WidgetIntegration_group`, so it rendered above the form
3. the shape catalog is not imported into `https://vocab.eccenca.com/shacl/`, so
   nothing in it is active at all
4. the field is derived and its query returns nothing - check the query against
   the installed graphs rather than the files
