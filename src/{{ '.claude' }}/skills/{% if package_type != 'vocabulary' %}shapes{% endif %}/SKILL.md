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

**An abstract class gets no node shape.** Without one the UI offers no way to
create a bare instance, which is exactly what abstract means. Give the concrete
subclasses their own shapes.

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

Reusing one property shape across many node shapes is normal and keeps a change
in one place - a shared `comment` or `editorialNote` field is the usual case.

## Derived fields

A field computed by a query carries `shui:valueQuery`, and often
`shui:inversePath` for a back-link.

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

## Queries live in this catalog

**Every query a shape references belongs in the shape catalog beside the shapes
that use it**, as a `shui:SparqlQuery` / `shui:SparqlOperation` with its
`shui:queryText`. A catalog pointing at a query in another graph is half a
deliverable: install the catalog somewhere that lacks the other graph and the
field silently renders nothing.

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

- `references/widgets.md` - aggregates, table reports, and the integration chain
- `references/navigation.md` - `shui:managedClasses` and navigation lists
- `references/validation.md` - validating a catalog without lying to yourself
