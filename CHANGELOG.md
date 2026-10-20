<!-- markdownlint-disable MD012 MD013 MD024 MD033 -->
# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/) and this project adheres to [Semantic Versioning](https://semver.org/)

## [Unreleased]

### Changed

- The `shapes` skill says that a class the package does not own - from a vocabulary it ships unchanged or depends on, such as QUDT or FOAF - gets its icon from a `foaf:depiction` on the package's node shape, so its resources show an icon in Explore without the package changing the source's vocabulary; the `vocabulary` skill's depictions reference points there
- The `shapes` skill carries the shape-catalog rules the eccenca packages settled on
  - one set of sections (property groups) per package, used on every form in steps of 100, findings first, the overview last, none by link direction; recommended common sections at fixed positions keep packages alike, replacing the fixed house-style groups and the advice to give each form its own group
  - rows numbered in steps of 10, editable before read-only before computed; row names in sentence case, plural for several values; every form text in every language of the vocabulary; a renamed row takes its slug, label and query along; embedding rows and embedded node shapes take no group
  - a computed *Type* row shows only the most specific classes
  - a package class whose instances another node shape also reaches - through `rdfs:subClassOf` or a second type - gets `shacl:order 0`, so its form opens first
  - `askIf…` queries edit and remove a resource only in the graph that holds it, with string placeholders and an empty guard because Explore also runs them without a resource; clone and create decide by graph alone, since Explore passes them no resource
  - validate through the graph that imports what the shapes need, data must satisfy the system shapes, no managed class in a shipped graph users create in, table reports set both flags and carry counts of marks
- The `vocabulary` skill: a term's IRI and label always match; a property links to an upper ontology's property with `rdfs:seeAlso`, never `rdfs:subPropertyOf`, while a class may extend an upper ontology's class; German definitions; class colours from a fixed palette with families spaced 360°/n apart, one neutral class in black and dependents in their owner's hue

## [1.8.0] 2026-10-18

### Added

- Generated packages now ship a skill check hook, `.claude/hooks/skill-check.py`, so that the session reads the skill covering a file at the moment it changes the file
  - an edit of a file that `.claude/skill-map.json` maps to a skill, and a shell command that names such a file, get a reminder naming the skill and its `SKILL.md`; the hook never denies anything, so no session, subagent or resumed session is locked out of its package
  - `content` patterns match RDF files only (`.ttl`, `.trig`, `.nt`, `.ttl.graph`, `.ttl.imports`), so prose, code and the skill map itself get no reminder for mentioning an RDF term
  - `.claude/skill-map.json` maps the shipped skills and belongs to the template; a project adds its own rules in `.claude/skill-map.custom.json`, which the template never writes, and switches the reminders off with an empty `.claude/no-skill-check`
  - a broken rule in `.claude/skill-map.custom.json` is dropped on its own and named in the reminder, and `task check:offline` fails on it by name (`bin/check_skill_map.py`), so a project rule never goes quiet unnoticed
  - `task check` smoke tests the hook in every test case (`check:skillhook:case`)

### Changed

- Every Python script a generated package ships - the hooks in `.claude/hooks/` and the checkers in `bin/` - is a PEP 723 script with a `uv run --script` shebang and is run by path, so [uv](https://docs.astral.sh/uv/) is now a prerequisite for working in a generated package with Claude Code - without it the hooks stay silent rather than block, so the skill reminders and the template feedback are simply missing; `task check:offline` calls `bin/check_all.py` by path, and `check_all.py` calls each checker the same way
- `task check:offline` stops with an install hint when uv is missing, and a checker that cannot be run fails with one line instead of a traceback
- `task import` runs the offline checks before it uninstalls the installed package, so a failed check leaves the instance as it was

## [1.7.0] 2026-10-06

### Added

- Generated packages now ship `bin/`, a set of offline RDF checks that need no Corporate Memory connection and no credentials, and a `task check:offline` that runs them
  - they report dangling `sh:property` / `sh:node` / `sh:group` / `sh:sparql` references, the `shui:QueryPlaceholder` declarations, every property shape's `shacl:path` against the vocabulary, the shipped queries against the documenting-a-query convention, and any graph no parser accepts
  - two of those mistakes are invisible until after an install and one of them then reports success: a dangling reference makes the SHACL service answer HTTP 500 for **every** graph on the instance, and a `shacl:path` that reaches nothing leaves `shacl:class`, `shacl:nodeKind` and every cardinality on that row with nothing to check
  - `task check` and `task import` both run the checks first - `import` because it is the task that puts a catalog on a live instance
  - the build fails only where something is actually broken: a dangling reference, a `shacl:path` that is a placeholder or not type-correct, a capitalised projection variable, a placeholder key written inside a comment, a value query carrying a parameter, an undeclared custom placeholder key, or a graph no parser accepts
  - the documentation conventions - a missing `dcterms:description`, a header that does not list the projection, an undeclared *built-in* placeholder key - print as warnings rather than failing, because a catalog can be complete and still be documented loosely, and failing on that buries the findings that do name a fault
  - **a package whose catalog has a real fault will go red on the next `copier update`.** That is the point of the checks, but it does mean a `copier update` can turn a pipeline red without anything in the package having changed
  - a file declaring `shui:SparqlQuery` counts as a catalog even with no shape beside it, so a package shipping nothing but queries is checked rather than skipped
  - they need [uv](https://docs.astral.sh/uv/), which resolves `rdflib` from each script's inline PEP 723 metadata - no install step and no Python project in the generated repository
- Two authoring skills, bringing the shipped set to six
  - `vocabulary` for every package type: predicate order, the `skos:definition` substitution principle and what belongs in `rdfs:comment` instead, label casing, head-final class names, classifying by intention, and a reference covering the `foaf:depiction` every class wants
  - `catalog-queries` for project packages: which column Corporate Memory takes as the value, why a projection variable may not be capitalised, how to document a query, and references for query placeholders and the `?graph` column
- `package-content` gained graph ownership - listing a graph is what makes uninstall clean - with a reference describing the four-graph layout a package shipping instance data wants, and the warning that a dataset writing with `clearGraphBeforeExecution` deletes the shipped graph description on every run
- `shapes` gained the conventions for cardinalities, slugs, `shacl:name` versus `rdfs:label`, and a reference on why every property shape needs a real `shacl:path`
- `package-content` also documents the lock an interrupted `package install` leaves behind, which makes every later install fail with a message that does not name the cause, and the rules note that the generated tasks pass no `-c` and so act on the default connection
- `package-content` also says to commit before `task build`, because a dirty tree names the archive for a state that lives on no commit, and scopes the namespace-dependency rule to project packages, because `cmemc` rejects a vocabulary manifest carrying any dependency

### Changed

- `bin/` is template owned, like `Taskfile.yaml`, `.gitlab-ci.yml` and `.claude/`: the session end check reports an edit there, and the shipped rules say so
- Reusing one property shape across node shapes is now scoped. It stays the right call for a domain-free annotation row such as `comment`, and is called out as wrong where the path is typed or the values come from a query, because one `shacl:path` cannot be type-correct for two target classes

## [1.6.0] 2026-09-24

### Added

- Generated packages now ship a `.claude/` directory: rules describing which files the template owns and where project specific additions go, a `template-feedback` skill that drafts an issue for the template's tracker, and a session end check that notices when a template owned file got in the way
  - the check is a blocking `Stop` hook and speaks only on evidence; a package switches it off with an empty `.claude/no-template-feedback` file
  - nothing is filed without the user seeing the exact issue text and confirming it
  - `.claude/settings.json` ships a tool permission allowlist: `task build`, `task check` and `task clean` run without a prompt, so note that a generated package's `task check` installs and uninstalls against the Corporate Memory deployment `CMEM_BASE_URI` points at. Filing an issue is deliberately not on that list
- Three authoring skills in the same directory: `package-content` (what `cpa-manifest.json` must declare, the licence rules, and how to check a package without a Corporate Memory connection), `build-projects` (DataIntegration project exports and workflow tasks) and `shapes` (the SHACL/shui shape catalog that drives the Explore UI)
  - vocabulary packages receive `package-content` only, since a build project and a shape catalog are things they do not have

### Changed

- The README now has a *Package Types* section explaining what the `package_type` answer decides - what each type ships, why a vocabulary package is asked no dependency questions, and which authoring skills a project package receives on top

### Fixed

- The header of the generated `Taskfile.yaml` now names `TaskfileCustom.yaml`, the filename it actually includes, instead of `TaskfileCustom.yml`

## [1.5.0] 2026-09-16

### Added

- A `marketplace` answer: answering no leaves the publish job out of the generated `.gitlab-ci.yml`, so internal packages no longer fail their pipeline on `main` for a missing marketplace credential

## [1.4.0] 2026-09-03

### Added

- The `github_page` answer now fills the homepage, source and issues URLs of the package manifest, which its help text promised but nothing implemented

### Changed

- `example.ttl` ships with the `owl:Ontology` declaration and vann namespace metadata that `register_as_vocabulary` requires, so the default generated package no longer contradicts the documentation
- Removed the workflow badge from the generated README, which could only ever 404 because the template ships no github workflow

### Fixed

- Derive the package version with `git describe --tags`, so that lightweight release tags are no longer silently published as `v0.0.0-<sha>`
- Set `GIT_DEPTH: 0` in the gitlab pipeline, so that `git describe` can see release tags outside the default shallow clone
- Escape package metadata in `cpa-manifest.json`, so that quotes or backslashes in the package name or description no longer produce an invalid manifest
- Quote the copier version specifier in the github workflow, which the shell parsed as a redirection instead of a version floor
- `task check` no longer rewrites the global git `init.defaultBranch` setting of the machine it runs on
- `task publish` honours `DIST_DIR` and reports a missing archive instead of failing with a bare file-not-found
- `task clean` also removes `*.cpa` archives now, as its description always claimed
- Explain the actual naming rule when a `package_id` is rejected, and derive a valid default from directory names containing underscores or capitals
- Corrected the generated structure and the Python prerequisite in the template README

## [1.3.0] 2026-09-03

### Added

- Documentation on the `owl:Ontology` declaration and the `vann:preferredNamespacePrefix` / `vann:preferredNamespaceUri` metadata needed when using `register_as_vocabulary`

### Changed

- Use cmemc 26.2.1 in gitlab and github pipelines
- Use eccenca-python v3.13.13 image in gitlab pipeline
- Bump github actions: checkout v7, setup-task v3, setup-python v7

## [1.2.2] 2026-08-26

### Fixed

- Disable the interrupt of gitlab pipelines to not have pipelines cancel and leave lock file artifacts wrongfully on the configured instance

## [1.2.1] 2026-08-25

### Fixed

- Use cmemc 26.2.0 in gitlab pipeline to ensure that dependency resolution works correctly against remote marketplace services

## [1.2.0] 2026-06-12

### Changed

- split maintainer and marketplace documentation


## [1.1.0] 2026-05-05

### Added

- build task handles language tag metadata of manifest automatically (needs cmemc 26.1.2)


## [1.0.0] 2026-04-27

### Added

- export task now extracts project archives to enable better version control (needs cmemc 26.1.1)

### Changed

- gitlab: use cmemc 26.1.1


## [0.9.7] 2026-03-16

### Fixed

- use bugfix python image


## [0.9.6] 2026-03-15

### Changed

- gitlab: publish can fail

### Fixed

- gitlab: use cmemc 26.1.0rc6


## [0.9.5] 2026-03-15

### Changed

- gitlab: use cmemc 26.1.0rc6
- publish to eccenca.market now


## [0.9.0] 2026-02-25

### Changed

- gitlab: use cmemc 26.1.0rc5
- gitlab: check for ECCENCA_MARKETPLACE_ACCOUNT and ECCENCA_MARKETPLACE_PASSWORD variables


## [0.8.0] 2026-02-11

### Changed

- gitlab: run publish only on main or master


## [0.7.0] 2026-01-30

### Changed

- rename manifest to `cpa-manifest.json`
- upgrading to cmemc RC3

### Added

- extend gitginore: .DS_Store


## [0.6.0] 2026-01-27

### Added

- documentation
  - more examples
- gitlab
  - resource group for check job


## [0.5.1] 2026-01-26

### Fixed

- gitlab build plan
- tests


## [0.5.0] 2026-01-26

### Added

- example graph
- adding more features to the manifest by default (readme, license, changelog)

### Changed

- upgrading to cmemc RC2
- preserving symlinks to re-use LICENSE, README and CHANGELOG
- improving the Taskfile with git checks
- remove Taskfile template for better maintenance
- replacing the tests

### Fixed

- tests
- unneeded workflow parts


## [0.4.0] 2026-01-20

### Changed

- reorder questions

### Added

- comment question (incl. input length validation)
- input validation for name and description

## [0.3.0] 2026-01-20

### Added

- add explicit `--vcs-ref` in example command
- add input validation to enforce non empty `package_name` and `package_description`

### Changed

- update generated structure, clarify default license


## [0.2.0] 2026-01-19

### Added

- README, CHANGELOG, CONTRIBUTING templates

### Removed

- dynamic license selection

### Changed

- Apache License 2.0 used by default


## [0.1.0] 2026-01-19

### Added

- simple package test case
- test case for a package with dependencies
- initial commit

