# Path builder queries

A property shape with `shui:valueQuery` takes its values from a **path builder
query** instead of reading its `shacl:path`. Always call it that - the predicate
is named `valueQuery`, but "value query" is reserved for nothing: the query
behind `shui:uiQuery` is a **selectable resources query**, the one behind
`shui:QueryPlaceholder_valueQuery` a **placeholder values query**
(`catalog-queries` skill).

Path builder queries serve seven different purposes. Each has its own shape,
query and validation treatment; `bin/check_path_builder_queries.py` classifies
every row into one of them and flags what fits none.

| # | Use case | The query returns | The row | Plain SHACL validation | `?graph` |
|---|---|---|---|---|---|
| 1 | **Subclass split** | the stored values of the path whose type is one leaf class | forward, editable, several rows on one path | keep | bound to the link |
| 2 | **Enriched stored relation** | exactly the stored values of the path, plus columns | forward, materialised path | keep | bound to the link |
| 3 | **Derived shortcut** | a multi-hop route the path *names* but nothing stores | forward, `shui:readOnly`, path unmaterialised | strip | bound to the defining hop, or echoed |
| 4 | **Back-link listing** | the subjects pointing at the resource, plus columns | `shui:inversePath`, `shui:readOnly` | strip | bound or echoed |
| 5 | **Read-only split** | 1 on a derived or inverse path | `shui:readOnly`, several rows on one path, `shacl:class` = the leaf | strip | as 3 or 4 |
| 6 | **Computed link** (anti-pattern) | a URL built from the resource | stand-in path (`rdfs:seeAlso`) | strip | echoed |
| 7 | **Embedded widget** (anti-pattern) | HTML | stand-in path (`rdfs:value`), header and footer hidden | strip | none |

**The validation rule follows from the table: keep a row for a plain SHACL
engine only if it is forward and its query returns nothing but stored values of
its path** (1 and 2). Everything else uses the path as a label, and a plain
engine would check the wrong triples (`validation.md`). Corporate Memory's own
validator ignores the `shui:` extensions and evaluates every row against its
path, which is why 3 to 7 need a path that is honest about direction and range
even though nobody edits them (`paths.md`).

**6 and 7 are catalogued, not recommended.** `paths.md` forbids a stand-in path
and `widgets.md` puts what is not a property of the resource into a widget. They
are listed so that existing rows can be classified; write no new ones. They do
work: a value column typed `sysont:Markdown` renders as markup, so an embedded
page shows (checked 2026-10-08); the objection is the stand-in path. A
computed link becomes a widget, or a real property where the URL is a stable
fact; an embedded page becomes a widget integration. Whether every existing
case has a widget to move to is unverified.

## 1 - The subclass split

One property, several rows: `ex:responsibleFor` ranges over the abstract
`ex:Product`, and the form shows one row per kind of product. The split lives
only in the form; the data keeps one property.

### When to split

Split only if a single row would need **different behaviour per subclass** - a
different selectable list, a different count - **and** the subclasses are
disjoint and few (about four at most). Grouping alone is no reason: the type
icon already tells the values apart. More leaves than that: keep one row.

Prefer the split over sub-properties (`ex:responsibleForHardware`): one
predicate keeps the term reusable and every reader of the data - inverse rows,
queries, transforms, exports - general, and the type, which already says what
kind a value is, is not stated twice. Sub-properties are the alternative only
where the relation itself means something different per subclass.

### The model it needs

- **Rows are the leaf classes of the range**, matched by exact type. A leaf has
  no subclasses, so `?value a ex:Hardware` is complete without
  `rdfs:subClassOf*`.
- **Superclasses are abstract: never instantiated directly.** Say so in their
  `rdfs:comment`; there is no reasoning to enforce an axiom. The abstract class
  gets **no node shape** (`SKILL.md`): Explore would offer it as a second form.
- Instances carry their leaf type explicitly - the data graph has no inference
  (`package-content`, graph architecture).
- A value that matches no leaf - untyped, or typed only with an abstract class -
  shows in no row. Mark it live, e.g. with a finding badge in the application
  view (`explore-badges`), rather than letting it disappear.

### The row

```turtle
ex-shapes:Department-responsibleForHardware a shacl:PropertyShape ;
  rdfs:label "Department: Responsible for hardware property shape" ;
  shacl:name "Hardware"@en ;
  shacl:path ex:responsibleFor ;
  shacl:nodeKind shacl:IRI ;
  shacl:class ex:Product ;                       # the range, never the leaf
  shacl:group ex-shapes:responsibilityGroup ;    # one group per split property
  shacl:order 1 ;
  shui:valueQuery ex-shapes:Department-responsibleForHardwareQuery ;
  shui:uiQuery ex-shapes:Department-responsibleForHardwareChoiceQuery ;
  shui:targetGraphTemplate ex-shapes:ResponsibilitiesGraphTemplate ;
  shui:denyNewResources true ;
  shui:showAlways true .
```

- **`shacl:class` is the range.** Every row sees every value of the path, so a
  leaf class would fail the sibling rows' values. With the range, plain SHACL
  checks the stored values truthfully (use case 1 is kept for validation).
- **One `shacl:group` per split property**, holding only its rows, named after
  the property; the rows are named by the leaf ("Hardware", "Services") and
  ordered within it.
- **Send the row's values to the graph that holds the link** with a
  `shui:targetGraphTemplate` on the row. The backend writes a form value into
  the property shape's template when the node shape has a template too, else
  into the node shape's template, and into the form's graph only when the node
  shape has none (Explore source, `ResourcePropertyInsert`; measured
  2026-10-07: a value set on a form whose node shape names a build graph landed
  in that build graph, whatever graph the form was open in). The frontend uses
  the same templates only to decide whether the row is offered as writable.
- **No inline creation (`shui:denyNewResources`)** where the leaf instances
  belong to graphs a build rewrites: a resource created from the row goes to
  its own node shape's template graph and is gone after the next build. Create
  it where it is maintained.
- **Counts per leaf only where the domain has them**, as a qualified value
  shape - `shacl:qualifiedValueShape [ shacl:class ex:Service ]`,
  `shacl:qualifiedMinCount`/`MaxCount`, `shacl:qualifiedValueShapesDisjoint
  true`. Without a count it checks nothing. Corporate Memory's validator
  evaluates it as the specification says (verified 2026-10-07: min, max and
  disjointness, reported with the constraint `UNKNOWN`); a form save that
  violates it is **not** blocked (verified), so it reports, it does not enforce.
- Names: `<Class>-<property><Leaf>`, the path builder query `…Query`, the
  selectable resources query `…ChoiceQuery` - the three sort together.

### The two queries

```sparql
# The hardware products the department is responsible for.
#
# ?resource: a product typed ex:Hardware that the department is responsible for
# ?graph: the graph holding the ex:responsibleFor triple
#
# Note: ?resource must stay left-most - it is the target of the row's shacl:path.
# Note: FROM NAMED is required - a GRAPH pattern under FROM alone matches nothing.
SELECT ?resource ?graph
FROM <{{shuiGraph}}>
FROM NAMED <{{shuiGraph}}>
WHERE {
  GRAPH ?graph { <{{shuiResource}}> ex:responsibleFor ?resource }
  ?resource a ex:Hardware .
}
```

```sparql
# The hardware products a department can be made responsible for.
#
# ?resource: a product typed ex:Hardware the department is not yet responsible for
#
# Note: ?resource must stay the only projected variable: the picker offers its values.
SELECT DISTINCT ?resource
FROM <{{shuiGraph}}>
WHERE {
  ?resource a ex:Hardware .
  FILTER NOT EXISTS { <{{shuiResource}}> ex:responsibleFor ?resource }
}
```

- **Let Corporate Memory walk the imports.** `FROM` and `FROM NAMED` both follow
  the context graph's `owl:imports`, transitively; a hand-written
  `owl:imports*` walk returns the same rows and is slower. Measured on 3.1 M
  triples over 413 imported graphs (2026-10-07): selectable resources queries
  1.7 to 3.6 times faster with `FROM`, the gap growing with the result size
  (405 ms vs 111 ms for 20 000 candidates); the path builder query, with the
  resource bound, 6 ms slower - the fixed cost of expanding the imports.
- **Wrap only the link in `GRAPH ?graph`**: `?graph` is where a removal through
  the form deletes the triple (`catalog-queries`, graph column), and the type
  sits in another graph than the link.
- **The selectable resources query hides what the row already holds.** Explore's
  picker does not (Explore source, `RelationManager`, read 2026-10-07).
- Declare `shuiGraph` and `shuiResource` placeholders so the queries run from the
  query editor (`catalog-queries`, placeholders).
- A split doubles the queries per leaf; `bin/check_path_builder_queries.py`
  keeps them in line with their row.

### Where the rows are edited

Keep curated links in a graph the build does not clear, or every build
overwrites what users edited; seed it from the build while it is empty, and
let that graph `owl:imports` what the row's queries need (the vocabulary, the
graphs holding the leaf instances), as for a classification graph (`thesauri`).
The row's `shui:targetGraphTemplate` sends every edit there, whichever graph
the form is open in - provided the node shape has a template as well; without
one, a save lands in the graph the form is open in.

### The inverse side

Judge it on its own with the same test: the back-link from a product to its
department splits only if the *departments* had leaf classes that need it. An
inverse row on the abstract superclass's node shape would be inherited by every
subclass - but the abstract class has no node shape, so put it on each leaf.

## What the checker enforces

`bin/check_path_builder_queries.py` (part of `check_all.py`) classifies every
row with a path builder query into the table above and, for each subclass
split:

- **fails** where a row lacks its path builder or selectable resources query,
  a query does not mention the row's path, the row's `shacl:class` is not a
  superclass of the leaf its queries test, the rows of a split do not share one
  group of their own, the path builder query does not bind `?graph` through
  `FROM NAMED` and `GRAPH`, or - when the vocabulary is in the package - a leaf
  of the range has no row;
- **warns** where a split row allows inline creation, a selectable resources
  query does not exclude held values, or a row is use case 6 or 7.
