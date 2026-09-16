# Feedback cycle for cmem-package-template

Date: 2026-09-16

## Goal

Give this template the same closed feedback loop that
[cmem-plugin-template](https://github.com/eccenca/cmem-plugin-template) has: a
project generated from the template notices when something in the template got
in the way, reports it upstream as a GitHub issue, and a maintainer triages
that issue into either a change under `src/` or a written, findable decision
not to make one.

Nothing flows back from a generated package on its own. A finding that would
help every package therefore has to leave the project it was found in, and the
loop exists to make that the path of least resistance.

## Why it is worth the machinery

Most packages generated from this template are private, several are customer
specific, and their maintainers are not the people who maintain the template.
Findings die where they are found. The plugin template answered this with four
shipped files and four maintainer-side ones, and that design has been in use
long enough to be worth copying rather than re-inventing — this repository's
`CLAUDE.md` already names the plugin template as the reference implementation
for shared procedures.

## What lands where

The repository's two-level split applies in full: `src/` is payload rendered
into every generated package, everything else is this repository's own tooling.
The feedback cycle has components on both sides, and confusing them is the
single most likely way to get this wrong.

### Shipped into generated packages

The directory is named `src/{{ '.claude' }}/` — an expression that always
renders to `.claude`. A literal `src/.claude/` would be picked up by Claude
Code *in this repository*, so a session working on the template would silently
load a generated package's rules and skills alongside this repository's own
`release` skill.

#### `rules/copier-template.md`

Claude Code auto-loads `*.md` under `.claude/rules/` as project documentation.
The template deliberately writes no `CLAUDE.md`, no `AGENTS.md` and no
`.mcp.json` into a generated package: `CLAUDE.md` is where the `#` memory
shortcut and `/init` write by name, and leaving that file to the project means
those writes can never become `copier update` conflicts. A project's own
`CLAUDE.md` is read alongside the rules, so nobody has to choose. The accepted
cost is that rules are Claude-Code specific.

Content, adapted to packages:

- The template owns `Taskfile.yaml`, `.gitlab-ci.yml` and everything under
  `.claude/`. Edits there are reverted or turned into conflicts by the next
  `copier update`.
- Project specific build steps belong in `TaskfileCustom.yaml` — note the
  `.yaml` spelling, since only that one is included. Project specific agent
  instructions belong in `CLAUDE.md`. Personal tool permissions belong in
  `.claude/settings.local.json`, which is git-ignored.
- `DOCUMENTATION.md` is what the marketplace frontend renders and
  `{{ package_id }}/README.md` is a symlink to it; the top level `README.md`
  is maintainer-facing only. Marketplace-facing prose goes in the former.
- `task check` builds the package and then runs `cmemc package install` and
  `cmemc package uninstall` against a live Corporate Memory deployment. It
  mutates shared state and needs `CMEM_BASE_URI` and `OAUTH_CLIENT_SECRET`.
- Every user visible change gets a `CHANGELOG.md` entry under `## [Unreleased]`,
  following Keep a Changelog. No issue or ticket references: the people reading
  that file cannot open them.
- When a template owned file is genuinely wrong, fix it upstream and update,
  rather than patching the generated copy. The way to do that is the
  `template-feedback` skill. Reach for it when you wanted to edit a template
  owned file, when a `copier update` conflict will recur for everyone, or when
  something the rules or the shipped skills claim turns out to be wrong. A
  finding that only applies to this project is not template feedback.

#### `skills/template-feedback/SKILL.md`

The reporting skill, retargeted at `eccenca/cmem-package-template`. It

1. tests whether the finding belongs upstream at all — would it still make
   sense in a package that has nothing to do with this one;
2. checks what has already been decided, by searching the issues open **and**
   closed with the `template-feedback` label, by reading the *Deliberate
   decisions* section of the template's `CLAUDE.md`, and by skimming the
   template's `## [Unreleased]` changelog section for a fix awaiting release;
3. drafts a title and body following the issue form;
4. files with `gh issue create --repo eccenca/cmem-package-template --label
   template-feedback` after the user's explicit go-ahead.

Two rules are load-bearing and carried over verbatim in spirit:

- **Never file without showing the exact title and body first**, and never
  without an explicit go-ahead in that turn. Filing is the only irreversible,
  public thing the feature does.
- **Do not name this repository and do not paste code from it.** The tracker is
  public; most generated packages are not. What the maintainer needs instead is
  taken from `.copier-answers.yml`: `_commit`, `package_type`, and whether
  `marketplace` and `github_page` are answered.

`gh issue create` is deliberately absent from the shipped permission allowlist,
so the harness prompts in addition to the skill's own gate. The two gates are
independent on purpose. When `gh` is missing or unauthenticated, the skill
prints the finished title, body and command and stops, rather than looking for
another way to publish.

#### `hooks/template-feedback.py`

A `Stop` hook that says nothing unless the session left evidence that a
template owned file got in the way, and then asks the agent to consider
reporting it. Deciding there is nothing to report is a valid answer; the hook
fires at most once per session either way, guarded by a marker file in the
temporary directory keyed on the session id.

Three invariants govern it: print nothing unless there is something to say,
because stdout is the hook's JSON channel; always exit 0, because a broken hook
must never keep a session from ending; and when a fact cannot be established,
drop the evidence rather than guess — a false positive blocks a session, a
false negative only misses one report.

Evidence, three signals:

1. A template owned path was changed — `.claude/`, `.gitlab-ci.yml`,
   `Taskfile.yaml`. The shipped rules tell the agent not to edit these, so a
   modification is the strongest available signal.
2. A `copier update` left `.rej` files behind.
3. Conflict markers are still in the working tree. The one template owned file
   that *documents* what a conflict looks like is exempt if such a file exists
   here; today it does not, so the exemption list starts empty and the constant
   stays, commented, for the day a skill quotes a marker.

A changed `_commit` line in the answers file means the working tree *is* a
copier update, in which case signal 1 is suppressed: the rewritten files were
not edited by anyone.

Compared with the upstream hook, `added_silencers()`, `added_ignores()`, the
`tomllib` import and the `PYTHON_SUFFIXES` and `SILENCER` constants are dropped
— a generated package contains no Python, no ruff and no `pyproject.toml`, so
those checks have nothing to match. `git()`, `entries()`, `attributed()`,
`owned()`, the copier-update guard, the session marker and `main()` are kept
with their reasoning intact. `.github/workflows/` and `.pre-commit-config.yaml`
leave the owned-paths tuple, because generated packages get neither.

A package switches the hook off with an empty `.claude/no-template-feedback`
file, which is project owned and therefore survives `copier update`. The skill
still works when invoked directly; only the automatic reminder goes away.

#### `settings.json`

```json
{
    "permissions": {
        "allow": [
            "Bash(task build:*)",
            "Bash(task check:*)",
            "Bash(task clean:*)",
            "Bash(gh issue list:*)",
            "Bash(gh search issues:*)"
        ]
    },
    "hooks": {
        "Stop": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 .claude/hooks/template-feedback.py",
                        "timeout": 30
                    }
                ]
            }
        ]
    }
}
```

`task check` is pre-approved deliberately, matching the plugin template's
shape, with the consequence understood and accepted: an approved run installs
and uninstalls the package on the configured Corporate Memory deployment
without a prompt. The hook is run directly rather than through a task runner,
because a task runner writes to stdout and picks its own exit codes, and stdout
is the hook's JSON channel. There is no `PostToolUse` formatter hook; a
generated package has no formatter.

#### `src/.gitignore`

Gains `.claude/settings.local.json`, so personal permissions stay out of the
generated repository.

### Kept in this repository

#### `.github/ISSUE_TEMPLATE/template-feedback.yml`

The form findings arrive through, labelled `template-feedback`, titled
`[feedback] `. Fields: *The finding* (required), *Why this generalises*
(required — a finding that only applies to the project it came from is not
template feedback), *Which part of the template* (optional, the file under
`src/`), *Suggested change* (optional), *Template version* (required, the
`_commit` from `.copier-answers.yml`), *package_type* (required dropdown:
`vocabulary`, `project`), and checkboxes for `marketplace` and `github_page`
being answered.

The markdown header repeats the confidentiality rule and points at the closed
issues and at the *Deliberate decisions* section of `CLAUDE.md`.

The `template-feedback` label does not exist in this repository yet and a form
silently drops a label it cannot find, so setting it up includes one manual
`gh label create template-feedback`.

#### `.claude/skills/template-triage/SKILL.md`

Maintainer-side, this repository only. It has no twin under `src/`, because
triage edits `src/`, which would be nonsense inside a generated package.

Preconditions: clean tree, on `develop`, then
`git switch -c feature/template-feedback-triage` — never work on `develop`
directly.

Decide each issue in order, stopping at the first hit:

1. **Already decided** — listed in *Deliberate decisions*. Decline it and do
   not implement it, however well the issue argues. Changing a settled decision
   is a human call, not a side effect of working through a list.
2. **Already fixed** — present in `## [Unreleased]` or in the current `src/`.
   Close, pointing at the entry.
3. **Not template material** — holds only for the project it came from, or asks
   for something that belongs in that project's `TaskfileCustom.yaml` or
   `CLAUDE.md`. Decline.
4. **Wrong side of the split** — about this repository's own CI, Taskfile or
   `.claude/`, not about `src/`. A real report, but not a change to what users
   receive; handle it as ordinary work and drop the framing.
5. Otherwise **accept**.

An accepted finding is weighed against both `package_type`s and against
`marketplace` and `github_page` answered either way. A change that only makes
sense for project packages belongs behind the `package_type != 'vocabulary'`
condition, not in the shared path — vocabulary packages take no dependencies at
all, which is why the dependency questions are already conditional.

Implementation: one issue, one commit, so a bad finding can be dropped without
unpicking the good ones. Change `src/`, remembering that filenames there are
Jinja and that `.gitlab-ci.yml.jinja` needs literal `{{` and `{%` escaped. Add
a `CHANGELOG.md` entry under `## [Unreleased]` — one commit per issue does not
mean one entry per issue; extend an existing entry when two findings land in
the same file. Commit both together with
`git commit -S -m "<what changed>, fixes #<issue>"`; the closing keyword has to
be in the subject, because the pull request targets `develop` and GitHub only
creates closing references against the default branch. The issue therefore
closes when the commit reaches `main`, which happens at release time — say so
when reporting, so nobody reads the delay as broken automation.

Declining is not just closing: the reasoning goes into *Deliberate decisions*
in `CLAUDE.md`, in the voice of the entries already there — what it looks like,
why it is not that, what was weighed — and the issue is closed with a comment
that says the same in short and links to the section. That section is what the
reporting skill tells generated packages to read before filing, so an entry
there is what stops the finding coming back. The entry is skipped only for a
one-off mistake in the report itself.

The skill ends at `task check` and never tags; releasing stays `/release`.

#### `CLAUDE.md`

Two new sections:

- **Feedback from generated packages** — how the loop works and which file does
  what, mirroring the structure of the plugin template's section, plus the note
  that `template-triage` is a skill with no `src/` twin.
- **Deliberate decisions — please do not re-raise these** — the destination for
  declines, and the section the reporting skill sends every would-be reporter
  to. It is seeded with two decisions already implicit in this repository, so
  the first reporter does not arrive at an empty list:
  - *Vocabulary packages are asked no dependency questions.* Marketplace
    vocabulary packages cannot declare dependencies at all, so
    `python_dependencies` and `vocab_dependencies` are conditional on
    `package_type != 'vocabulary'`.
  - *`main` carries no commits of its own.* It is a fast-forward pointer onto
    `develop`; the pre-1.5.0 `--no-ff` merge is what broke that and is not
    coming back.

The *Generated package anatomy* section gains a line about the shipped
`.claude/` payload.

#### `Taskfile.yaml`

A new internal `check:hook:case`, called from `check:validate:case` before the
generated `task check`. It asserts, against the freshly generated and committed
tree that `check:generate:case` leaves behind, that

- the hook prints nothing on a clean tree, and
- the hook prints nothing when `stop_hook_active` is true.

Both matter because this is a blocking `Stop` hook: if it spoke when it should
not, or ignored the loop guard, every session in every generated package would
stop being able to end. The task runs offline and needs no Corporate Memory
instance, so it also gives `task check` its first assertion that does not
depend on a live deployment.

It cannot tell you the hook fires on the *right* evidence. That stays a hand
run in a rendered case.

#### `CHANGELOG.md`

An `### Added` entry under `## [Unreleased]`, replacing the placeholder TODO
line, saying what a template user notices: generated packages now ship
`.claude/` rules, a `template-feedback` skill and a session-end check that
points findings at the template's issue tracker.

## Non-goals

- No `release` skill for generated packages. Package releases are out of scope
  here and are not part of the feedback cycle.
- No `CLAUDE.md`, `AGENTS.md` or `.mcp.json` shipped into generated packages.
- No formatter or linter introduced into generated packages in order to give
  the hook more signals to read.
- No automatic filing. Every issue passes two independent human gates.

## Verification

1. `task check` — renders both test cases, runs the new `check:hook:case`
   assertions and then each generated package's own `task check`. Needs
   `CMEM_BASE_URI` and `OAUTH_CLIENT_SECRET`, and serialises against the
   nightly GitHub run.
2. A hand run of the positive path in a rendered case: edit `Taskfile.yaml` in
   `eccenca-testing-vocab_dir`, pipe a `Stop` payload into the hook, and
   confirm it blocks with the template owned files evidence; then confirm a
   second run with the same session id stays silent.
3. Render both test cases and read the generated `.claude/` tree to confirm the
   `{{ '.claude' }}` expression resolved and no Jinja leaked into the shipped
   files.

## Rollout

The work lands on `feature/template-feedback-cycle`, merges into `develop`, and
reaches users at the next release, since a release here is a tag and
`copier copy` resolves the newest tag. The one manual step outside git is
`gh label create template-feedback`, which has to happen before the first
report arrives.
