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
- `src/.gitlab-ci.yml.jinja` is Jinja-rendered rather than copied verbatim, because the `marketplace` answer gates the `publish` stage entry and the `publish` job — an internal package gets a pipeline with no trace of publishing. Literal `{{` or `{%` in that file now needs escaping.
- `src/Taskfile.yaml` reads `dotenv: ['.copier-answers.env', '.env']` — `package_dir` / `package_id` come from `.copier-answers.env.jinja`, not from Jinja substitution into the Taskfile. Users extend it via an optional `TaskfileCustom.yaml` (included with `flatten: true`); the generated Taskfile itself is marked not-to-be-edited.
- `src/{{ '.claude' }}/` ships agent support into every generated package — rules, the `template-feedback` skill, the `Stop` hook and `settings.json`. The quoted-expression directory name is deliberate; see *Feedback from generated packages*.

## Feedback from generated packages

Generated packages report findings back through the `template-feedback` skill
shipped in `src/{{ '.claude' }}/skills/`. Two things point at it: the rule in
`src/{{ '.claude' }}/rules/copier-template.md`, which names the moments worth
reporting, and a blocking `Stop` hook that speaks only when the working tree
shows evidence of template friction — a template owned file was edited, a
`copier update` left `.rej` files or conflict markers behind. The hook is
`src/{{ '.claude' }}/hooks/template-feedback.py`, which `settings.json` runs
directly rather than through a task, because a task runner writes to stdout and
picks its own exit codes, and stdout is the hook's JSON channel. A package
switches the hook off with an empty `.claude/no-template-feedback` file, which
is project owned and therefore survives `copier update`.

The shipped directory is named `src/{{ '.claude' }}/`, an expression that
always renders to `.claude`, because a literal `src/.claude/` would be picked
up by Claude Code *in this repository*: sessions working on the template would
silently load a generated package's rules and skills.

Nothing is filed unattended. The skill drafts, shows the user the exact title
and body, and only then files — and `gh issue create` is deliberately left out
of the shipped permission allowlist, so the harness prompts as well. The two
gates are independent on purpose, because filing is the one irreversible,
public thing this feature does.

Reports arrive as issues labelled `template-feedback`, through
`.github/ISSUE_TEMPLATE/template-feedback.yml`. They deliberately do **not**
name the package they came from: most generated packages are private, several
are customer specific, and this tracker is public. What the form asks for
instead is `_commit`, `package_type` and whether `marketplace` and
`github_page` are answered.

The maintainer side is `/template-triage`, a skill of this repository with no
twin under `src/` — triage edits `src/`, which would be nonsense inside a
generated package. Accepted findings become one commit each in `src/` with a
changelog entry; declined ones become an entry in *Deliberate decisions*, which
is what stops them coming back.

`task check` covers exactly one part of this: `check:hook:case` asserts that the
shipped hook stays silent on a clean tree and respects `stop_hook_active`. It
cannot tell you the hook fires on the right evidence — that needs a hand run in
a rendered case, piping a `Stop` payload into
`<case>_dir/.claude/hooks/template-feedback.py`. Remember that a test case is
rendered from `git rev-parse HEAD`, so a change under `src/` has to be
committed before it shows up in one.

## Branching and release process

Git-flow style: feature branches → `develop` → `main`. Feature branches must be current with `develop` before merging — a stale branch silently reverts template fixes in `src/`.

`main` is a **fast-forward pointer** onto `develop`, never carrying commits of its own, so `main` is always an ancestor of `develop`. Do not merge into `main` with `--no-ff`; that is what the pre-1.5.0 procedure did and it is what broke the fast-forward.

A release is a **git tag**, and nothing else — `copier copy gh:eccenca/cmem-package-template` resolves the newest tag, so tagging *is* publishing. This repo deliberately has no GitHub Release objects.

The full procedure — preflight checks, version derivation, commit and tag messages, and the exact push order — lives in `.claude/skills/release/SKILL.md` and is invoked with `/release`. It is not repeated here, because it is only relevant at release time. Two things from it are worth knowing while doing ordinary work:

- A release makes **exactly two branch pushes**. The `check` job declares `concurrency: testing_environment`, a static group shared by every branch, and GitHub keeps only one *pending* run per group — so a third push cancels whichever run was waiting. Avoid pushing to `develop` while a release is in flight for the same reason.
- The procedure is a deliberate mirror of the one in the sibling repository `eccenca/cmem-plugin-template`. Read that repository's `.claude/skills/release/SKILL.md` before redesigning anything here, and consider porting improvements in both directions.

## Conventions

- `CHANGELOG.md` follows [Keep a Changelog](http://keepachangelog.com/) and [Semantic Versioning](https://semver.org/); every user-visible change gets an entry before release.
- Generated packages default to `Apache-2.0`.
- `package_id` is validated by a regex in `copier.yaml`: lowercase, 2–5 hyphen-separated segments.
- CI runs Python 3.13, while the README states Python 3.8+ as the user-facing prerequisite.

## Deliberate decisions — please do not re-raise these

The following look like oversights during a review, but are intentional. They
have each been considered and left as they are. This is the section the shipped
`template-feedback` skill sends every would-be reporter to, and the section
`/template-triage` writes a declined finding into.

### Vocabulary packages are asked no dependency questions

`python_dependencies` and `vocab_dependencies` in `copier.yaml` carry
`when: "{{ package_type != 'vocabulary' }}"`, so a vocabulary package is never
asked about either. This is not a missing question: a marketplace vocabulary
package cannot declare dependencies at all, so an answer would have nowhere to
go in `cpa-manifest.json`. Asking anyway would invite an answer that is
silently dropped.

### `main` carries no commits of its own

`main` is a fast-forward pointer onto `develop` and never receives a merge
commit. The pre-1.5.0 procedure merged with `--no-ff`, which is what broke the
fast-forward relationship and had to be repaired. A release is a tag, and
`main` only ever moves to a commit that already exists on `develop`.

### Generated packages get `.claude/rules/`, never a `CLAUDE.md`

Agent support is delivered as `.claude/rules/`, `.claude/settings.json` and
`.claude/skills/`. The template writes no `CLAUDE.md`, no `AGENTS.md` and no
`.mcp.json` into a generated package.

Claude Code auto-loads `*.md` under `.claude/rules/` as project documentation,
which buys two things a shipped `CLAUDE.md` cannot. Agent writes stay harmless:
the `#` memory shortcut and `/init` write to `CLAUDE.md` by name, whatever a
"do not edit, this is generated" header says, and leaving that file to the
project means those writes cannot become `copier update` conflicts. And both
files are read, so a package that already has a hand-written `CLAUDE.md` does
not have to choose.

The cost is accepted: rules are Claude-Code-specific.
