# Query placeholders

A `shui:QueryPlaceholder` declares a named parameter of a query. The consuming
query embeds the key literally - `GRAPH <{{graph}}> { … }` - and the
placeholder's `shui:QueryPlaceholder_valueQuery` supplies the choices,
projecting **`?value`** (the text substituted in) and optionally
**`?description`** (shown beside it in the picker).

The fields, from Corporate Memory's own node shape: `rdfs:label` (plain
`xsd:string`, **required**, exactly one - *not* language tagged, unlike most
catalog text), `rdfs:comment` (plain string, rendered as "Description"),
`shui:QueryPlaceholder_key`, `shui:QueryPlaceholder_datatype` (an IRI),
`shui:QueryPlaceholder_valueQuery` (one) and
`shui:QueryPlaceholder_usedInQuery` (many).

Declare yours in the package namespace with `shui:isSystemResource false`. Do
not put one in `https://ns.eccenca.com/data/queries/`, which is Corporate
Memory's system catalog, where its own `graph` placeholder lives marked
`shui:isSystemResource true`.

## `shuiResource` and `shuiMainResource` are not the same

Both name "the resource this is rendered for", and in most cases they resolve
to the same IRI - which is exactly why the wrong one survives until somebody
nests the shape.

- **`{{shuiResource}}` is the one to use normally.** It refers to the resource
  being rendered in the *immediate* sub-shape, so inside a nested form it
  follows the nesting and names whatever that level is about.
- **`{{shuiMainResource}}` keeps a stable reference to the top-level origin
  resource** of the entire structure, whatever depth the query runs at. Widgets
  use it, because a widget reports on the page rather than on a level.

Reach for `shuiMainResource` only where the query genuinely needs the origin
rather than the current level, and say so in its `dcterms:description`.

## Declaring a built-in key does not hijack it

`{{shuiGraph}}`, `{{shuiResource}}` and `{{shuiMainResource}}` are substituted
by the form renderer from context. Declaring a placeholder of the same key does
not override that - both were verified on a running instance to keep working
unchanged, even with a concrete value query attached.

So declaring a built-in is documentation plus an editor fallback: it records
which queries take which parameter, and supplies values only where there is no
form context. `task check:offline` warns about an undeclared built-in key for
that reason and fails on an undeclared custom one, where nothing would ever
substitute a value.

## One `shuiResource` placeholder per class

`{{shuiResource}}` is the resource a path builder query is rendered for. The
form renderer substitutes it from context; the query editor has none, so
without a declaration the parameter has to be pasted by hand. One placeholder
per class, each offering that class's instances, makes every path builder query
runnable from the editor.

**`shui:QueryPlaceholder_usedInQuery` scopes resolution per query, so one key
may be declared many times.** The key is resolved against the declaration
naming *that* query, not against the key alone, which is what lets each class
offer its own instances.

**The corollary is that a key may be claimed by at most one placeholder per
query.** Two placeholders sharing a key and both naming the same query leave it
ambiguous with nothing to break the tie - `task check:offline` fails on this.

That constraint drives the design: where a query serves two classes, either one
placeholder covers the union or the query is split. **Split it.** One
placeholder per class is the clearer model, it is what the
one-property-shape-per-node-shape rule asks for anyway, and each half can then
drop the alternation it only needed in order to serve both subject types.
Measure the branches per class before splitting rather than assuming which
belongs where; they are usually disjoint, and if they are not, the row means
something other than it claims.

## A value query has three constraints of its own

Each was found by breaking it:

- **It must contain no placeholder at all**, not even `{{shuiGraph}}`. It runs
  in order to produce values for a parameter, so a parameter of its own could
  never be resolved first. Name the graph literally.
- **`FROM <g>` follows `owl:imports`; `GRAPH <g> { … }` does not.** Reading
  instances from an integration graph that holds only imports gives 0 rows
  through `GRAPH` and all of them through `FROM`.
- **Accept the empty language tag as well as the one you want.**
  `FILTER(LANG(?l) = "en")` silently drops untagged plain literals, and the
  `COALESCE` fallback then shows raw IRIs in the picker.
  `FILTER(LANG(?l) IN ("en", ""))` covers both.

## Never write a key in braces inside a comment

Substitution is a plain text replace over the whole query text, **comments
included**. A value query that mentions its own key in prose therefore becomes
circular - Corporate Memory needs a value for the key in order to compute the
list of values for it - and the picker cannot be filled.

## Verify a custom key before shipping one

What is proven is a *built-in* key on queries attached to property shapes. A
**custom** key on a **standalone** query with no shape behind it is the
untested combination, and it is the one that has failed: such a placeholder was
built, installed and removed again because its picker never filled. Check a
custom key in the query editor before shipping it.

`cmemc query open <iri>` opens a query in the editor to check a picker, but its
`--catalog-graph` defaults to `https://ns.eccenca.com/data/queries/`. Pass the
package's own shapes graph, or it will not find the query.
