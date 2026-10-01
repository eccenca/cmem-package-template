# Graph architecture

A package shipping instance data wants four graphs, each in its own file and
each labelled after the file that ships it:

| graph | role |
|---|---|
| vocabulary | the ontology; `register_as_vocabulary: true` |
| shapes | the SHACL catalog; `import_into` the Corporate Memory shapes graph |
| data | the instances; shipped holding only its own description |
| integration | the entry point - imports the vocabulary and the data |

## Keep the `owl:imports` in the integration graph

A data graph that imports the vocabulary itself cannot be explored
independently of it, and every pipeline run would have to preserve that import
statement.

The price is that **no inference is available in the data graph**: types and
sub-properties must be asserted explicitly by whatever writes it. Budget for
that when designing the pipeline, because the alternative is discovering it
when a query over the data graph returns nothing.

## Describe the data graph even though it ships empty

Describe it as a `void:Dataset` with publisher, rights, creation and
modification dates and a version. Corporate Memory then renders a full
metadata form for it rather than a bare IRI.

That description is also what makes the graph ownable: a file holding nothing
but it is enough for the manifest to list, which is what gets the graph created
on install and removed on uninstall.

## A clearing dataset deletes the shipped description

**A dataset writing with `clearGraphBeforeExecution` deletes the graph
description the package installed.** Every run wipes the label, comment and
imports, and nothing restores them.

So anything the package ships into a graph the workflow clears has to be
written back by a final post-processing step in that workflow. The symptom is a
graph that was fine after install and has lost its metadata - and its
`owl:imports` - after the first run.
