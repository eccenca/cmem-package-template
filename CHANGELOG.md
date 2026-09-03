<!-- markdownlint-disable MD012 MD013 MD024 MD033 -->
# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/) and this project adheres to [Semantic Versioning](https://semver.org/)

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

