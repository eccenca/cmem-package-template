# Every property shape needs a real path

Never use `shacl:path <urn:path>` as a placeholder on a query-driven row. The
same goes for the softer version: pointing `shacl:path` at a real property that
does not reach the values the query returns.

Two reasons, and the second is the one that bites:

1. A placeholder carries no semantics. The relation lives only inside an opaque
   SPARQL body, so a reader of the vocabulary cannot tell what the row shows.
2. **It silently disables validation.** A path that matches nothing gives
   `shacl:class`, `shacl:nodeKind` and every cardinality nothing to check, so
   wrong assertions on that row survive indefinitely. Placeholder rows checked
   after the fact turn out to be wrong the moment a real path makes the
   constraints live - a row asserting one `shacl:class` while returning
   another, a row asserting `shacl:nodeKind shacl:Literal` over IRIs.

`task check:offline` reports both as failures, so this is enforced rather than
merely recommended.

## Name the shortcut, and leave it unmaterialised

Declare the relation the row shows as an `owl:ObjectProperty` in the
vocabulary. The vocabulary then says what the row means, the `shacl:class`
becomes a live check, and the data stays as the pipeline writes it.

Materialising such relations is usually wrong: they are derivable, and writing
them adds large numbers of triples that can go stale. Mark the row
`shui:readOnly true` - the relation is derived, so a hand edit could only
contradict its own query - and state in the `rdfs:comment` which hops the
property abbreviates and that it is not materialised.

Do not add `owl:propertyChainAxiom` when the path builder query already
computes the relation and nothing else relies on inference.

## Diagnose a query-driven row by counting both sides

Compare what the query returns against what the path reaches, for the same
subject. Three outcomes, three different faults:

- **They agree.** The path names exactly what the query computes and the query
  merely adds columns. The row is sound and may legitimately stay editable.
  `shui:readOnly true` is the rule for *derived* relations, not a blanket flag
  for every query-driven row; setting it here only makes a working row
  read-only for no reason.
- **The path reaches nothing.** It is a placeholder, or type-incorrect -
  inverted from the wrong end, or pointed at a property whose domain or range
  does not admit the target class.
- **They differ.** This is the one that hides. The path is a real,
  materialised property and the row renders, so nothing looks wrong - but the
  form lists one set while a deletion through it would remove a triple from
  another.

**One subset is meant: the subclass split.** Where several editable rows share
one path and each query keeps only the values of one leaf class of the range,
the rows *should* differ from the path - each shows a typed part of it, every
value it shows is stored, and a removal deletes exactly that triple. That is
use case 1 of `path-builder-queries.md`, not this fault; keep the rows editable
and their `shacl:class` at the range.

Do not bend the query to match the path. The query usually states the row's
intent correctly and the *path* is the thing misnamed: name the derived
relation, make it an `rdfs:subPropertyOf` the materialised one where every
computed value is also a stored one, and mark the row read-only.

## One property shape per node shape, where the path is typed

Sharing one property shape across two node shapes forces one query to serve
several subject types through an alternation path, and no single `shacl:path`
can then be type-correct for all of them. Splitting costs a few more lines and
makes each row independently readable.

This is about typed and query-driven rows. A shared annotation row whose path
has no `rdfs:domain` to be wrong about - `comment`, `editorialNote` - stays
shared, which is what keeps one change in one place.

## Measure the claim before naming the property

Naming the shortcut is a claim about the data, and the data can contradict it.
The `vocabulary` skill has the rule and what to count.
