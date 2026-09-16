---
name: build-projects
description: Work with the Corporate Memory DataIntegration projects a package ships - export one back into the repository, read the exported XML, choose the right workflow task, and test a workflow against an instance. Use when a build project is added, re-exported, edited or debugged, or when deciding how to get data into a graph.
---

# Build projects inside a package

A package ships DataIntegration projects the way it ships graphs: as files
declared in `cpa-manifest.json`. The manifest entry names a **`.zip`**:

```json
{ "file_path": "build/<project-id>.zip", "file_type": "project", "project_id": "<project-id>" }
```

but what the repository holds is the **extracted** directory
`build/<project-id>/`, so that changes are diffable in git. `cmemc package
build` and `package install` re-zip it on the fly. Do not commit the `.zip`, and
do not change the manifest to point at the directory.

## The live instance is the source of truth

These files are exports. Authoring happens in the Corporate Memory UI, and the
repository holds the result. Hand-editing an XML is legitimate - it is often the
quickest way to rename something consistently - but it is only real once
installed back into an instance and exported again.

```bash
cmemc project export --extract --replace --without-userdata \
    --output-dir <package_dir>/build <project-id>
```

**`--without-userdata` is not optional in practice.** Without it, `config.xml`
carries timestamps and account IRIs, so every round-trip produces a diff that
says nothing about what changed.

**`--replace` is not optional either, from the second export onwards.** Without
it, cmemc finds the directory already there, writes an error to stderr and
**still exits 0** - so the export silently does nothing and the directory you
then diff still holds the previous one. Since the whole point is a round trip,
that is every export but the first.

## What an export looks like

```text
build/<project-id>/
├── config.xml       project metadata, prefixes, variables config
├── variables.xml    project variables
├── tags.xml         tags used by tasks
├── dataset/         one XML per dataset
├── transform/<rule-id>/{rules.xml,dataset.xml}
├── workflow/        one XML per workflow
├── custom/          one XML per custom task
└── resources/       files the project reads (only if it has any)
```

Task filenames carry a generated suffix (`Cleardataset_11d6044…xml`); the
identity that matters is the `id` attribute inside, and workflows reference
tasks by that id.

A workflow is a graph of `<Dataset>` and `<Operator>` elements, each with
`inputs`, `outputs` and `dependencyInputs`. `dependencyInputs` is how you
sequence two branches that exchange no data - the second operator waits for the
first without reading from it.

## Choosing a task

Custom tasks are `<CustomTask id="…" type="…">`. The types worth knowing:

| `type` | Use it for |
| --- | --- |
| `sparqlCopyOperator` | a CONSTRUCT from one graph into another - the workhorse |
| `sparqlUpdateOperator` | an INSERT/DELETE against a graph |
| `tripleRequestOperator` | piping an RDF file or endpoint straight into a graph |
| `clearDataset` | emptying a target before a rebuild |
| `Scheduler` | running a workflow on a schedule |

A plugin contributes its own type (`cmem_plugin_nextcloud-List` and so on); the
package must then declare that plugin as a `python-package` dependency in the
manifest.

**Avoid hand-authoring a transform.** A `transform/<rule-id>/rules.xml` mapping
tree is the one part of DataIntegration authoring that is genuinely painful to
write by hand. If the source can be produced as RDF - generated Turtle, an
endpoint - `tripleRequestOperator` reaches the same result without a mapping
tree. Build transforms in the UI and export them.

## A SPARQL finding worth not rediscovering

Joining on a label by comparing strings does not use the literal index:

```sparql
# scans every candidate literal - never finished on ~120k labels
FILTER(STR(?cityLabel) = STR(?referenceLabel))

# binds the plain literal and looks it up as a bound object - seconds
BIND(STR(?cityLabel) AS ?plainName)
?reference rdfs:label ?plainName .
```

## Testing a workflow

Install first, then run the workflow - `package install` replaces the graphs the
package ships, so a test fixture inserted beforehand is wiped by the install
that was supposed to test it.

```bash
cmemc workflow execute <project-id>:<workflow-id>
cmemc query execute <file.sparql> --accept text/csv
```

A workflow is addressed as `<project-id>:<workflow-id>`; `cmemc workflow list`
shows what is there. There is no `cmemc project execute`.

If `cmem-build` is connected as an MCP server it can inspect projects, tasks,
datasets and workflows directly, which is faster than reading exported XML. Note
what it is configured to do: read-only in some setups, and it covers
DataIntegration only - SPARQL and Graph Store access come from the separate
Explore server.

## Relative IRIs do not survive import

Corporate Memory resolves a relative IRI against the **importing server's
filesystem**: `<resources/poster.png>` becomes
`<file:/root/graphdb-import/resources/poster.png>`. Reference project resources
from a graph with an absolute URL, and treat that URL as the thing to rewrite
when the package is installed on a different deployment.
