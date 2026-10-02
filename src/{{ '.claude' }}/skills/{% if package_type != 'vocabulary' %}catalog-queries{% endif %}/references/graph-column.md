# The `?graph` column of a path builder query

A path builder query conventionally projects `(<{{shuiGraph}}> AS ?graph)` as a
trailing column. Corporate Memory uses that attribution for two things:

- **Deletion.** When a value is removed through the form, `?graph` is what
  tells Corporate Memory which graph to delete the statement from.
- **The graph chip.** Each value is rendered with a visible marker naming the
  graph that value's triple is located in.

So the column is read as a claim about where the value *is*. Do not describe it
in a comment as the query's input graph echoed back - that says where the value
came from, which is a different claim.

## Binding it to the graph that actually holds the triple

`?graph` can be bound rather than echoed, and the recipe keeps the `shuiGraph`
parameter, so no graph IRI is hard-coded:

```sparql
FROM <{{shuiGraph}}>
FROM NAMED <{{shuiGraph}}>
...
  GRAPH ?graph { ?resource :someProperty ?value }
```

Two facts make that work, neither of them obvious:

1. **`FROM` populates the default graph, not the named-graph set.** A query
   carrying `FROM` and then a `GRAPH ?g` pattern matches **nothing** - no
   error, no warning, just an empty row. A `GRAPH` pattern needs its own
   `FROM NAMED`.
2. **Corporate Memory expands `owl:imports` for `FROM NAMED` as well as for
   `FROM`.** Naming the *integration* graph in `FROM NAMED` therefore binds
   `?graph` to the *data* graph, because the integration graph imports it. That
   is what keeps the recipe parameterised: the form's context graph goes in,
   and the graph physically holding the triple comes back.

Where a query already carries `PREFIX : <{{shuiGraph}}>` and `FROM :`, the
change is the one line `FROM NAMED :` plus a `GRAPH ?graph { … }` around the
hop.

## When to prefer the computed binding

- **Take it when the row's `shacl:path` is materialised** and the query reaches
  the value in one hop. The column then reports a fact rather than a tautology,
  and the echo is not merely uninformative: on the four-graph layout the form
  is rendered against the integration graph, which holds nothing but imports,
  so a value deleted against that attribution is deleted from a graph the
  triple is not in.
- **Wrap the defining hop, not the whole body.** One `GRAPH ?graph` block can
  only match triples that all live in the same graph, so wrapping a path whose
  hops straddle two graphs reproduces trap 1 - zero rows, silently. A
  sub-`SELECT` inside the block inherits the active graph as well. Measure
  which graph each traversed predicate is in before wrapping anything.
- **A bound `?graph` joins the `GROUP BY` key**, which the constant never did.
  If the wrapped hop is asserted in more than one graph, each value's row
  splits into one row per graph.
- **Keep the echo where no hop is defining.** On a derived multi-hop relation
  no single stored triple underlies the value, so the choice of hop to wrap is
  itself a claim.
- **Where a hop is wrapped on a derived relation, say so.** Record in the
  query's `dcterms:description` which hop was wrapped and why, because the
  column's attribution is then a decision rather than a reading.

A row marked `shui:readOnly true` cannot have values removed through the form
at all, so the deletion half of the column does nothing there - the chip is the
only thing it still drives.
