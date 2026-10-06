---
name: shapes
description: Author and maintain the SHACL/shui shape catalog a package ships - node shapes, property shapes, groups, URI templates, derived fields, widgets and navigation. Use when a class needs a form in the CMEM Explore UI, when a field does not appear or appears in the wrong place, or when the catalog has to be validated.
---

# The shape catalog

A shape catalog is a graph typed `shui:ShapeCatalog`. It does two jobs at once,
and the second is the one that surprises people: it **validates** data as SHACL,
and it **drives the Corporate Memory Explore UI** - which class offers a form,
which fields that form has, in what order, which of them are read-only, and what
the resulting resource's IRI looks like.

Consequence: a change that is meaningless to SHACL can still be the whole point
of the edit, and an edit that looks like a constraint can quietly change a form.

## How it is wired into the package

The catalog is a graph like any other in `cpa-manifest.json`, with one entry
that is easy to lose and fatal to lose:

```json
{
  "file_path": "explore/shapes.ttl",
  "file_type": "graph",
  "graph_iri": "https://vocabs.example.com/<vocab>/shapes/",
  "import_into": ["https://vocab.eccenca.com/shacl/"],
  "register_as_vocabulary": false
}
```

`import_into` names the **global shape catalog**. That is what activates these
shapes on install; remove it and the package installs cleanly and does nothing.
The catalog itself declares `owl:imports` of the vocabulary it shapes.

`register_as_vocabulary` is `false`: the graph declares a `shui:ShapeCatalog`,
not an `owl:Ontology`, so registering it would register no prefix.

## Node shapes

```turtle
gigos:Festival a shacl:NodeShape ;
  shacl:targetClass gigo:Festival ;
  rdfs:label "Festival"@en ;
  rdfs:comment "A multi-day event with its own bill. Add one festival day per day that was played."@en ;
  shacl:property gigos:Festival-startDate, gigos:Festival-venue ;
  shui:uriTemplate gigos:EventURITemplate ;
  shui:navigationListQuery gigos:navlist-festival .
```

Note the prefix: these catalogs write `shacl:`, not `sh:`.

**A node shape's user-facing text is `rdfs:comment`, not `shacl:description`.**
`shacl:description` is the help text of a single *property* shape. The
platform's own catalog settles it - 21 of its node shapes use `rdfs:comment` and
one uses the other. It is shown while someone creates or edits a resource of
that type, so write what the thing is and what to do with it, not a restatement
of the class comment.

**An abstract class gets no node shape** where its subclasses already cover
every instance. Without one the UI offers no way to create a bare instance,
which is exactly what abstract means. Each subclass carries the shape; the
superclass carries none.

## Property shapes

```turtle
gigos:Festival-startDate a shacl:PropertyShape ;
  shacl:name "First day"@en ;
  shacl:description "The day the festival begins."@en ;
  shacl:path gigo:startDate ;
  shacl:datatype xsd:date ;
  shacl:nodeKind shacl:Literal ;
  shacl:group gigos:group-when ;
  shacl:order 10 ;
  shacl:minCount 1 ;
  shacl:maxCount 1 .
```

`shacl:group` points at a `shacl:PropertyGroup`; `shacl:order` sorts within it.
`shui:` adds the UI behaviour: `shui:showAlways` holds an empty row open,
`shui:readOnly` forbids editing, `shui:markdown` and `shui:textarea` change the
input widget, `shui:languageIn` restricts language tags.

**Measure before asserting a cardinality.** Derive every `shacl:minCount` and
`shacl:maxCount` from a SPARQL count over the real data rather than guessing.
Every property shape also needs a `shacl:nodeKind`, and a `shacl:datatype` has
to point at something typed `rdfs:Datatype`, so declare the datatypes the
catalog uses at the top of the file.

**When a shape and the data disagree, fix the data or the model - not the
shape.** Relaxing a constraint to make a validation run pass turns the catalog
into a description of whatever the data happens to be. Where the choice is
between a looser shape and a stricter one that still holds, take the stricter
one: it is the only part of the package that can catch a regression.

Reusing one property shape across many node shapes is normal where the path is
a domain-free annotation - a shared `comment` or `editorialNote` field is the
usual case - and it keeps a change in one place. Do **not** share a row whose
path is typed or whose values come from a query: one `shacl:path` cannot be
type-correct for two target classes, and the query ends up serving both through
an alternation. See `references/paths.md`.

## Derived fields

A field computed by a query carries `shui:valueQuery`, and often
`shui:inversePath` for a back-link. **Multi-hop relations are
`shui:valueQuery` path builder queries** - standard SHACL sequence paths are
not used anywhere in Corporate Memory, and 0 of the 236 paths in eccenca's own
system catalog are blank nodes.

Derived is not the same as query-driven. A row whose query returns exactly what
its `shacl:path` reaches is query-driven but not derived, and it may stay
editable; `references/paths.md` has the test and what each outcome means.

**A derived field takes `shui:readOnly` and neither `shacl:minCount` nor
`shui:showAlways`.** Both of those address a user who is expected to act, and
nobody can type into a generated field: a `minCount` raises a violation the
reader of the form cannot fix, and `showAlways` holds open a row that fills
itself or stays empty regardless. Put the expectation on the editable inputs the
derivation reads from. An empty derived field simply reads as "not computed
yet".

## URI templates

```turtle
gigos:EventURITemplate a shui:URITemplate ;
  shui:templateString "{graph}event/{label}" .
```

- named things interpolate **`{label}`**
- join resources with no name of their own - a membership, a performance, an
  address - interpolate **`{uuid}`**, keeping a type segment so the IRI still
  says what it identifies

A label that the system generates rules out `{label}`, not a template: an
identifier must not be slugged from a value something is about to overwrite, so
such a shape uses `{uuid}` and keeps its `shui:onUpdateUpdate` operation for the
label. Omitting the template altogether also yields a UUID, but directly under
the graph IRI and without the segment.

`{uuid}` is a platform placeholder, not an invention. The placeholders are not
enumerated in the documentation; query `?t shui:templateString ?s` across all
graphs to see what exists.

## Readable slugs, never UUIDs

Corporate Memory mints UUID local names when a shape, group or query is created
through the UI. Replace them. A UUID tells a reader nothing, forces a lookup on
every cross-reference, and a local name starting with a digit - which two
thirds of them do - is legal Turtle that breaks syntax highlighting. The
platform's own built-in queries use slugs such as `total-number-of-triples`.

The scheme, by how widely the resource is shared:

| resource | slug |
|---|---|
| property shape on one class | `<Class>-<camelCased row name>` |
| shape shared by subclasses of one class | `<Superclass>-<row>` |
| shape shared by unrelated classes | `<row>` |
| property group | the same, plus `Group` |
| path builder query | the using shape's slug, plus `Query` |

Naming a query after the shape that uses it keeps the pair adjacent when the
file is sorted, and a query with no matching shape then stands out as an
orphan.

Renaming exposes duplicates that UUIDs hide - but **duplicate group labels are
often correct, not redundant**. `shacl:order` belongs to the group, not to the
form, so placing one block at a different height on several forms requires one
group per form, and merging them would force a single position everywhere. Give
every group an explicit `shacl:order`; without one its position is undefined.

## `shacl:name` is the form, `rdfs:label` is the catalog

The two serve different readers and therefore follow different conventions.

- **`shacl:name`** renders the UI element built from the shape - a form row's
  caption, a form's title. It is what an end user reads, so it says
  "Condition", never "hasCondition", and **must never contain "node shape" or
  "property shape"**. Putting `"Product Node Shape"` in `shacl:name` and hiding
  the plain name in `rdfs:label` is the wrong way round.
- **`rdfs:label`** is how the shape itself appears in a catalog listing, so it
  must **distinguish one shape from another**. Many `shacl:name`s repeat by
  design, so a bare label identifies nothing.

Derive `rdfs:label` from the slug, which is unique by construction:
`<Class>-NodeShape` → `"<Class> node shape"`; `<Class>-<row>` →
`"<Class>: <Row> property shape"`; a shared `<row>` → `"<Row> property shape"`.

Property **groups** are the exception: SHACL renders a group's `rdfs:label` as
the block heading, so there it *is* the UI text and stays short
("Constraints", "Metadata").

## Queries live in this catalog

**Every query a shape references belongs in the shape catalog beside the shapes
that use it**, as a `shui:SparqlQuery` / `shui:SparqlOperation` with its
`shui:queryText`. A catalog pointing at a query in another graph is half a
deliverable: install the catalog somewhere that lacks the other graph and the
field silently renders nothing.

**Mint them in the package's own namespace**, not in
`https://ns.eccenca.com/data/queries/`. That is Corporate Memory's system query
catalog, and putting your IRIs there claims a namespace the package does not
own.

How to write and document the query itself - the header comment, the
projection, placeholders, the `?graph` column - is the `catalog-queries` skill.

## House style

The conventions below are what the eccenca packages converged on. They are
recommended defaults - a package with a good reason may depart from them.

- Fixed property groups with stable orders, the resource's name at order 1 of
  the first group: **Basics** (10), **When** (20), **Where** (30), then
  domain-specific groups, **Stats** (60) for counted figures, **Related** (90)
  for read-only back-links, always last.
- Design reasoning lives on the term it concerns as `skos:editorialNote`, in
  English only, even where labels and comments are bilingual: it is for whoever
  maintains the vocabulary, and a translated argument drifts.
- Labels come from a few shared label shapes rather than one copy per node
  shape, using `shacl:uniqueLang` instead of `shacl:maxCount` so a second
  language stays possible.

## Going further

- `references/paths.md` - why every row needs a real `shacl:path`, and how to
  diagnose a query-driven row that has the wrong one
- `references/widgets.md` - aggregates, table reports, and the integration chain
- `references/navigation.md` - `shui:managedClasses` and navigation lists
- `references/validation.md` - validating a catalog without lying to yourself
