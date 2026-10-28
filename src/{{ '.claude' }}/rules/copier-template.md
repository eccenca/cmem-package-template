# Working in this project

This repository was generated from the
[cmem-package-template](https://github.com/eccenca/cmem-package-template)
copier template and stays connected to it through `copier update`.

## Some files belong to the template

`Taskfile.yaml`, `.gitlab-ci.yml`, `bin/` and the template's part of `.claude/` -
its hooks, rules, `settings.json`, `skill-map.json` and the shipped skills - are
rendered from the template; a skill of your own, `skill-map.custom.json` and the
two opt-out files are the project's. Edits there are not preserved: the next
`copier update` either reverts them or turns them into a merge conflict.

Add project specific build steps to `TaskfileCustom.yaml` instead - note the
`.yaml` spelling, since only that one is included. Project specific agent
instructions belong in `CLAUDE.md`, which the template never writes and which
is read alongside these rules. Personal tool permissions belong in
`.claude/settings.local.json`, which is git-ignored.

When something in a template owned file is genuinely wrong, fix it upstream in
the template and update, rather than patching the generated copy. The way to
do that is to report it: use the `template-feedback` skill, which checks what
the template has already decided and drafts an issue for you to confirm. Reach
for it when you wanted to edit a template owned file, when a `copier update`
conflict will recur for everyone, or when something these rules or the shipped
skills claim turns out to be wrong. A finding that only applies to this project
is not template feedback.

A session that shows evidence of such friction ends with a check that asks
about it once. Answering "this one is specific to this project" is a complete
answer. A project that does not want the check at all creates an empty
`.claude/no-template-feedback` file, which the template never overwrites.

## Skills ship with this project

Besides these rules, the template ships skills under `.claude/skills/`. Run
`/` to see which ones this project has - they depend on the answers it was
generated with:

- `package-content` - the manifest contract, adding or removing shipped files,
  the licence rules, and how to check a package without a Corporate Memory
  connection
- `vocabulary` - the ontology: predicate order, definitions and comments,
  naming, and the icon every class wants
- `build-projects` - DataIntegration project exports, their layout, projects
  by lifecycle, ids, descriptions, tags, namespaces and migrations, which task to
  reach for, and how to test one
- `workflows` - the design of a workflow: constructs first, phases,
  responsibilities, sticky notes, the waterfall layout (`task layout`) and the
  mechanics found on the way
- `shapes` - the shape catalog: node and property shapes, groups, URI
  templates, widgets, navigation and validation
- `catalog-queries` - the SPARQL a catalog ships: the header comment, the
  projection, placeholders and the `?graph` column
- `thesauri` - a SKOS taxonomy resources are categorized by: its shape, who
  maintains it, the taxonomy editor, type on use, and a view to browse it
- `template-feedback` - reporting a finding back to the template

A vocabulary package ships fewer of them, because a build project and a shape
catalog - and so the queries inside one - are things it does not have.

## Load the skill that covers a file before changing it

`.claude/skill-map.json` maps files to the skills that cover them; read the
skill before the first edit. `.claude/hooks/skill-check.py` adds a note
naming the skill and its `SKILL.md` to every edit of a mapped file and to
every shell command that names one. The note arrives with the tool's result,
after the change is made: if this session had not loaded that skill yet, load
it now, check the change against it and fix what departs. The hook never
refuses a tool call, so the note is all there is; act on it.

`.claude/skill-map.json` belongs to the template. Rules for this project - for
skills of your own, or for files only this project has - go into
`.claude/skill-map.custom.json`, in the same format; the template never writes
it, and `task check:offline` fails on a rule it cannot use. An empty
`.claude/no-skill-check` switches the reminders off.

## Two files carry the documentation, and they face different readers

`DOCUMENTATION.md` is shipped inside the package and is what the marketplace
frontend renders; the package directory's `README.md` is a symlink to it. The
top level `README.md` faces whoever maintains this repository. Prose written
for users of the package belongs in `DOCUMENTATION.md`, not in `README.md`.

`LICENSE` and `CHANGELOG.md` are symlinked into the package directory the same
way. Edit the originals at the top level, never the links.

## Checks talk to a live Corporate Memory deployment

`task build` builds the package archive, and `task check` installs it with
`cmemc package install --replace` and then uninstalls it again. That needs
`CMEM_BASE_URI` and `OAUTH_CLIENT_SECRET` in the environment, and it changes
shared state on whichever deployment those point at. Know which deployment you
are aimed at before running it, and do not run it concurrently with a pipeline
doing the same thing.

**The generated tasks invoke `cmemc` without `-c`**, so they act on the
default connection. Drop to the bare `cmemc` commands with an explicit `-c`
when that is not the instance you mean.

`task check:offline` is the exception: it runs the checks in `bin/` over the
shipped RDF and touches no deployment at all, so it is always safe to run.
`task check` and `task import` both run it first, because two of the mistakes
it catches are invisible until after an install - a dangling shape reference
takes the SHACL service down for every graph on the instance.

`task build` has a precondition on `git describe`, because the package version
is derived from it. In a repository without a tag the version becomes
`v0.0.0-<describe>`.

## Every user visible change gets a changelog entry

`CHANGELOG.md` follows [Keep a Changelog](https://keepachangelog.com/). Add an
entry under `## [Unreleased]` in the matching `### Added`, `### Changed`,
`### Fixed` or `### Removed` section. The trigger is whether a user would
notice, not whether behaviour changed.

Do not cite an issue or Jira ticket. The people reading this file cannot open
them, so the entry has to stand on its own.
