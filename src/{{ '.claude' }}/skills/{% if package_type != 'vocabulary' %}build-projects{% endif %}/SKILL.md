---
name: build-projects
description: Work with the Corporate Memory DataIntegration projects a package ships - export one back into the repository, read the exported XML, split projects by lifecycle, name ids and labels, write descriptions, tag tasks, keep namespaces in project variables, write migrations, choose the right task, and test a workflow against an instance. Use when a build project is added, re-exported, edited, tagged, documented or debugged, when a namespace or a migration is needed, or when deciding how to get data into a graph. The design of the workflows themselves is the workflows skill.
---

# Build projects inside a package

A package ships DataIntegration projects the way it ships graphs: as files
declared in `cpa-manifest.json`. The manifest entry names a **`.zip`**:

```json
{ "file_path": "projects/<project-id>.zip", "file_type": "project", "project_id": "<project-id>" }
```

but what the repository holds is the **extracted** directory
`projects/<project-id>/`, so that changes are diffable in git. `cmemc package
build` and `package install` re-zip it on the fly. Do not commit the `.zip`, and
do not change the manifest to point at the directory.

## The live instance is the source of truth

These files are exports. Authoring happens in the Corporate Memory UI, and the
repository holds the result. Hand-editing an XML is legitimate - it is often the
quickest way to rename something consistently - but it is only real once
installed back into an instance and exported again.

**Push the edit up before pulling anything down.** `--extract` deletes the
target directory before writing (`shutil.rmtree`), so an export run over
hand-edited files destroys them and leaves the server's untouched state in their
place, uncommitted and without an error. The order is:

```bash
cmemc project import <package_dir>/projects/<project-id> <project-id>   # your edits go up
cmemc project export --extract --replace --without-userdata \
    --output-dir <package_dir>/projects <project-id>                 # the result comes back
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
projects/<project-id>/
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

## Build projects by lifecycle

A package ships up to three build projects, split where the lifecycle differs:

| project | holds | runs |
| --- | --- | --- |
| `<prefix>-bootstrap` | setting up an environment: master data and curated graphs' first fill, a taxonomy from its SKOS XML, migrations | once per environment, again after a reset |
| `<prefix>-demo` | the example files, their transforms, learning demos, the count tests | on demand, never in production |
| `<prefix>` | the operational workflows: consume (read sources) and produce (inference, checks, exports) | all the time |

- **The prefix is the package id's infix without a trailing `-demo`**: package
  `acme-orders-project` → `orders`, `orders-bootstrap`, `orders-demo`. *Whoever meets a project in the workspace knows which
  package it belongs to; the demo is a project of its own, so a `-demo` in the
  prefix would read `…-demo-demo`.*
- Consume and produce stay together: they share datasets and rule blocks, and
  tags tell them apart.
- **Several operational projects** `<prefix>-<purpose>` only where each serves a
  usage context that is called by name from outside - a trigger, an assistant
  skill, an instance. *Renaming a project breaks every trigger and skill that
  calls it.* Bootstrap and demo stay one each.
- **Example data has flaws**: one or more for every check the package shows,
  each documented with its count (DOCUMENTATION.md) and guarded by the count
  check. Record each flaw's provenance for maintainers - *generator* (which seed
  or rule) or *source* (which source, which cached snapshot). *A demo shows the
  checks working; when a count changes, the provenance tells a defect
  (generator) from a changed source.*
  - **Also a check that only guards against hand edits gets a flaw**, planted
    needle-in-the-haystack style: one inconspicuous record deep inside an
    otherwise normal source, placed where it stays local (on something no other
    check reads), with every count that moves with it re-measured.
  - **A documented flaw counted exactly is a real violation**: it may show up in
    validation; the exact count makes any further violation fail the test.
- **The demo is guarded**: its entry workflow first reads a global or project
  variable `environment` (`dev`, `qa`, `stage`, `prod`; set by the bootstrap)
  and cancels on `prod`, with the reason in the report. Migrations and checks
  may read it too.

## A project maintained from the repository says so

Every build project carries, next to the package's tag, the project tag
`from-repository`, and its description says in one line that it is maintained
from the package's repository: edit it in the UI only if you export it back,
because the next `task import` replaces the whole project. *In a workspace
shared by people and an agent, the workbench filter shows which projects an
import will overwrite. The unit is the project: a tag on single tasks would make
the untagged tasks of the same project look safe to edit, and they are not.*

## Ids and labels

- Ids are readable kebab-case, chosen at creation, never generated. Workflows
  and processing tasks are verb-object (`create-entities`); datasets are a noun
  (`staged-book`). No `WF_` prefix.
- **Ids and labels name the intention**, not the format: `staged-book`, not
  `book-json`.
- Labels are sentence case and use the same words as the id.
- Rename a generated id only while nothing outside the project references it.
- **Never give a workflow and a task the same id**, even of different types: the
  project can no longer be loaded.

## Descriptions

- **Every task and workflow has a description.** Its first sentence stands
  alone - lists show only it.
  - A task: that sentence plus at most one paragraph on why it exists and what
    breaks without it. A SPARQL task says why no construct does the job.
  - A workflow run by hand: its full instruction set - the first sentence, then
    plain-text sections `Input:`, `Preconditions:`, `What it does:`, `Result:`,
    `On failure:`; lists with `- `.
- **A workflow run by hand gets a skill of exactly the same name.** The skill
  never repeats the description; it only adds the decision, the confirmation
  and the check.
- What no single node can say goes into a sticky note on the canvas (the
  `workflows` skill).

## Task tags

A tag names the role a task plays, never its content. Tags are filters: each
axis exists because someone searches by it, across all packages of a workspace.

| axis | tags | use case |
| --- | --- | --- |
| position (datasets) | `source`, `target` - both on a dataset the build reads and writes; only on persistent datasets, and by effect: a graph a SPARQL task writes gets `target` even when no workflow node uses its dataset as a target; a temporary dataset gets none (`temporary` says it) | find every dataset a build reads or writes persistently - including what SPARQL tasks write |
| writes (workflows) | `writes-<graph role>`: `writes-term`, `-entity`, `-rule`, `-inference`, `-categorization`, `-relation`, `-integration`, `-settings`, `-views`, `-shapes` (the roles of the `package-content` graph table), one per role the workflow writes - a parent carries the union of its phases; none for temporary graphs | find every workflow that writes a kind of graph, in every package - a workflow writing three roles is found by each of the three |
| warning (datasets) | `reads-imports` - the dataset's graph imports others, so a read expands every import, whatever the graph's role | see at a glance which reads see more than one graph, and are expensive |
| lifetime | `temporary` (not persistent: in-memory or cleared per run, no position tags), `rebuilt` (a persistent graph every build clears and writes again; keeps `source`/`target`), `clean-up` | find what may be cleared without loss; everything without a lifetime tag must survive a release |
| data kind | `master-data`, `production-data`, `demo-data` | find all data of one kind - every demo source, say - whatever the build does with it |
| started by | `by-person`, `by-skill`, `by-form` (a form save or button), `by-schedule`, `by-workflow` (only nested), `by-api` (an external system through the REST API or cmemc) | know who runs it before changing it |
| lifecycle | `bootstrap`, `run-after-import`, `migration`, `demo` | find what runs once, after an import, or never in production |
| external systems | `consume`, `produce`, plus the system's name (an input delivered through the MCP is `consume`) | find everything touching one external system |
| bookkeeping | `metadata`, `generated` (written by a script, not to be edited in the UI), `shared-logic` (rule blocks) | know what not to edit by hand |

- **Graph roles, not graph names**, in `writes-`: the package is named by the
  project tag. *A `writes-products` would filter together different graphs of
  different packages.*
- **Tags are a set**: DataIntegration keeps no tag order. A checker compares
  sets; no rule fixes an order.
- At most one tag per axis, except position (`source` + `target` on one dataset)
  and `writes-` (one per role written): both describe what the task does, and a
  task can do several things.
- `entry-point` marks the workflow to open first. Processing steps stay
  untagged.
- **No tag for what a flag already says**: a dataset the build only reads gets
  DataIntegration's `readOnly="true"`, never a `read-only` tag. *The workbench
  search filters on the flag, and the flag also refuses a write; a tag next to
  it is a second source that drifts.*
- The project itself carries the package's tag and `from-repository` (above).
- Create, assign and delete tags with the DataIntegration MCP server's tag
  tools, or in the UI, and export afterwards.

## Namespaces in one place

- Every namespace **decided per instance** is a **project variable**: one base
  variable (`dataNamespace`), graph variables as templates over it
  (`{{project.dataNamespace}}entities/`). A shipped graph's IRI,
  fixed by the manifest, stays written out. *Whoever installs on a new instance
  changes one place instead of searching the tasks; what never changes gets no
  variable to misconfigure.*
- **Not the vocabulary namespace**: templates resolve only in plugin
  parameters, and the vocabulary's IRIs also sit in mapping targets, type URIs,
  source paths and restriction patterns. The vocabulary namespace stays written
  out.
- Datasets take it as `<Template name="graph">`; SPARQL tasks as
  `PREFIX x: <{{project.x}}>`; transforms as template constants.
  A template inside a rule block's `constant` resolves; a changed value takes
  effect after `cmemc project reload`; an export keeps
  `{{project.x}}`.
- Document instance-decided variables as preconditions of the workflows that
  use them.
- **Jinja trap**: a SPARQL task's text may contain no `{{`, `{%`
  or `{#` besides the variables.
- **Template trap**: give a task parameter's template in the task JSON's
  `templates` field, not in `parameters`. A URI rule that is a bare
  `concat(constant, path)` may lose its template; safe shape:
  `concat(constantUri <graph>, urlEncode(path))` with the segment in `glue`, or a
  namespace as `constantUri` in angle brackets. After a transform edit, export
  and count the `<Template>` elements.
- **Execution variables** resolve in SPARQL task templates per run, but not in a
  task parameter template, which resolves when the task is saved. To use one
  there, feed an Evaluate template task into the operator's configuration port.

## Migrations

A migration is a DataIntegration workflow, one per migration, id
`migrate-<NNN>-<what-it-migrates>`, tag `migration`, in the bootstrap project:

1. **check** - ASK whether it is needed (old pattern present, not yet recorded
   in the graph description); otherwise end with the reason in the report;
2. **back up** the affected graphs into a backup graph;
3. **migrate** - constructs first (the `workflows` skill), SPARQL update only
   where no construct can;
4. **verify** - counts before and after, and validation, both in the report;
5. **record** the id and date in the graph description.

A parent workflow `migrate`, tagged `run-after-import`, runs them all in order.
Test each twice from a pre-change backup: the results must be isomorphic.
Production data and master data maintained by users always get a migration;
package definition is replaced by the release, demo data by re-running the demo,
imported master data by re-import.

**Applied migrations are history**: a migration already run as a script stays as
it is; only new ones become workflows. *Nobody runs an applied migration again,
so a workflow copy would only be maintained.*

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
cmemc workflow execute --wait <project-id>:<workflow-id>
cmemc query execute <file.sparql> --accept text/csv
```

**`--wait` is what makes this a test.** Without it cmemc sends the start signal
and returns, so the command exits 0 whether the workflow succeeded or failed,
and the query on the next line reads a graph that is still being written.

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
