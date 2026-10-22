---
name: vocabulary
description: Author and maintain the RDFS/OWL vocabulary a package ships - classes, properties, definitions, labels, comments and class icons. Use when a term is added, renamed or redefined, when writing skos:definition or rdfs:comment, or when deciding what a class is for.
---

# The vocabulary

The ontology a package ships: its classes, its properties, and the annotations
that say what each one means. A vocabulary package is exactly this; a project
package usually carries one too.

The graph declares an `owl:Ontology` **at the graph IRI** with
`vann:preferredNamespacePrefix` and `vann:preferredNamespaceUri` - that is what
`register_as_vocabulary` needs in order to register a prefix.

## Predicate order

Structural axioms first (`rdfs:subClassOf`, `rdfs:domain`, `rdfs:range`,
`rdfs:subPropertyOf`), then `rdfs:label`, `skos:definition`, `rdfs:comment`,
`rdfs:isDefinedBy`, `foaf:depiction`, `dcterms:modified`.

A consistent order makes a diff readable: a term that gained a constraint looks
different from one that gained prose.

## `skos:definition` is the definition, `rdfs:comment` is everything else

Definitions follow the **substitution principle** of ISO 704 / DIN 2330, which
iiRDS applies: the definition must be a noun phrase that can *replace the term*
in running text. So it is genus plus differentiating characteristics, with no
article, no initial capital, no final full stop, and never a sentence *about*
the term.

- yes - `"constraint that puts a material into a position of the bill of material when its condition holds"`
- no - `"A constraint that selects a material…"`, article and capital, reads as prose
- no - `"Relates a value precondition to a material that…"`, describes the term instead of replacing it

Test it by substituting the definition for the term in a real sentence. For an
object property the definition denotes the **object role**, qualified by the
relation: `valueOf` is "feature whose set of admissible values contains the
feature value", so "v is a value of f" becomes "f is the feature whose set of
admissible values contains v".

`rdfs:comment` then carries what the definition must not - for a derived
property the **verbalization of its inference rule** ("If a product has a
material, and a selection condition selects that material, then…"), and for
everything else the invariants, the measured counts and the pointers to related
terms. Name related terms with the vocabulary's own prefix, in the comment
rather than the definition.

**German definitions** follow the same principle and keep German noun capitals:
"no initial capital" applies only where the definition starts with an adjective
or a participle. Where the head noun and the agent are both feminine, a relative
clause can be read the wrong way round (*die Bedingung, die die Regel prüft*) -
write it passive (*die von der Regel geprüft wird*).

## Naming

- Class labels are sentence case (`"Feature value"`, not `"FeatureValue"`);
  property labels are lowercase words (`"selects material"`).
- Class names are **head-final**: the last word says what the thing *is*.
  `ValuePrecondition` is a precondition; `ConditionValue` would wrongly name a
  value.
- **A term's IRI and its label always match.** Renaming a term renames its IRI,
  and with it every slug, query, task id and instance IRI built from it, so a
  reader never has to translate between the two. The former name, and an expert
  name users search for, stay as `skos:altLabel` or `skos:hiddenLabel`.
- Bump `dcterms:modified` whenever a term's definition changes.

## Classify by intention, not by content

A class is what its role in the model makes it, not what its instances happen
to contain. A content-based rule silently reclassifies things when the data
changes, which is how a vocabulary stops describing anything stable.

## Upper ontologies: properties link, classes may extend

A property that corresponds to a property of an upper or external ontology
(gist's `isCategorizedBy`, for instance) links to it with `rdfs:seeAlso`; the
ontology becomes a package dependency that no graph imports. Do not state
`rdfs:subPropertyOf` across: every statement of the package would become one of
the other property's, so whatever that ontology says about it - domain, range,
characteristics, and their next release - applies to the package's data.

A class may extend a class of an upper ontology with `rdfs:subClassOf` - a
domain's concepts subclass `skos:Concept`, a package class may specialize a
gist, BFO or schema.org class. Its node shape then needs `shacl:order 0`, so
that the package's form opens before the upper class's (the `shapes` skill).
Never make a class a subclass of `owl:Class` or another meta-ontology term -
that turns its instances into classes.

## Measure the claim before naming a property

Names asserting sufficiency (`implies…`, `triggers…`) or necessity
(`conditionFor…`, `requires`) are claims the data can contradict. Count first.

Where premises are conjoined, one premise is not *sufficient*; where several
rules reach the same object, none is *necessary*. What usually survives both
counts is participation - "contributes to".

## Competency questions, drawn

A package states the questions its model has to answer as competency questions:
one SPARQL query per file in `requirements/questions/<slug>.rq` (next to the
package directory, not shipped), its header comment carrying the question as
it was asked - `# question: Which of our suppliers sit in a country we flag?`.
*Whoever changes the model sees which questions it still answers, and a
customer signs off a model as the answer to their own questions.*

After changing a question, a class or a property, run `task visualizations`.
It writes one Business Knowledge Editor visualisation per question into
`graphs/competency-questions.ttl` (declared in the manifest): the part of the
model that answers it, named after the question.

Each relation reads as an L: its box in the row of the class it leaves from,
right beside it, and the class it leads to in the box's column, above or
below. Where the two classes are already aligned, the box sits on the line
between them, and several relations between the same two classes stand stacked
across it. *A reader follows each relation along one short edge and one
straight drop, the way the model's author would sketch it.* A class's
attributes (datatype properties) sit on its left, one below the other - on the
first free side of below, right and above where an edge arrives on the left,
never above a class with a parent - closer to it than any of its relations.
*Closeness reads as belonging: a class and its attributes are one unit, the
relations connect units.* The BKE places the datatypes itself and marks them
as not declared in the vocabulary, which is true.

Where these meet, a higher rule decides, so a reader of a drawing can tell why
each box sits where it does:

0. **No edge across the drawing**: a relation box at most three columns from
   the class it leaves from, the class it leads to at most one column beside
   it, and no edge longer than that across or down. *An edge across the whole
   picture reads as badly as a crossing.*
1. **Nothing crosses**: no edge through a box or a label, no label on a box or
   another label, no two edges leaving a box together, no box on a box. The
   BKE draws each edge as a curve with its label in the middle; the check takes
   the straight line. A crossing no placement avoids is named by the check.
2. **Hierarchies run top-down**, parent above child: a superclass above its
   subclass, and every relation the vocabulary marks as a tree -
   `rdfs:subClassOf`, `skos:broader`, a transitive part-of, a property linked by
   `rdfs:seeAlso` to `gist:isPartOf`, `gist:isMemberOf` or
   `gist:isCategorizedBy` - with its box on the line between parent and child,
   whichever way the query reads it. Every level between a class and a
   superclass is drawn. A step between instances of one class -
   `?c skos:broader* ?parent` within a taxonomy - gets no box: the drawing
   shows the model, the visualisation's description names the walk, and the
   application view shows the tree.
3. **The L**, as above.
4. **One parent straight above.** A class with several parents in the drawing
   has one bound parent directly above it - the hierarchy the question asks
   about (member of, part of) before `rdfs:subClassOf` - and the others reach it
   by an angled edge. The L ranks higher: a class the question reaches by a
   relation hangs below that relation, and its `rdfs:subClassOf` runs angled.
5. **A parent centred** over its bound children.
6. **The question's first class top left**, where nothing above decides; the
   same question always gives the same drawing.
7. **The shortest edges.**

- The boxes are the classes and properties the query names, plus each
  property's declared domain and range, so every box is connected: where the
  query names a subclass (`?x a :Hardware ; :hasSupplier ?s` with the property
  declared on `:Product`), the declared class sits above it and the BKE draws
  the `rdfs:subClassOf` link. A question that names no term of the vocabulary
  gets no drawing, and the check says so.
- **Open a drawing** for whoever reviews it in the Business Knowledge Editor
  with one link per visualisation, so nobody searches for it by name:
  `https://<host>/<view>/bke/viz?graph=<context graph>&vizIri=<visualisation IRI>&catalogGraphIri=<graph holding the visualisations>`,
  each IRI URL-encoded - `graph` is the visualisation's `shui:hasContextGraph`
  (the vocabulary), `catalogGraphIri` the competency-questions graph, and
  `<view>` an application view of the instance. *A reviewer judges a drawing
  only in the BKE; the Explore page of the same IRI shows its triples, not the
  drawing.*
- Positions are never placed by hand: `task visualizations:check` reports a
  drawing that no longer matches its question or the vocabulary. A hand-made
  visualisation goes into a graph of its own.

## Going further

- `references/depictions.md` - the `foaf:depiction` icon every class wants, and
  the colour scheme that keeps a family recognisable
