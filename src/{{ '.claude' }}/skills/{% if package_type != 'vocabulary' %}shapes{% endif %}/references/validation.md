# Validating a shape catalog

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
install. Parse every graph yourself as a separate step.

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
