---
name: workflows
description: Design the DataIntegration workflows of a Corporate Memory package - CMEM constructs before SPARQL, the minimal input per task, linking natively, optimising a build, phases and in-memory hand-off, responsibilities between tasks and graphs, sticky notes, the waterfall canvas layout (task layout), testing, and the DataIntegration mechanics found on the way. Use when a workflow is created, split, laid out or reviewed, when a task is chosen or replaced, or when deciding how a build step gets its data into a graph.
---

# Workflows in a package's build project

How to design the workflows a package ships. The `build-projects` skill holds the
project around them - lifecycle, ids, descriptions, tags, namespaces,
migrations, and the export round trip; this skill holds the flow.

## Build from constructs, read the minimal input

- **Use CMEM constructs** - Knowledge Graph and in-memory datasets, transforms,
  linking tasks, nested workflows, the Clear dataset operator - so a reader
  understands a workflow in the workbench and can change it without code. A
  SPARQL Update or CONSTRUCT task replaces a construct only where no construct
  can do the job (check `plugin_list` first), and its description says why.
- **Each task reads the minimal input**: the graph that holds its data, never
  the integration graph - a Knowledge Graph dataset over an integration graph
  expands every import. Where a task needs data from several graphs, stage it
  with constructs (a transform into an in-memory dataset).
- **Link natively instead of joining in SPARQL**: let the transform write the
  raw key as a working property (`urn:<project>:working:<key>`), let a linking
  task (`equality`) write the real link, and delete the working property in a
  final clean-up step.

## Optimising a build

- **Measure before optimising.** A workflow run's report has a timestamp per
  node, nested workflows included; the gap between two nodes run one after the
  other is the later one's runtime. Find the dominant node first.
- **Keep external lookups out of the rebuild.** A transform that calls a service
  per entity (geocoding, REST) is the dominant cost. Look up once into a
  persistent graph the build does not clear, and on later runs only what is
  missing: the cache records per resource the key it was looked up for, also
  when the lookup found nothing; the current and the recorded key are staged
  into an in-memory dataset, and the lookup transform reads only the resources
  without an entry for their current key (a `FILTER NOT EXISTS` in its source
  restriction works on an in-memory dataset). One SPARQL update first deletes
  the entries of moved or gone resources. A cache of a remote service is derived
  data under that service's licence (the `package-content` skill).
- **Type every input.** A Knowledge Graph dataset read with a type reads only
  those resources; an untyped read takes every subject of the graph, the graph
  description's blank nodes included.
- **A source restriction sees only the dataset's own graph.** A pattern that
  needs another graph (the vocabulary's `rdfs:subClassOf*`) matches nothing on a
  single graph, with no error. Replace it with a type, or stage the entities.
- **Compare graph sizes after narrowing an input**, not only the minted IRIs.
- **Clear on the first port of the target node.** "Clear dataset" on the first
  input port of the graph node, the data on a later port: the graph is emptied
  before the write. A separate clear node is needed only when several nodes
  write the dataset - then a dependency edge from it to every writing node.
- **Don't order what needs no order.** Independent sub-workflows get no
  dependency edges between them.

## Phases

- Split a workflow into phases when its parts can be named separately or the
  canvas needs edges doubling back.
- The parent holds only phase nodes (nested workflows), ordered by
  `dependencyInputs`, with no data edges.
- **At most two levels of nesting**: a phase may split once more into
  independent units of the same kind (one workflow per source in a load phase),
  so every canvas fits on a screen.
- **Hand data between phases through in-memory datasets where possible.** A
  workflow-scoped in-memory dataset is shared with nested workflows for the
  same task id and removed after the run. Limits: default graph only,
  `maxInMemorySize` fails the run when exceeded, and anything read after the run
  must be persistent.
- A dataset with `clearGraphBeforeExecution` clears once per run, not in each
  nested workflow that writes it.

## Responsibilities

1. **One writing dataset per persistent graph.**
2. **Stage, then publish.** A transform writing straight into a Knowledge Graph
   dataset can leave partial results despite `abortIfErrorsOccur`. Map into an
   in-memory dataset, check, then copy into the graph.
3. **A workflow that clears a graph restores what the package ships in it** (the
   graph description, a scheme, an icon) - only where people look; scratch
   graphs read only by workflows need none.
4. **Helper triples are retracted last.**
5. **One task, one job, one output**; a task whose results belong in two graphs
   becomes two tasks.
6. **A curated graph seeded while empty never receives later source
   additions**: carry new source data into it by a migration (the
   `build-projects` skill), and compare the seed with the curated graph after a
   source change.
7. **Graphs created at run time sit under a package-owned IRI prefix** (one
   graph per product, its check graph). The package ships a workflow `clean-up`
   (tag `clean-up`) that deletes every graph below the prefix the manifest does
   not ship. A stack test calls it **before the uninstall** - afterwards the
   workflow is gone with its project - and once more **right after every fresh
   install**, for graphs an older install left. *Uninstalling the package leaves
   these graphs behind, because the manifest does not list them, and a
   reinstalled test would count the old ones; whoever uninstalls by hand runs
   `clean-up` first.*
   **Backups of user data are not run-time graphs of the package**: a
   migration's backup sits next to the data it backs up, `clean-up` never
   touches it, and the migration's report names it and how to delete it once
   checked. *A fault found a week after a migration still has its way back,
   across an uninstall.*

## Sticky notes

- **Sticky notes** say what no single node can say and carry non-obvious
  information, workarounds and complex patterns. A parent holds at most one
  note, explaining its crossings.
- **A read-back gets one note**: a workflow that reads a graph it wrote earlier
  in the same run shows the dataset twice in that graph's lane. One yellow note
  per workflow says why it reads back (what the later step needs from the
  earlier one) - no note per node, no second dataset for the same graph. *Someone
  reading the canvas tells the read from the write and does not remove the
  read-back as a mistake; the edge direction already shows that it reads.*
- **Two colours**: yellow `#ffd54f` = read this; a warning colour = temporary (a
  workaround with its ticket: key, what it works around, what to do once fixed,
  the ticket as a Markdown link). In a note a Markdown link and a bare URL are
  clickable.

## Canvas layout: a waterfall

`task layout` lays out every workflow of the package's build projects
(`bin/layout_workflows.py --write`, rewriting only `posX`/`posY` of the exported
workflow XML); `task layout:check` reports a workflow that departs from the
layout without changing it. Neither runs in `check:offline` and `task export`
calls neither: run `task layout` after an export in which nodes were moved, and
review the diff - a deliberate arrangement is yours to keep. A package that
wants the layout as a gate adds `task: layout:check` to its `check:custom`.

- **x = order**: column = longest path over data, config and dependency edges,
  so every edge points right; 300 px columns, 200 px rows.
- **y = tier, then lane.** Tiers top to bottom: *input* (read from outside the
  run - a read of a graph the same workflow writes sits in that graph's lane
  instead) → *working* → *target* (persistent graphs written). Within the target
  tier one swimlane per persistent graph, ordered by which is written first. An
  operator sits in the lane of what it writes. Empty lanes take no space.
- **Configuration tier on top**: a branch that only reconfigures a step sits in
  a lane above the flow.
- **Interface nodes**: a replaceable input in column 0; a replaceable output in
  its own lane at the very bottom, in the last column.
- **No edge runs upward within a lane.**
- **Planarity is the goal within those rules**: a crossing that survives is
  accepted by `layout:check`, and a yellow note explains it.
- **Port order counts as a crossing**: the predecessor feeding the first input
  port sits above the one feeding the second.
- **Rule canvases too**: place the node of the first port above the node of the
  second. A comparison with `reverse=true` draws the source into the second
  port.
- **Sticky notes** sit 50 px above the lane of the step they explain.

## Testing

The commands for running a workflow against an instance are in the
`build-projects` skill. What to test:

- Test workflows on a test instance, never on production data.
- On a shared development instance: point an instance-decided graph variable at
  a throwaway graph for the run, restore it and delete the test graphs in a
  `finally`, check that every rejected input leaves the triple count unchanged,
  and run it from a task so others run the same thing.
- After any URI rule touching a column path, count source rows against minted
  entities.
- **Demo sources come from a cached copy; live lookups get their own live
  test.** *The demo and its counts run offline and repeatably; a workflow whose
  job is to query a live service is tested against that service, outside the
  demo counts.*
- **A generator over a remote source checks against its cache**: without the
  cache its `--check` reports "not checked" and passes - it never queries the
  remote source. *`task check` runs offline and in CI.*

## Mechanics found on the way

- **A spreadsheet path like `#J` is a column letter.** In a URI rule an empty
  cell yields no URI and the row is skipped silently.
- **Skipping source rows on purpose**:
  `concat(uri, regexReplace(filterByRegex(key, negate=true), "^.*$", ""))`.
- **An absent object still links**: a hash-based URI of an absent key is the
  hash of nothing. Gate the URI on the key.
- **An object mapping's link is evaluated from the parent's side**: a child URI
  rule with backward paths (`\../key`) mints the right child IRIs, but the
  parent→child link hashes differently. Give the object mapping a working
  property as target (`urn:<project>:working:<name>`), let the child state the
  link back from `\../` values, and remove the working property before
  publishing. *Never an empty target: DataIntegration resolves it against its
  working directory and writes a `file:` predicate into the data.*
- **Every DataIntegration write to a graph adds `<graph> a di:Dataset`.**
- **Cross-graph reads in a SPARQL update task**: `USING <g1> USING <g2>` before
  `WHERE`, `GRAPH <primary> { }` around DELETE/INSERT. Name every graph
  explicitly.
- **SPARQL scoping in templated queries**: a FILTER inside an OPTIONAL or UNION
  branch does not see variables bound outside it - write per-row values into
  each branch; put label lookups inside the candidate OPTIONAL; bind a joined
  variable without OPTIONAL before an OPTIONAL `GRAPH ?g` label lookup, or each
  row fans out.
- **`GROUP_CONCAT` is fed sorted** from a sub-select with `ORDER BY`.
- **SPARQL Select with run-time input**: input entities reach the template only
  with "use fallback RDF dataset". A replaceable JSON input and output make the
  workflow callable with the result returned inline.
- **A SPARQL select task needs a dataset on its input** even when it reads no
  data ("did not receive a SPARQL endpoint"). Connect the target Knowledge Graph
  dataset.
- **`replaceableInputs` takes the dataset task id**, not the workflow node id; a
  node id is silently dropped.
- **A Binary file dataset yields its reference even when the file is missing**;
  guard with Get project files and a regex.
- **Binary input through the MCP**: `workflow_execute` carries no binary data and
  runs a replaceable input on empty JSON when none is given. Deliver a binary
  through a fixed inbox file in the project.
- **Rule blocks**: one value-producing expression with ports and per-reference
  bindings. It fits where a single non-trivial expression is duplicated three or
  more times with only leaf constants or paths differing.
