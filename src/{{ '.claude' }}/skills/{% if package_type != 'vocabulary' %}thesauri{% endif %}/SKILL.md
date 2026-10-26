---
name: thesauri
description: "Shape a thesaurus in a Corporate Memory package - a SKOS taxonomy of categories that resources point at - so that charts, forms and search stay readable, maintain it in the taxonomy editor or from an external term library, and categorize resources against it. Use when categories have grown flat and too many, when duplicates should be merged, when a taxonomy is to be maintained in the taxonomy editor or synchronised from a term library, when a standard classification is to be linked."
---

# Thesauri

A thesaurus here is a set of SKOS concepts that resources point at through a
categorizing property (`ex:genre`, `ex:componentKind`). It starts flat and grows
with whoever adds the next resource; left alone it ends with dozens of top-level
entries where a chart can show six. This skill is about keeping it usable,
maintaining it and letting people browse it.

**Naming:** call it a *thesaurus* (or *taxonomy* for its hierarchy), never a
*controlled vocabulary*: Corporate Memory's "Vocabularies" are its ontologies.
The taxonomy editor's own term is *thesaurus project*.

## The shape of a taxonomy

- **Few top concepts.** Everything that aggregates - a chart's series, a
  navigation tree's first level, a filter - shows the top level. Aim for about
  six, unless the top level mirrors a linked standard (one top concept per
  division of a classification) or the vocabulary is a flat list without a tree
  (badge or finding concepts). Then roll up in charts, or add a level above.
  *Use case: a chart or tree stays readable; a standard is not bent to fit the
  rule.*
- **Level classes**: concepts of one tree may have a class per level (category,
  feature, value) when a level has properties, relations or checks of its own; a
  tree whose levels all do the same job stays one class. The producer (import or
  seed) types by role in the tree; type on use types per property. *Use case: a
  feature tree with values is a small data model - without classes every form
  and check would reconstruct the level from the depth, and moving a concept
  would silently change its meaning.*
- **Place, do not relabel.** An existing flat concept keeps its IRI and labels
  and gets `skos:broader` to a top concept. A concept that already is general
  becomes a top concept itself rather than getting a new parent with the same
  name.
- **One broader per concept** unless the domain really has two parents: a
  concept with two broaders is counted under both tops in every roll-up and
  appears twice in a tree.
- **Merge duplicates**: keep the concept with more uses, relink every reference
  to the other (`DELETE/INSERT` on the referring property), then delete the
  merged concept's statements in both directions. Decide each pair with the
  people who own the data - a merge throws away a distinction somebody once
  made.
- **List the doubtful placements** when proposing a taxonomy and let the owners
  decide them.
- Roll-ups read the hierarchy, not a copy of it:
  `?x prop/skos:broader* ?top . FILTER NOT EXISTS { ?top skos:broader ?b }`.
  Then the taxonomy can change without touching a chart or report.

## The package's concept form comes first

A package class under `skos:Concept` inherits Corporate Memory's concept form
(`shacl:ConceptShape`, and `ConceptSchemeShape` for schemes), so its node shape
gets `shacl:order 0` (the `shapes` skill) - every such class, not only the one
that showed the problem. Navigation follows the same idea: browse by
the package's class or a scheme's top concepts, not by `skos:Concept`, which
lists every concept on the instance.

## Labels and languages

- `skos:prefLabel` with a language tag on every concept, in each language the
  package speaks. An untagged label fails a shape requiring `rdf:langString`.
- A concept scheme (`skos:ConceptScheme`, `skos:topConceptOf`) is needed by a
  tree that roots at the scheme's top concepts; the roll-up above works
  without one.

## Changing a vocabulary that holds user data

When the concepts live in a graph users author, the change is data, not package
content:

- Write it as a migration workflow (the `build-projects` skill): check whether
  it is needed, back up, change, verify, record. Every graph in its own `GRAPH`
  block, additions idempotent, so a second run changes nothing.
- Apply on a development instance, validate, look at the chart or tree with the
  owners, and only then on production.
- Merges and placements are separate steps: a placement only adds, a merge
  deletes.

## Who maintains a taxonomy

**One master per taxonomy, and its graph says which** - in the graph
description, so nobody edits a copy that the next delivery overwrites:

| master | the term graph | edits go to |
|---|---|---|
| the taxonomy editor | a thesaurus project (`dsm:ThesaurusProject`), writable | the editor |
| an external term library | replaced by its sync workflow on every delivery; read-only by access condition, still a thesaurus project so it can be browsed | the source system |
| a script or table | only as a **seed**: it writes the graph once, then the editor is master and the script stops writing it | - |

- **A term library the organisation already has takes precedence.** Mirror it
  as it is; do not map it onto the package's own taxonomy (two vocabularies to
  maintain) and do not copy it once (it drifts). The package's own taxonomy is
  the default for those without one.
- A build that regenerates a term graph from a table wipes every edit made in
  the editor. When the editor becomes master, the generator writes only the
  tables it still feeds.
- A taxonomy is not package definition: it reaches an instance through a
  bootstrap workflow, not as a filled graph in the manifest. Where the package
  has no natural XML source, the taxonomy ships as SKOS in RDF/XML (one
  `rdf:Description` per resource) and is mapped by an XML transform.

## Linking a standard classification

Copying a standard taxonomy into a package needs a licence that allows
redistribution and derivatives. Many common classifications do not grant that
(no open licence, no derivatives, or a commercial licence). The fallback that
needs no licence for the content:

- ship the package's **own** concepts with labels the package writes itself;
- carry the standard's code as `skos:notation` and link the standard's published
  concept IRI with `skos:closeMatch`; copy nothing else;
- check that every `closeMatch` target exists, with a query against the
  publisher's SPARQL endpoint, before shipping it.

Where a standard is open (CC0, CC BY), it may be bundled in its own graph with
`dcterms:license` and `dcterms:source` on the graph and a row in the
`DOCUMENTATION.md` licences table (the `package-content` skill). Share-alike
data (ODbL, CC BY-SA) stays in its own graph, marked as such.

## What the taxonomy editor reads and writes

- **A project is one graph**, typed `dsm:ThesaurusProject` in itself. The graph
  may hold any number of `skos:ConceptScheme`s, each shown as a root. For the
  tree, `owl:imports` is not followed, so schemes in separate graphs do not form
  one project. Do not copy them into one graph to get there - that graph would
  have several masters.
- **A concept's page follows `owl:imports`**: when the concepts are shipped in
  another graph, the project graph imports that graph and states only what the
  tree needs (the scheme, `skos:topConceptOf`/`skos:inScheme`, `skos:narrower`;
  the master states `skos:broader` once). Never copy labels, definitions, notes
  or notation into the project graph. The icon (the package class) also follows
  the import: the project graph states `a skos:Concept`, not the package class.
- **Give every concept both types**: `skos:Concept` and the package class. A
  concept typed only with a package subclass does not appear in the editor.
- **The form's *Type* row shows the most specific classes only** (the `shapes`
  skill): a plain `rdf:type` row lists *Concept* next to the package class. Keep
  the double typing in the data; fix the display.
- **The tree is built from `skos:hasTopConcept` and `skos:narrower`.** A
  taxonomy that states only `topConceptOf` and `broader` shows up empty or flat:
  state both directions - with a separate master, the master states `broader`,
  the project graph `narrower` and `hasTopConcept`, so no triple is in two
  graphs.
- **A concept created in the editor** is a plain `skos:Concept` with no package
  class and no `skos:inScheme`, linked with both directions. No hook of the
  package runs for it.
- **Hooks run on form saves, not on SPARQL writes**: `shui:onUpdateUpdate` on a
  node shape runs when a resource is saved through a form drawn with that shape,
  `shui:onInsertUpdate` / `shui:onDeleteUpdate` on a property shape per added or
  removed value. A SPARQL update - a workflow's, a script's - runs none of them,
  so a workflow that writes the same data runs the same update itself.
- **Corporate Memory keeps SKOS inverses in sync for forms**: its SKOS property
  shapes carry the system updates `shapes:Make-inverse-explicit-update` and
  `shapes:Clean-explicit-inverse-update`. A package row on `skos:broader` reuses
  them as its `shui:onInsertUpdate` / `shui:onDeleteUpdate` - do not write hooks
  of your own for this.
- **Never give a node shape to all of `skos:Concept`**: with order 0 it replaces
  the concept form of every taxonomy on the instance.
- **The package's concept form refuses editing when the thesaurus has another
  master**: its node shape carries `shui:askIfEditableQuery`,
  `askIfCreatableQuery`, `askIfRemovableQuery` and `askIfCloneableQuery` as
  `ASK { FILTER(false) }` (the `shapes` skill, *A resource is edited only where
  it lives*), plus the read-only link row to the editor (below). Read-only rows
  alone are not enough: Explore still offers *Edit*, and a save would land in
  the graph that is open, never in the thesaurus.
- **The taxonomy editor is not reached by those queries**: it draws Corporate
  Memory's own concept forms, so the concepts stay editable there. Protect the
  term graph with an access condition that makes it read-only for everyone but
  its producer (the table under *Who maintains a taxonomy*) - that is the only
  lever in the editor.

## Icons for the scheme and its concepts

A resource whose class has no `foaf:depiction` gets the icon of the node shape
that targets the class. The lookup runs in the graph that is open together with
its `owl:imports`: in the taxonomy editor a concept whose package class is
stated only in an imported graph still gets its class icon.

- **Concepts take their icon from their class.** Draw one icon per package
  class, as a `foaf:depiction` on its node shape, and type every concept with
  both `skos:Concept` and the package class - in the project graph, or in a
  graph the project graph imports. Do not copy the icon onto each concept.
- **A direct `foaf:depiction` on a concept** only where the concept means
  something of its own that the class icon cannot show.
- **The scheme gets a direct `foaf:depiction`: a small tree whose root is the
  glyph of the class it collects**, in that class's colour. A 24×24 viewBox,
  strokes only, the root glyph within y ≈ 1.8–10.2 around (12, 6):

  ```svg
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><g fill="none" stroke="COLOUR"
    stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
    ROOT-GLYPH
    <path d="M12 10.8v1.7M6 12.5h12M6 12.5v2.5M18 12.5v2.5"/>
    <rect x="3.5" y="15" width="5" height="5" rx="1"/><rect x="15.5" y="15" width="5" height="5" rx="1"/>
  </g></svg>
  ```

- Colours follow the `vocabulary` skill (`references/depictions.md`, *Colour*).
  Inline the SVG as a base64 `data:image/svg+xml` IRI, with a comment that says
  what it shows.
- **The thesaurus project keeps the editor's book**: give the project graph a
  direct `foaf:depiction` that redraws the book (Carbon's `Book`, 32×32, in the
  palette's darkest grey - never `currentColor`, which changes on mouse-over)
  with **one glyph on its right page** (x 17–28, y 7–25), in the schemes'
  colour. The editor's project list shows it.
- Check it in the taxonomy editor: the project list, the scheme, a top concept,
  a leaf.

## Typing concepts made in the taxonomy editor: type on use

The editor always creates a plain `skos:Concept`. A package subclass of
`skos:Concept` therefore treats its class as something a concept *gets through
use*:

- **The rule.** The package class's node shape has `shacl:order 0`, and no
  resource of the package should be *only* a `skos:Concept`.
- **Type on use, generically.** When a resource is saved, every concept it
  points to through a property whose `rdfs:range` is a `skos:Concept` subclass
  gets that class. The range is read from the vocabulary, never named in the
  update, so the same update fits any package. It runs from the referring
  class's node shape (`shui:onUpdateUpdate`) and in every workflow that sets the
  property.
- **Write only into the package's own data graph**: the visible graph that holds
  the concept as `skos:Concept` and declares `shui:managedClasses` for its
  class. A concept in another graph, such as a synced term library, gets its
  type from that graph's producer - and so does a shipped concept the project
  graph only references and imports: the update skips every concept another
  graph holds as its master, or it would type the copy back in.
- **Save validation does not block it.** A save of a resource whose row has
  `shacl:class <PackageClass>` and points at an untyped `skos:Concept` is
  accepted. Keep `shacl:class` on the row.
- **The picker.** A `shui:uiQuery` on the row offers every concept in the
  scheme's tree, never every `skos:Concept` - other concept classes would be
  typed as this one.
- **Gaps of an editor-made concept.** Keep the editor's IRI. Don't infer labels;
  flag a missing English label as a finding.
- **Lifecycle.** Concepts are created only in the taxonomy editor (the form row
  gets `shui:denyNewResources`); only a concept placed under something broader
  is offered or typed; when a concept is no longer used, the inferred type goes
  again - the concept stays in the editor.
- **"Used"** means a resource sits at the concept or anywhere below it
  (`?x <prop>/skos:broader* ?c`) - the same test for the picker and the type,
  so they agree. Shipped top concepts are exempt, and so is a
  concept that another visible graph types with the class.
- **Clean-up removes exactly what was inferred**: `a <class>` and
  `skos:inScheme`.
- **Reconcile all, on every hook.** One idempotent update types every used,
  placed concept and untypes every one that isn't. It runs on the referring
  resource's save, its delete (`onDeleteUpdate` runs before the delete, so it
  must ignore the resource being deleted), the concept form's save, and every
  workflow that writes the property. Changes made in the editor fire no hook and
  are corrected at the next save anywhere.
- **One master, generated copies**: the shape catalog holds the update; a script
  of the package writes every copy, and its `--check` mode runs as a task of
  the package's own in `TaskfileCustom.yaml` before every commit, so a hand
  edit to a copy fails the check.
- **Scope traps.** A `FILTER NOT EXISTS` inside `GRAPH ?data { … }` sees only
  that group's variables - put it where the concept is bound. Don't put
  `broader*` inside `GRAPH ?g`: the zero-length match leaves `?g` unbound.

## Concept forms show SKOS data, the categorizing link and usage

The node shape of a `skos:Concept` subclass has the SKOS rows, the inverse link
to the resources it categorizes, and widgets describing its use.
Package-specific data about a concept goes into SKOS terms:

- Corporate Memory's concept form offers `prefLabel`, `notation`
  (`xsd:string`), `definition`, notes, `example`, `altLabel`, `hiddenLabel`,
  `related` and `^member`; it has no broader/narrower rows and no mapping
  properties.
- Mapping to an external classification: its term names as `skos:hiddenLabel`,
  its code as `skos:notation` with the source in the string (`"DNB-SG 640"`).
- **A term that names a narrower concept belongs to that concept**: drop a
  hidden label from a broader concept when a narrower one has that name; the
  import checks it on every sync. A hidden label is a label of the concept
  itself. *Use cases: a suggestion still finds the narrower concept by its own
  label (an own label ranks above a hidden label); the taxonomy editor no longer
  shows the children's names on the parent.*
- **One notation per concept**: the system shape for `skos:notation` has
  `sh:maxCount 1` and applies to every `skos:Concept`. Keep the one code that
  actually decides; a finer code goes on a narrower concept. Never put the same
  code on two concepts.

## Categorizing resources by a taxonomy

The link from a resource to a concept is curated data, not a build product:

- Keep the links in a **categorization graph** that the build does not clear;
  let it `owl:imports` what the resource's form needs, and describe it with
  `void:propertyPartition [ void:property <categorizing property> ]`, so the
  graph says which links it holds. Links minted into a graph the build clears are lost on
  the next run.
- Name it after gist: a *categorization* graph (gist's `isCategorizedBy` links a
  thing to a `Category`).
- **Where a form save writes**:
  - a new value goes into the graph the form is open in - unless the node shape
    has a `shui:targetGraphTemplate`, then into the property shape's template if
    it has one, otherwise into the node shape's;
  - a removed value is deleted in the graph that holds it - for a row filled by
    a query only when the query returns a `?graph` column bound to the graph
    holding the triple (`FROM NAMED` + `GRAPH ?graph`); without it, or with
    `?graph` echoing the open graph, nothing is deleted;
  - a template names a **fixed** graph. Whether it substitutes any placeholder
    besides the account name is not yet observed - name the graph literally
    until a test shows otherwise.
- **Save the categorization where it lives, from any form**: give the resource's
  node shape and its categorizing row a `shui:targetGraphTemplate` naming the
  categorization graph, make every other row of that form read only. A save
  from the integration graph then lands in the categorization graph. Check in
  a task of the package's own in `TaskfileCustom.yaml` that every
  `shui:GraphTemplate` names a graph of the manifest, or the default of the bootstrap variable that set-up writes into
  it. *Use case: a save lands in the graph the instance really uses, also when
  the package ships that graph empty or not at all.*
- **Link the categorizing property to gist, do not subclass it**: depend on the
  gist vocabulary package, import it nowhere, and state
  `<categorizing property> rdfs:seeAlso gist:isCategorizedBy` - no
  `rdfs:subPropertyOf` (the `vocabulary` skill).
- **Keep the scheme IRI apart from the graph IRI** when the graph is a thesaurus
  project.
- **The categorizing property's range is the package subclass, also for term
  libraries of the organisation**: the import of a term library is its
  concepts' producer and types them with the package class. *Use case: an
  organisation's classification becomes the package's categories - type on use,
  `shacl:class` on the row and the picker then work the same for both sources,
  and no package has to know in advance whether a term library will come.*

## Importing a term library

- **One sync workflow per source**, delivering a complete SKOS graph that the
  workflow owns and replaces: push (the source dataset is the workflow's
  replaceable input, posted through the REST API) or pull (*Execute REST
  requests*).
- **Validate the delivery before replacing the graph**: an XML export against
  its XSD with *Validate XML*, its errors fed into *Cancel Workflow* (condition
  `empty`, inverted, *fail workflow* on), the mapping ordered after it by a
  dependency edge. A broken delivery fails the run and the old taxonomy stays.
- **Map a flat term list with parent references**: the root rule makes the
  scheme, an object mapping over the terms makes the concepts, `@parent` gives
  `skos:broader` and, as a backward target, `skos:narrower`;
  `label[@lang = "en"]` filters an XML element by its attribute.
- **Traps:** `replaceableInputs` takes the dataset's task id; a node id is
  accepted and silently dropped. DataIntegration adds `a di:Dataset` to every
  graph it writes. A URI rule `concat(constant, path)` needs its path segment in
  `glue`.
- **Replace, do not merge.** A merge needs stable identifiers and rules for
  deletions and conflicts - that belongs in a dedicated synchronisation package.
- **The import types what it delivers** with the package class (and the level
  class, where the tree has them), and drops hidden labels that name a narrower
  concept.

## A link from the concept's form to the taxonomy editor

- A read-only row on an annotation property of the package's own (e.g.
  `ex:openIn`, label "open in", comment "a link to another tool or view that
  shows this resource; computed by a form row, never stored", `rdfs:range
  sysont:Markdown`), `shui:readOnly true`, `shacl:nodeKind shacl:Literal`, whose
  `shui:valueQuery` returns the link typed `sysont:Markdown` (no `shui:markdown`
  needed). The nodeKind is required: Corporate Memory's own shape for property
  shapes demands one, so validate the shape catalog too, not only the
  integration graph. Never a borrowed path such as `rdfs:seeAlso` or
  `foaf:page`: their values are resources, not text.
- The editor addresses a concept as
  `/default/thesaurus/details?project=<graph>&concept=<concept>`. Find the
  project with `FROM NAMED <{{shuiGraph}}>` and
  `GRAPH ?project { ?project a eccdsm:ThesaurusProject . <{{shuiResource}}> a skos:Concept }`;
  build the link with `ENCODE_FOR_URI`.
- Make the link **absolute** (`/default/…`), so it reaches the editor
  wherever the form is opened.

## Charts on a taxonomy

Roll up to the top concept in the dataset query, one series per top concept,
and chart one level down a part-whole hierarchy.
