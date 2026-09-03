# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A [Copier](https://copier.readthedocs.io/) template that generates eccenca Corporate Memory (Marketplace) package repositories. There is no application code — the deliverable is the template itself, released as a git tag.

## The two-level layout (read this first)

The repository contains two distinct projects that share a directory tree:

| Level | Files | Audience |
|---|---|---|
| **Template project** | `Taskfile.yaml`, `CHANGELOG.md`, `README.md`, `.github/`, `tests/`, `copier.yaml` | maintainers of *this* repo |
| **Template payload** | everything under `src/` | rendered into *generated* packages |

`copier.yaml` sets `_subdirectory: src`, so only `src/` is rendered. A change under `src/` alters what every future generated package gets; a change at root level only affects this repo's own tooling. Never conflate the two `Taskfile.yaml` / `CHANGELOG.md` / `README.md` pairs.

Filenames themselves are Jinja-templated (`src/{{ package_id }}/…`, `src/{{ _copier_conf.answers_file }}.jinja`), so quote paths in shell commands.

## Commands

Root-level (template development):

```bash
task                    # list documented tasks
task create             # interactively generate a package into new_dir/
task check              # full suite: generate all test cases, then validate each
task clean              # remove *_dir working directories
```

Run a **single** test case (case name = a filename in `tests/` without `.yml`):

```bash
TEST_CASE=eccenca-testing-vocab task check:generate:case    # render into eccenca-testing-vocab_dir/
TEST_CASE=eccenca-testing-vocab task check:validate:case    # run `task check` inside it
```

Adding a `tests/<name>.yml` copier answers file automatically adds a test case — the task list is discovered with `find`, not enumerated.

`task check` is the only automated check; there is no separate lint or unit-test step in CI.

## Testing requires a live Corporate Memory instance

`check:validate:case` runs the *generated* project's `task check`, which calls `cmemc package install` / `uninstall` against a real CMEM deployment. Consequences:

- Needs `CMEM_BASE_URI` and `OAUTH_CLIENT_SECRET` in the environment.
- It mutates shared state, so both pipelines serialize it — GitHub Actions via `concurrency: testing_environment`, GitLab via `resource_group: testing-server`. A local run can collide with the nightly 3am GitHub run.
- Generated directories are `git init`-ed by `check:generate:case` on purpose: the generated `task build` has a precondition on `git describe`, because `PACKAGE_VERSION` is derived from it (`v0.0.0-<describe>` when the describe output is not already a `v…` tag).

## cmemc is pinned in two places and drifts

- `src/.gitlab-ci.yml` — `uv tool install cmem-cmemc@<version>`, the version *generated projects* use.
- `.github/workflows/check.yml` — `pip install cmem-cmemc==<version>`, the version *this repo's* CI uses.

These are independent literals with no coupling; they have silently diverged before. Always update both together, and note the version in `CHANGELOG.md`.

## Generated package anatomy

- `src/README.md.jinja` → the generated repo's README, **maintainer-facing** only.
- `src/DOCUMENTATION.md` → shipped *inside* the package and shown in the marketplace frontend. `src/{{ package_id }}/README.md` is a symlink to it (`_preserve_symlinks: true` in `copier.yaml`); `LICENSE` and `CHANGELOG.md` are symlinked into the package dir the same way. Marketplace-facing prose belongs in `DOCUMENTATION.md`, not `README.md.jinja`.
- `src/{{ package_id }}/cpa-manifest.json.jinja` builds the manifest: `python_dependencies` become `dependency_type: python-package` entries, `vocab_dependencies` become `marketplace-package` entries, and `register_as_vocabulary` is true only when `package_type == 'vocabulary'`.
- `src/Taskfile.yaml` reads `dotenv: ['.copier-answers.env', '.env']` — `package_dir` / `package_id` come from `.copier-answers.env.jinja`, not from Jinja substitution into the Taskfile. Users extend it via an optional `TaskfileCustom.yaml` (included with `flatten: true`); the generated Taskfile itself is marked not-to-be-edited.

## Branching and release process

Git-flow style: feature branches → `develop` → `main`. Feature branches must be current with `develop` before merging — a stale branch silently reverts template fixes in `src/`.

A release is a **git tag**, and nothing else — `copier copy gh:eccenca/cmem-package-template` resolves the newest tag, so tagging *is* publishing. This repo deliberately has no GitHub Release objects.

1. On `develop`: rename `## [Unreleased]` to `## [X.Y.Z] <YYYY-MM-DD>` in `CHANGELOG.md` (commit message: `update CHANGELOG`).
2. Merge `develop` into `main` with a merge commit (`--no-ff`).
3. Create a **signed annotated** tag on `main`, with the version string as its message: `git tag -s vX.Y.Z -m "vX.Y.Z"`.
4. Push `main` and the tag, then re-add the `## [Unreleased]` + TODO stub on `develop` (commit message: `add unreleased section`).

Version choice follows this repo's own precedent: releases with an `### Added` section take a minor bump, `### Fixed`-only releases take a patch.

## Conventions

- `CHANGELOG.md` follows [Keep a Changelog](http://keepachangelog.com/) and [Semantic Versioning](https://semver.org/); every user-visible change gets an entry before release.
- Generated packages default to `Apache-2.0`.
- `package_id` is validated by a regex in `copier.yaml`: lowercase, 2–5 hyphen-separated segments.
- CI runs Python 3.13, while the README states Python 3.8+ as the user-facing prerequisite.
