---
name: vocabulary
description: Author and maintain the RDFS/OWL vocabulary a package ships - classes, properties, definitions, labels, comments and class icons. Use when a term is added, renamed or redefined, when writing skos:definition or rdfs:comment, or when deciding what a class is for.
---

<!--
PREVIEW: not yet in the template's main branch. Open pull requests: #31,
#48; merged to develop, not released: #30. From the branch
preview/skills of eccenca/cmem-package-template.
-->

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
- **A relation is named as a verb phrase**, read from its domain to its range:
  a verb (`manages`, `appliesTo`, `standsInFor`), or `has` / `is … of` with the
  role the range plays (`hasProductManager`, `isMemberOf`). Never a bare class or
  role name: `productManager` reads like the class Product manager and hides
  which way the relation runs. *A form row, a query and a Business Knowledge
  Editor drawing show the label between two resources - "Product has product
  manager Employee" says what it states, "Product product manager Employee" does
  not.*
- **An attribute is named as a noun** for the value it holds (`title`, `price`,
  `email`), without `has`, `is` or `was` - the verb belongs to relations, so the
  name tells a reader, a query author and a mapping which of the two a property
  is. *Schema.org, Dublin Core, DCAT and QUDT name their attributes this way, so
  a package's own terms read like the ones it reuses.* Where a kind of value has
  a form of its own, the name says it:
  - a date or a point in time ends in `Date` or `Time` (`acquisitionDate`,
    `startTime`), not a participle (`acquiredOn`) - the suffix names the
    datatype;
  - a yes/no value starts with `is` or `has` (`isSigned`, `hasCover`), the one
    exception: a bare `signed` could be a date or a person;
  - a count ends in `Count` (`pageCount`), an integer.

  `task check:offline` checks these four by spelling (`bin/check_names.py`) on
  the package's own properties; whether a name is a noun stays with review. A
  package that mirrors a published vocabulary unchanged keeps its publisher's
  names and switches the check off with an empty `.claude/no-naming-check`.
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
project package that installs the vocabulary declares the ontology as a
dependency that no graph imports. Do not state
`rdfs:subPropertyOf` across: every statement of the package would become one of
the other property's, so whatever that ontology says about it - domain, range,
characteristics, and their next release - applies to the package's data.

A class may extend a class of an upper ontology with `rdfs:subClassOf` - a
domain's concepts subclass `skos:Concept`, a package class may specialize a
gist, BFO or schema.org class. Its node shape in the shape catalog of a
project package then needs `shacl:order 0`, so that the package's form opens
before the upper class's.
Never make a class a subclass of `owl:Class` or another meta-ontology term -
that turns its instances into classes.

## Measure the claim before naming a property

Names asserting sufficiency (`implies…`, `triggers…`) or necessity
(`conditionFor…`, `requires`) are claims the data can contradict. Count first.

Where premises are conjoined, one premise is not *sufficient*; where several
rules reach the same object, none is *necessary*. What usually survives both
counts is participation - "contributes to".

## Going further

- `references/depictions.md` - the `foaf:depiction` icon every class wants, and
  the colour scheme that keeps a family recognisable
