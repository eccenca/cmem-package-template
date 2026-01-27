<!-- markdownlint-disable MD012 MD013 MD024 MD033 -->
# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/) and this project adheres to [Semantic Versioning](https://semver.org/)

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

