# Working in this project

This repository was generated from the
[cmem-package-template](https://github.com/eccenca/cmem-package-template)
copier template and stays connected to it through `copier update`.

## Some files belong to the template

`Taskfile.yaml`, `.gitlab-ci.yml` and everything under `.claude/` are rendered
from the template. Edits there are not preserved: the next `copier update`
either reverts them or turns them into a merge conflict.

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
- `build-projects` - DataIntegration project exports, their layout, which
  workflow task to reach for, and how to test one
- `shapes` - the shape catalog: node and property shapes, groups, URI
  templates, widgets, navigation and validation
- `template-feedback` - reporting a finding back to the template

A vocabulary package ships fewer of them, because a build project and a shape
catalog are things it does not have.

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
