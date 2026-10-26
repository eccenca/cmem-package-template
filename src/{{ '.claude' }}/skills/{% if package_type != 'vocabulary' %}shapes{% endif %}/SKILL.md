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

**A class the package does not own gets its icon from the node shape.** A
package that shapes a vocabulary it ships unchanged or depends on - QUDT, FOAF,
a customer's ontology - leaves those classes as the source ships them and puts
a `foaf:depiction` on its node shape instead, stroked as described in the
`vocabulary` skill's `references/depictions.md`. Explore takes a resource's icon
from the node shapes that target its class whenever the class has none, in the
navigation tree, the list and the page header (observed on CMEM 26.2). Without
it every unit or person in the package's views shows no icon; with a depiction
added to the source's class instead, the package would change a vocabulary it
does not own, and the next update of the source would drop it. The depiction
uses the FOAF namespace, so the manifest needs the `foaf-vocab` dependency (see
the `package-content` skill on dependencies).

**A package class whose instances another node shape also reaches gets
`shacl:order 0` on its node shape** - because the class extends a class that
Corporate Memory or another package already shapes (a domain's concepts under
`skos:Concept`, a class under a gist, BFO or schema.org class), or because its
instances carry such a type as well (a source that types its datatypes
`rdfs:Datatype` too brings Corporate Memory's datatype form along). Explore
offers a resource a form for every node shape whose target class it reaches
through its types and `rdfs:subClassOf`, and opens the page on the first, so
without the order the generic form can win. The other shape is not
the package's to change or remove, so ordering is the lever; check with
`GET /dataplatform/api/explore/resource/nodeshapeforms/byresource` that the
package's shape comes first for an instance of each such class.

**A resource is edited only where it lives.** When other graphs import a
resource, its node shape carries `shui:askIfEditableQuery`, so the form offers
editing only in the graph that holds the resource's statements; opened through
an importing graph, the same form is read-only and nobody writes a copy into
the wrong graph. Explore offers the edit control only when that query answers
true; `{{shuiGraph}}` is the graph the form is opened in, `{{shuiResource}}` the
resource. `shui:askIfRemovableQuery` takes the same query, so nobody removes the
resource through an importing graph. `shui:askIfCloneableQuery` and
`shui:askIfCreatableQuery` decide by graph alone and answer true only in the
graphs that may hold the class: Explore fills `{{shuiResource}}` with an empty
value for them, so the guarded query below would always hide Clone. A purely
aggregating resource's form gets `ASK { FILTER(false) }` and keeps its widgets.

```sparql
ASK { FILTER("{{shuiGraph}}" = "https://example.org/library/") }
```

**Pass the placeholders as strings and guard the empty value.** Explore also
runs the edit and remove queries without a resource; `<{{shuiResource}}>` then becomes `<>`,
the request fails with HTTP 400 and the form shows "Validation completed with
Unknown Error". An empty value has to answer false instead:

```sparql
ASK {
  BIND(IRI("{{shuiResource}}") AS ?resource)
  BIND(IRI("{{shuiGraph}}") AS ?graph)
  FILTER("{{shuiResource}}" != "" && "{{shuiGraph}}" != "")
  GRAPH ?graph { ?resource ?p ?o }
}
```

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

**Number the rows of a section in steps of 10, without ties, and give every
visible row an explicit order**: editable stored rows first, then read-only
stored rows, then rows computed by a query. Ties and gaps in the numbering let
the renderer decide, and a reader then meets the things to fill in after the
things to look at.

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

**A row that embeds a sub-shape (`shacl:node`) gets no group**, and neither do
the embedded node shapes nor a hidden `shacl:maxCount 0` guard row. Ungrouped
rows sort together with the groups by `shacl:order`, so give an embedding row
an order between two sections (250, 260). An embedded node shape carries no
description: the renderer repeats it under every embedded section.

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

**A computed *Type* row shows only the most specific classes**: its query leaves
out every class that is a superclass of another listed one. A resource typed
twice - its own class and, say, `skos:Concept` - would otherwise show *Concept*
next to its own class on every form, and badges aggregated over all concepts
with it.

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

**A renamed row takes its slug, its `rdfs:label` and the query named after it
along**, so the three stay findable from each other. A role in parentheses goes
into the slug camel-cased: *Acts (headliner)* becomes
`Festival-actsHeadliner`.

## Sections: one set per package, the same on every form

A form's sections are its property groups. **A package defines one set of
sections and uses it on all its forms**: each section has a one-sentence
`rdfs:comment`, its `shacl:order` is the same on every form, in steps of 100,
and a form shows only the sections it has rows for. Someone who has learned
where a section sits on one form then finds it there on the next. `shacl:order`
belongs to the group, not to the form, so one shared group per section is what
keeps its height fixed; give every group an explicit order, since without one
its position is undefined.

- **Sections follow meaning, never link direction.** A row reached through an
  inverse path goes into the section its meaning belongs to; there is no
  "Related" section collecting back-links, which would split one topic across
  two places.
- **At most one status section comes first** - findings or status widgets (a
  table report, an action button), no charts.
- **The overview with charts goes last**, after everything that is edited.

Packages stay alike through these recommended sections. Use them where they
fit and put the package's own sections between them, in the range 400-700:

| order | section | holds |
|---|---|---|
| 50 | Findings | the rule check's results for this resource |
| 100 | Identity | name, type, identifiers, notation |
| 200 | Description | definition, comment, notes |
| 300 | Classification | concepts, categories, kinds |
| 400-700 | the package's own | e.g. *Line-up*, *Tickets* |
| 800 | External sources | links out: `rdfs:seeAlso`, `skos:closeMatch`, a source's page |
| 900 | Overview | widgets, charts, table reports |

A user who knows one package then finds *Identity* at the top and *Overview* at
the bottom of the next one, while each domain keeps its own sections.

The gig package defines its set once and uses it on the Festival form and on
the Band form:

```turtle
gigos:group-identity a shacl:PropertyGroup ;
  rdfs:label "Identity"@en ;
  rdfs:comment "What the festival or band is called."@en ;
  shacl:order 100 .

gigos:group-description a shacl:PropertyGroup ;
  rdfs:label "Description"@en ;
  rdfs:comment "What the festival or band is about."@en ;
  shacl:order 200 .

gigos:group-when a shacl:PropertyGroup ;
  rdfs:label "When"@en ;
  rdfs:comment "The days a festival takes place."@en ;
  shacl:order 400 .

gigos:group-lineup a shacl:PropertyGroup ;
  rdfs:label "Line-up"@en ;
  rdfs:comment "Who plays at a festival, and where a band plays."@en ;
  shacl:order 500 .

gigos:group-overview a shacl:PropertyGroup ;
  rdfs:label "Overview"@en ;
  rdfs:comment "Figures computed from the gigs."@en ;
  shacl:order 900 .

gigos:Band-playsAt a shacl:PropertyShape ;
  shacl:name "Plays at"@en ;
  shacl:path [ shacl:inversePath gigo:hasAct ] ;
  shacl:nodeKind shacl:IRI ;
  shacl:group gigos:group-lineup ;
  shacl:order 10 .
```

The Festival form shows *Identity*, *When*, *Line-up* and *Overview*; the Band
form has no row for *When* and so does not show it, but its *Line-up* sits at
the same height as the festival's. *Plays at* reaches the band's festivals
through the inverse of `gigo:hasAct` and still goes into *Line-up*, because
sections follow meaning, not link direction. The row examples in this skill and
its references - *First day* in *When*, the band's *Visitors per year* widget in
*Overview* - use this set.

## `shacl:name` is the form, `rdfs:label` is the catalog

The two serve different readers and therefore follow different conventions.

- **`shacl:name`** renders the UI element built from the shape - a form row's
  caption, a form's title. It is what an end user reads, so it says
  "Condition", never "hasCondition", and **must never contain "node shape" or
  "property shape"**. Putting `"Product Node Shape"` in `shacl:name` and hiding
  the plain name in `rdfs:label` is the wrong way round.

  Row names are **sentence case, without acronyms, and plural for a row that can
  hold several values**. Name a row after the class it lists where that reads
  well ("Venues"), otherwise by its relation read from the form's resource
  ("Played at"). Two rows on one form that would get the same name are told
  apart by a role in parentheses ("Acts (headliner)", "Acts (support)").
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

- **Everything a form shows exists in every language the vocabulary has**:
  section titles and descriptions, row names and descriptions, node shape
  descriptions and messages. A user switching the UI language otherwise meets a
  form in two languages. The shapes' own `rdfs:label` stays English - it names
  the shape in the catalog, not on the form.
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
