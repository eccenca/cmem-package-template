# Graph architecture

A package shipping instance data wants four graphs, each in its own file and
each labelled after the file that ships it:

| graph | role |
|---|---|
| vocabulary | the ontology; `register_as_vocabulary: true` |
| shapes | the SHACL catalog; `import_into` the Corporate Memory shapes graph |
| data | the instances the package's workflows rebuild; shipped holding only its own description |
| integration | the root users open - imports the vocabulary and the data; read-only |

A graph of data only the users produce - their own records, kept across
updates - is not one of these: it is not shipped, and a workflow creates it
(see "Listing a graph is what makes the package own it" in the skill). The
integration root may import it like any data graph.

## The integration root is read-only

The integration graph is the root of the package: users open it to see the
vocabulary and the data together, and it holds nothing but its own description
and its `owl:imports`. **Nothing writes into it** - no workflow, and no form
save. A statement saved into the root sits apart from the data it belongs to,
in a graph no workflow owns and no uninstall of a data graph takes along.

Between the data graphs and the root there may be **intermediate integration
graphs**: a graph that imports parts and also holds data of its own - a
product's graph holding the product and importing its components, say. Such a
graph integrates, but it is not read-only; users may edit the data it holds.
The read-only rule is for the root alone.

## Keep the `owl:imports` in the integration graphs

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
