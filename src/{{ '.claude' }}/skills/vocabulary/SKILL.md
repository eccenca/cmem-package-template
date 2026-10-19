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

## Link to an upper ontology, do not bridge into it

A class that corresponds to a term of an upper or external ontology (gist, for
instance) links to it with `rdfs:seeAlso`; the ontology becomes a package
dependency that no graph imports. Do not state `rdfs:subClassOf` or
`rdfs:subPropertyOf` across: the axioms would pull the other ontology's
inferences and constraints into the package's data. And never make a class a
subclass of `owl:Class` or another meta-ontology term - that turns its instances
into classes. Subclassing `skos:Concept` for a domain's concepts is different
and fine: it is a domain class, not a meta term.

## Measure the claim before naming a property

Names asserting sufficiency (`implies…`, `triggers…`) or necessity
(`conditionFor…`, `requires`) are claims the data can contradict. Count first.

Where premises are conjoined, one premise is not *sufficient*; where several
rules reach the same object, none is *necessary*. What usually survives both
counts is participation - "contributes to".

## Going further

- `references/depictions.md` - the `foaf:depiction` icon every class wants, and
  the colour scheme that keeps a family recognisable
