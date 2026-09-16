# Three authoring skills for generated packages

Date: 2026-09-16

## Goal

Ship three skills into every package generated from this template, so that the
knowledge four packages have each written down for themselves — and that
seventeen Claude sessions show being re-derived — arrives with the package
instead of being reconstructed per repository:

1. **`package-content`** — the manifest as a contract, and what breaks a build.
2. **`build-projects`** — DataIntegration project exports inside a package.
3. **`shapes`** — the shape catalog that drives the CMEM Explore UI.

## The evidence this is built from

A survey of every repository on this machine generated from this template: 38
packages (24 `vocabulary`, 14 `project`), plus 17 Claude session transcripts,
18 MB, covering 6 of them.

### Version drift

34 of the 38 sit on template version v1.2.0 or older, three of them on v0.7.0
or v0.9.7; the current release is v1.5.0. Only three packages are near current.
`copier update` is, in practice, not run. This does not change what the skills
should say, but it does set expectations: what ships here reaches new packages
immediately and existing ones only when somebody pushes an update through the
fleet.

### The layout has evolved past the template

| Layout | Packages |
|---|---|
| `<package_dir>/graphs/` + `<package_dir>/projects/` | 4 |
| `<package_dir>/explore/` + `<package_dir>/build/` | 3 |
| flat, an ontology `.ttl` beside the manifest | the rest |

The three most recently maintained packages — `fearskaper-fame`,
`ecc-isms-project`, `eccenca-infrastructure` — all use `explore/` for graphs and
`build/` for project exports, mirroring the two CMEM applications. The template
scaffolds neither; it ships `example.ttl` at the package root.

**Decision: describe both, prescribe neither.** The skills explain that older
packages use `graphs/` + `projects/`, that newer ones use `explore/` + `build/`,
and that either is fine as long as the manifest matches. The template keeps
shipping `example.ttl`. Changing the scaffolded layout is a separate decision
and is out of scope here.

### The same knowledge is re-derived per package

Four packages carry a hand-written `CLAUDE.md` — 320, 247, 95 and 70 lines —
independently restating the same facts: the manifest's two-way match, why
`README.md`/`CHANGELOG.md`/`LICENSE` are symlinks, that `package_version` stays
`0.0.0` while the real version comes from `git describe`, that `Taskfile.yaml`
is generated and additions belong in `TaskfileCustom.yaml`, and the same
six-row table of tasks. Two packages hand-wrote validation scripts. Only 3 of 38
have a `TaskfileCustom.yaml` at all.

That repetition is the case for these skills: it is knowledge about *packages*,
not about any one package.

### Friction the transcripts show

**Manifest.** Undeclared files are the recurring build failure.
`cmemc graph export` leaves `*.ttl.graph` and `*.ttl.imports` sidecars, neither
extension legal in a manifest; they must be transcribed — `.graph` holds the
graph IRI, `.imports` lists the graphs that import *this* one — and then
deleted. A `.DS_Store` fails the build the same way
(`PackageContentError: Some paths are not described in the manifests file_spec
list`); a dangling symlink fails the other direction (`Some file_spec paths are
not present in the package`). Further enforced rules seen in practice: at most
one directory level, lowercase path segments of 2–30 characters, and only
`.ttl`, `.zip` and `.png` besides the three literal text filenames.

**Licensing.** `metadata.license` accepts open source and open data identifiers
plus the `LicenseRef-scancode-unknown` sentinel, and **none of them means
proprietary**. The marketplace rejects a package that ships a `LICENSE` file
while the identifier is unspecified. The working combination for an internal
package — mapped empirically in `ecc-isms-project`, at the cost of a failed
build and a session spent on it — is `LicenseRef-scancode-unknown` together with
**no `LICENSE` file** in the package directory.

**Build projects.** Export with `--without-userdata`, or `config.xml` churns
with timestamps and account IRIs on every round-trip. The extracted directory is
what git holds; the manifest names the `.zip`, and `package build` re-zips on
the fly. Hand-authoring a `mappingRule` tree in XML is "the one part of DI
authoring that is genuinely painful", which is why generating Turtle and piping
it through `tripleRequestOperator` beat writing a transform task. A join written
as `FILTER(STR(?a) = STR(?b))` scanned ~120k reference labels and never
finished; binding the literal first and looking it up as a bound object
completed in under two seconds.

**Shapes.** The largest body of re-derived knowledge, and the least documented
elsewhere:

- `shui:WidgetIntegration_group` is optional in the schema and mandatory in
  practice — without it the widget renders above the form instead of in it. Only
  ten of sixteen widget integrations on a stock deployment set it, so copied
  examples mislead.
- `shui:TableReport_hideHeader` hides the search box *and* the column titles
  together; `shui:` has no search-specific property, so the two cannot be
  separated.
- A node shape's user-facing text is `rdfs:comment`, not `shacl:description` —
  settled by the platform's own catalog, where 21 node shapes use the former
  and one the latter.
- URI templates interpolate `{label}` for named things and `{uuid}` for join
  resources that have no name of their own. A generated label rules out
  `{label}`, not a template.
- A derived field carries `shui:readOnly` and neither `minCount` nor
  `shui:showAlways`: both address a user who is expected to act, and nobody can
  type into a generated field.
- `shui:managedClasses` lists **root classes only**. Introducing a superclass
  means adding it and removing the classes that became its subclasses; new
  subclasses are never added. Navigation lists, by contrast, belong on whichever
  classes have distinct column sets, managed or not.
- House rule, stated by the user: every query a shape references lives in the
  shape catalog beside the shapes that use it. A catalog pointing at a query in
  another graph is half a deliverable.
- A plain SHACL engine misreads `shui:inversePath` and `shui:valueQuery`: it
  evaluates the forward path and invents violations. Those property shapes must
  be stripped before validating, which is exactly what one package's
  hand-written `validate.py` does.

## What gets built

### `package-content`

Ships to **every** generated package.

Covers: the two-way match and both error messages; the sidecar transcription
and deletion ritual, with `import_into` documented in its counter-intuitive
direction; `.DS_Store` and dangling symlinks; the path and extension rules; the
licence matrix including the internal-package combination; why
`package_version` stays `0.0.0`; the symlink arrangement and why
marketplace-facing prose belongs in `DOCUMENTATION.md`; and the offline loop —
`cmemc package build` into a temporary directory catches manifest and content
mismatches but **ignores RDF syntax errors entirely**, so it is not a validation
pass and must not be described as one.

Deliberately does **not** restate the manifest field reference. It names
`manifest_schema` and `manifest_check` from the `cmem-marketplace` MCP server as
authoritative, `manifest_example` and `package_build_guide` as the worked
examples, and the template's own README as the fallback when no MCP server is
connected. `CLAUDE.md` already records what happens when one fact lives in two
places — the cmemc pin — and this skill is written so there is nothing to drift.

### `build-projects`

Ships to **project packages only**.

Covers: `build/<project-id>/` as an extracted export while the manifest names
the `.zip`; `cmemc project export --extract --without-userdata` and why the flag
matters; the task-type subdirectories (`dataset/`, `transform/<rule-id>/`,
`workflow/`, `custom/`, `resources/`) beside `config.xml`, `variables.xml` and
`tags.xml`; that the live instance is the source of truth, so a hand-edited XML
is only real once installed back; which operator to reach for
(`tripleRequestOperator`, `sparqlCopyOperator`, `sparqlUpdateOperator`,
`clearDataset`, `Scheduler`) and the warning about hand-authoring a mapping
rule tree; the literal-index join finding; and testing a workflow **after**
install, because install replaces the data graph and would wipe a test fixture.

### `shapes`

Ships to **project packages only**.

Covers the catalog as something that drives the Explore UI as much as it
validates: node and property shapes, property groups, URI templates, read-only
and derived fields, the WidgetIntegration → TableReport → SparqlQuery chain,
`shui:managedClasses` and navigation lists, the queries-in-the-catalog rule, and
the validation caveat together with the property-coverage check that finds
predicates written on instances that no form can show.

This is the one skill whose material exceeds a single readable file. It splits
into `references/` sub-files — widgets, navigation, validation — with `SKILL.md`
holding the model and routing to them.

### House style versus general rule

Everything that holds for any package — the manifest contract, `shui:`
mechanics, export flags, the SHACL caveat — is stated as fact. The eccenca
conventions the newest packages converged on — the six property groups and their
orders, `rdfs:comment` on node shapes, `skos:editorialNote` in English for
design reasoning, bilingual labels where a package is bilingual — ship as
**recommended defaults a package may override**, and are marked as such. No
package-specific detail (ISMO's class clusters, the Gig Ontology's decisions)
is prescribed; such cases appear only as illustrations.

### Conditional shipping

`build-projects` and `shapes` are dropped for vocabulary packages by a Jinja
filename conditional on `package_type != 'vocabulary'` — the mechanism where a
name rendering empty removes the file. This matches the evidence: every
`build/` and `explore/` tree in the fleet is in a project package, while the 24
vocabulary packages hold one ontology `.ttl` and an icon.

Upstream only ever applies such a conditional to a *file* name, and a skill is a
directory, so the mechanism was verified before being designed in: rendering a
`skills/{% if package_type != 'vocabulary' %}shapes{% endif %}/SKILL.md` for both
answers produces the directory in a project package and **nothing at all** in a
vocabulary one — not even an empty directory.

### Where the rules file points

`src/{{ '.claude' }}/rules/copier-template.md` gains a short paragraph naming
the shipped skills, so an agent learns they exist before it needs one. The
paragraph is written so it stays true for a vocabulary package, where two of the
three are absent.

## Verification

`task check` cannot exercise a skill's content; what it can assert is that the
skills ship correctly. A new offline task, `check:skills:case`, modelled on
`check:hook:case`, asserts in a rendered case that:

- every expected `SKILL.md` exists, its YAML frontmatter parses, and its `name`
  matches its directory name;
- `build-projects` and `shapes` are present in the project test case and
  **absent** in the vocabulary test case;
- no unrendered Jinja remains in any shipped skill file.

Everything beyond that is a hand read. The spec does not pretend otherwise.

## Non-goals

- **No `validate.py` shipped.** Two packages hand-wrote one and it is the most
  duplicated artifact after `CLAUDE.md`, so this is a real candidate — but it is
  executable content with its own test burden, and it belongs in its own change.
- **No change to the scaffolded package layout.** `example.ttl` stays.
- **Nothing about the 34 packages on old template versions.** That is a fleet
  update problem, not a template change.
- **No new copier questions.**
- **No `CLAUDE.md` written into generated packages.** The existing decision
  stands: agent support is `.claude/rules/`, `.claude/settings.json` and
  `.claude/skills/`.

## Rollout

The work lands on `feature/package-authoring-skills`, merges into `develop`, and
reaches users at the next release, since a release is a tag and `copier copy`
resolves the newest tag. Existing packages see it only on their next
`copier update`, which — per the drift finding above — is rare.
