# Template feedback cycle — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give cmem-package-template the closed feedback loop cmem-plugin-template has — generated packages notice template friction and file it upstream, maintainers triage it into `src/` changes or written decisions.

**Architecture:** Four files are added under `src/{{ '.claude' }}/` and rendered into every generated package (rules, a reporting skill, a blocking `Stop` hook, `settings.json`). Four more stay in this repository (a GitHub issue form, a maintainer triage skill, two new `CLAUDE.md` sections, a `Taskfile.yaml` smoke test). The hook is the only executable code and is the only part `task check` can assert on.

**Tech Stack:** Copier 9 with `_subdirectory: src`, Jinja-templated filenames, Taskfile 3, Python 3 standard library only (the hook has no dependencies), GitHub issue forms, `gh` CLI.

**Spec:** `docs/superpowers/specs/2026-09-16-template-feedback-cycle-design.md`

## Global Constraints

- **Two-level split.** Everything under `src/` is payload rendered into generated packages. Everything else is this repository's own tooling. Never edit one believing you are editing the other.
- **The shipped directory is `src/{{ '.claude' }}/`**, an expression that always renders to `.claude`. A literal `src/.claude/` would be loaded by Claude Code in this repository. Always quote these paths in shell commands.
- **Copier answers available in `src/` templates:** `package_type` (`vocabulary` | `project`), `package_id`, `package_name`, `package_description`, `python_dependencies`, `vocab_dependencies` (both only when `package_type != 'vocabulary'`), `marketplace` (bool), `github_page` (str).
- **Upstream reference:** `/Users/seebi/Repositories/plugins/cmem-plugin-template`. Read the corresponding file there before writing each new file, and port the reasoning, not just the shape.
- **All commits are signed:** `git commit -S`. Never `--no-gpg-sign`.
- **Work happens on `feature/template-feedback-cycle`**, already created, branched from `develop`.
- **Repository the loop reports to:** `eccenca/cmem-package-template`, public, issues enabled.
- **Label used throughout:** `template-feedback`.
- **A generated package has no Python, no ruff, no mypy, no pytest and no formatter.** Never add one to give the hook more to read.
- `task check` needs `CMEM_BASE_URI` and `OAUTH_CLIENT_SECRET` and mutates a shared Corporate Memory deployment. `task check:generate:case` and `task check:hook:case` do not.

---

### Task 1: The shipped `Stop` hook, its settings and its smoke test

**Files:**
- Modify: `Taskfile.yaml` (add `check:hook:case`, call it from `check:validate:case`)
- Create: `src/{{ '.claude' }}/hooks/template-feedback.py`
- Create: `src/{{ '.claude' }}/settings.json`
- Modify: `src/.gitignore`
- Test: `Taskfile.yaml` task `check:hook:case`, run against `eccenca-testing-vocab_dir`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: the file `.claude/hooks/template-feedback.py` in every generated package, invoked as `python3 .claude/hooks/template-feedback.py` with a JSON `Stop` payload on stdin. It prints either nothing or a single JSON object `{"decision": "block", "reason": "<text>"}` on stdout, and always exits 0. The `reason` text names the `template-feedback` skill created in Task 3 and the opt-out file `.claude/no-template-feedback`. Task 2's rules file and Task 3's skill both document this behaviour and must match it.

- [ ] **Step 1: Write the failing test — add `check:hook:case` to `Taskfile.yaml`**

Insert this task after `check:generate:cases` and before `check:validate:case`:

```yaml
  check:hook:case:
    desc: smoke test the Stop hook a generated package ships
    summary: |
      Nothing else here ever executes the shipped agent files, and this one is
      a blocking Stop hook: if it spoke when it should not, or ignored the
      loop guard, every session in every generated package would stop being
      able to end. Both cases are asserted against a freshly generated, clean
      working tree.

      This cannot tell you the hook fires on the right evidence. That is still
      a hand run in a rendered case - see CLAUDE.md.
    internal: true
    cmds:
      - >
        cd {{.TEST_CASE}}_dir &&
        out=$(printf '%s' '{"hook_event_name":"Stop","session_id":"smoke-{{.TEST_CASE}}-quiet","stop_hook_active":false}'
        | python3 .claude/hooks/template-feedback.py) &&
        { [ -z "$out" ] || { echo "hook spoke on a clean tree: $out"; exit 1; }; }
      - >
        cd {{.TEST_CASE}}_dir &&
        out=$(printf '%s' '{"hook_event_name":"Stop","session_id":"smoke-{{.TEST_CASE}}-loop","stop_hook_active":true}'
        | python3 .claude/hooks/template-feedback.py) &&
        { [ -z "$out" ] || { echo "hook ignored stop_hook_active: $out"; exit 1; }; }
```

Then wire it into `check:validate:case`, whose `cmds:` block becomes:

```yaml
    cmds:
      - task: check:hook:case
        vars: {TEST_CASE: '{{.TEST_CASE}}'}
      - cd {{.TEST_CASE}}_dir && task check
```

- [ ] **Step 2: Run it to make sure it fails**

```bash
TEST_CASE=eccenca-testing-vocab task check:generate:case
TEST_CASE=eccenca-testing-vocab task check:hook:case
```

Expected: FAIL — `python3: can't open file '.claude/hooks/template-feedback.py': [Errno 2] No such file or directory`. The generated package ships no `.claude/` yet.

- [ ] **Step 3: Write the hook**

Create the directory and the file:

```bash
mkdir -p "src/{{ '.claude' }}/hooks"
```

`src/{{ '.claude' }}/hooks/template-feedback.py`:

```python
#!/usr/bin/env python3
"""Notice friction with the cmem-package-template at the end of a session.

This is a Claude Code ``Stop`` hook. ``.claude/settings.json`` runs it
directly, and not through a task, because a task runner writes to stdout and
picks its own exit codes - and stdout is this hook's JSON channel. It reads the
hook payload from stdin, so a hand run needs one::

    echo '{}' | python3 .claude/hooks/template-feedback.py

It belongs to the template - see ``.claude/rules/copier-template.md``.

It says nothing at all unless the session left evidence that a template owned
file got in the way, and then it asks the agent to consider whether that is
worth reporting upstream. Deciding there is nothing to report is a valid
answer; the hook fires at most once per session either way.

Three rules govern everything below. Print **nothing** unless there is
something to say, because stdout is the hook's JSON channel. Always exit 0,
whatever goes wrong - a broken hook must never keep a session from ending. And
when a fact cannot be established, drop the evidence rather than guessing: a
false positive blocks a session, a false negative only misses one report.

This file is not part of the package and is not covered by ``task check``
beyond a smoke test, so keep it small, dependency free and readable.
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

OPT_OUT = Path(".claude") / "no-template-feedback"

# Paths the template owns. The shipped rules tell the agent not to edit these,
# so a modification here is the strongest available signal that something in
# the template did not fit. A generated package gets no GitHub workflows and no
# pre-commit configuration, which is why neither is listed.
TEMPLATE_OWNED = (
    ".claude/",
    ".gitlab-ci.yml",
    "Taskfile.yaml",
)

# Template owned files that *document* what a conflict looks like, in a fenced
# example. Every copier update rewriting such a file would add those markers to
# the diff and block the session during the very workflow this hook exists to
# support. Nothing shipped today does that, so the tuple is empty - keep it,
# and name the file here the day a shipped skill quotes a marker.
CONFLICT_PROSE: tuple[str, ...] = ()

# What copier leaves behind when an update could not be merged. Only an added
# line counts; a marker already committed is this package's problem, not the
# template's.
CONFLICT = re.compile(r"^\+<{7} ")

# A changed `_commit` in the copier answers file. Its presence means the
# working tree *is* a copier update, so the template owned files it rewrote
# were not edited by anyone and are not evidence of anything.
COPIER_UPDATE = re.compile(r"^\+_commit:")

# Colour codes git writes when the user configured `color.diff = always`, which
# it does even when the output is a pipe.
ANSI = re.compile(r"\x1b\[[0-9;]*m")

# The shortest useful `git status --porcelain` record: "XY " and one character
# of path.
MIN_STATUS_FIELD = 4

TIMEOUT = 10


def git(*args: str) -> str | None:
    """Run a git command and return its plain output, or None if it failed.

    "Failed" and "said nothing" must stay apart. `git diff HEAD` exits non-zero
    on an unborn HEAD, and a caller reading that as an empty diff would go half
    blind - seeing every untracked file through `git status` while believing
    nothing had changed. The same applies when git is missing from PATH or
    another process holds `index.lock`.

    The configuration passed here pins the output format the parsers assume:
    colour off (`color.diff` outranks `color.ui` and paints even into a pipe),
    the `a/` and `b/` diff prefixes on, and paths unquoted.
    """
    command = [
        "git",
        "--no-pager",
        "-c",
        "color.ui=false",
        "-c",
        "core.quotePath=false",
        "-c",
        "diff.noprefix=false",
        "-c",
        "diff.mnemonicPrefix=false",
        *args,
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return ANSI.sub("", result.stdout)


def entries(status: str) -> list[tuple[str, str]]:
    """Return the (status, path) pairs of a `git status --porcelain -uall -z`.

    `-z` is what makes this safe to parse: paths arrive verbatim, so neither
    `core.quotePath` nor a space in a name can defeat a prefix or suffix test.
    A rename is emitted as the new path followed by the original one, and only
    the new path is of any interest here.
    """
    fields = [field for field in status.split("\0") if field]
    pairs = []
    index = 0
    while index < len(fields):
        field = fields[index]
        index += 1
        if len(field) < MIN_STATUS_FIELD:
            continue
        code, path = field[:2], field[3:]
        pairs.append((code, path))
        if code[0] in "RC" or code[1] in "RC":
            index += 1  # the original path of a rename or copy
    return pairs


def attributed(diff: str) -> list[tuple[str | None, str]]:
    """Pair every content line of a diff with the file it belongs to.

    A flat scan cannot tell a package's own content from a template owned file
    that merely *writes about* the thing being looked for - a shipped skill
    that quotes a conflict marker would otherwise report the template to
    itself.

    A line whose file could not be established is paired with None, and every
    caller drops those. That happens for a deletion, whose `+++` side is
    `/dev/null`, and it is the safe direction: unattributed evidence is no
    evidence.
    """
    pairs: list[tuple[str | None, str]] = []
    path: str | None = None
    in_header = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            path, in_header = None, True
        elif not in_header:
            pairs.append((path, line))
        elif line.startswith("@@"):
            in_header = False
        elif line.startswith("+++ b/"):
            # Git pads the path with a tab when the name needs it.
            path = line[len("+++ b/") :].split("\t")[0]
    return pairs


def collect_evidence() -> list[str]:
    """Return human readable evidence of template friction."""
    status = git("status", "--porcelain", "-uall", "-z")
    diff = git("diff", "HEAD")
    if status is None or diff is None:
        return []

    pairs = attributed(diff)
    listed = entries(status)
    evidence = []

    # A `copier update` rewrites every template owned path by definition. Do
    # not report the act of taking a new template version as friction with it.
    updating = any(COPIER_UPDATE.match(line) for _, line in pairs)

    touched = sorted({path for _, path in listed if path.startswith(TEMPLATE_OWNED)})
    if touched and not updating:
        evidence.append(f"template owned files were changed here: {', '.join(touched)}")

    rejects = sorted({path for _, path in listed if path.endswith(".rej")})
    if rejects:
        evidence.append(f"a copier update left rejected hunks behind: {', '.join(rejects)}")

    # Conflict markers are the opposite case: one inside a template owned file
    # is precisely the "the update could not be merged" report worth having.
    if any(
        CONFLICT.match(line)
        for path, line in pairs
        if path is not None and path not in CONFLICT_PROSE
    ):
        evidence.append("conflict markers are still in the working tree")

    return evidence


def marker_for(session_id: str) -> Path:
    """Return the once-per-session marker file for a session id."""
    safe = re.sub(r"[^A-Za-z0-9_-]", "", session_id)[:64] or "unknown"
    return Path(tempfile.gettempdir()) / f"cmem-package-feedback-{safe}"


def main() -> None:
    """Read the hook payload, and block once if there is something to report."""
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, OSError):
        return

    if not isinstance(payload, dict) or payload.get("stop_hook_active"):
        return
    if OPT_OUT.exists():
        return

    marker = marker_for(str(payload.get("session_id", "")))
    if marker.exists():
        return

    evidence = collect_evidence()
    if not evidence:
        return

    try:
        marker.touch()
    except OSError:
        return

    reason = (
        "Before finishing: this session shows signs that something in the "
        "cmem-package-template got in the way - "
        + "; ".join(evidence)
        + ". Consider whether that is a finding other generated packages would "
        "share. If it is, use the 'template-feedback' skill to check what has "
        "already been decided and to draft an issue for the template, which "
        "you must show the user before filing anything. If it is specific to "
        "this package, say so in one sentence and stop - that is a complete "
        "answer and this check will not ask again in this session."
    )
    json.dump({"decision": "block", "reason": reason}, sys.stdout)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
```

- [ ] **Step 4: Write `settings.json`**

`src/{{ '.claude' }}/settings.json`:

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

`gh issue create` is deliberately absent: the permission prompt is the last checkpoint before something becomes public.

- [ ] **Step 5: Ignore personal permissions in generated packages**

Append to `src/.gitignore`:

```text
.claude/settings.local.json
```

- [ ] **Step 6: Run the test to verify it passes**

```bash
TEST_CASE=eccenca-testing-vocab task check:generate:case
TEST_CASE=eccenca-testing-vocab task check:hook:case
```

Expected: PASS, both commands silent. Confirm the rendering while you are there:

```bash
ls -la eccenca-testing-vocab_dir/.claude eccenca-testing-vocab_dir/.claude/hooks
```

Expected: a literal `.claude` directory containing `settings.json` and `hooks/template-feedback.py` — no `{{` anywhere in the names.

- [ ] **Step 7: Hand-run the positive path, which the smoke test cannot cover**

```bash
cd eccenca-testing-vocab_dir
echo "# provoke the hook" >> Taskfile.yaml
printf '%s' '{"hook_event_name":"Stop","session_id":"hand-1","stop_hook_active":false}' \
    | python3 .claude/hooks/template-feedback.py; echo
printf '%s' '{"hook_event_name":"Stop","session_id":"hand-1","stop_hook_active":false}' \
    | python3 .claude/hooks/template-feedback.py; echo
git checkout Taskfile.yaml
cd ..
```

Expected: the first run prints a JSON object whose `reason` contains
`template owned files were changed here: Taskfile.yaml`; the second prints
nothing, because the session marker already exists. Record both outputs in the
task report.

- [ ] **Step 8: Commit**

```bash
git add Taskfile.yaml src/.gitignore "src/{{ '.claude' }}"
git commit -S -m "ship a session end check for template friction into generated packages"
```

---

### Task 2: The shipped rules file

**Files:**
- Create: `src/{{ '.claude' }}/rules/copier-template.md`

**Interfaces:**
- Consumes: the hook and opt-out file from Task 1 — the rules describe both.
- Produces: the prose every generated package's agent reads. Task 3's skill assumes the reader has met the terms *template owned file* and *template feedback* here.

- [ ] **Step 1: Read the upstream original**

```bash
cat "/Users/seebi/Repositories/plugins/cmem-plugin-template/src/{{ '.claude' }}/rules/copier-template.md"
```

Note what it does: it names the owned files, says where project specific things go instead, and names the moments worth reporting. Its lint and typing sections have no counterpart here.

- [ ] **Step 2: Write the file**

```bash
mkdir -p "src/{{ '.claude' }}/rules"
```

`src/{{ '.claude' }}/rules/copier-template.md`:

```markdown
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
```

- [ ] **Step 3: Verify it renders**

```bash
TEST_CASE=eccenca-testing-project task check:generate:case
cat eccenca-testing-project_dir/.claude/rules/copier-template.md | head -20
```

Expected: the file exists at a literal path, with no unrendered Jinja.

- [ ] **Step 4: Commit**

```bash
git add "src/{{ '.claude' }}/rules"
git commit -S -m "ship rules telling generated packages which files the template owns"
```

---

### Task 3: The shipped `template-feedback` skill

**Files:**
- Create: `src/{{ '.claude' }}/skills/template-feedback/SKILL.md`

**Interfaces:**
- Consumes: the hook's `reason` text from Task 1, which names this skill by the slug `template-feedback`; the vocabulary established by Task 2's rules.
- Produces: the drafting and filing procedure, and the body layout that Task 4's issue form must match heading for heading.

- [ ] **Step 1: Read the upstream original**

```bash
cat "/Users/seebi/Repositories/plugins/cmem-plugin-template/src/{{ '.claude' }}/skills/template-feedback/SKILL.md"
```

- [ ] **Step 2: Write the file**

```bash
mkdir -p "src/{{ '.claude' }}/skills/template-feedback"
```

`src/{{ '.claude' }}/skills/template-feedback/SKILL.md`:

```markdown
---
name: template-feedback
description: Report a finding upstream to the cmem-package-template - check what has already been decided, draft a GitHub issue and file it after the user confirms. Use when a template owned file is wrong or in the way, when a copier update conflict will recur for everyone, or when asked to report something to the template.
---

# Reporting a finding to the template

This project is generated from
[cmem-package-template](https://github.com/eccenca/cmem-package-template) and
receives changes only through `copier update`. Nothing here flows back on its
own, so a finding that would help other generated packages has to be filed as
an issue on the template repository.

The point is not to log everything that happened. It is to move the small
number of findings that are **about the template** out of this project, where
they die, and into the one place a fix can reach every package.

## Does this belong upstream?

Ask whether the finding would still make sense in a package that has nothing
to do with this one. Concretely, upstream material looks like:

- a step in `Taskfile.yaml` or the GitLab pipeline that is missing, wrong or
  fails identically everywhere
- something the generated `cpa-manifest.json` should contain and does not, for
  every package of this type
- a statement in `.claude/rules/` or one of the shipped skills that turned out
  to be wrong or out of date
- a copier question that should have been asked, or one whose validation
  rejects a name it should accept
- a `copier update` conflict that every package will hit
- a pattern this project keeps writing by hand that the template could ship

Anything specific to this project - its vocabulary content, its own
dependencies, a task only it needs - is not template feedback. Put those in
`TaskfileCustom.yaml`, in `CLAUDE.md`, or in this project's own tracker.

Wishes count. "The template could ship X" is a legitimate report as long as it
is argued for packages in general, not just this one.

## Check what has already been decided

Do this before drafting anything. Most findings have been seen before, and a
duplicate costs a maintainer more than it costs you.

1. Search the issues, open **and** closed:

   ```bash
   gh issue list --repo eccenca/cmem-package-template \
       --state all --label template-feedback --search "<keywords>"
   ```

   An **open** match means comment there instead of opening a second issue. A
   **closed** match means it was answered already - read the answer and stop.

2. Read the *Deliberate decisions - please do not re-raise these* section of
   the template's `CLAUDE.md`:
   <https://github.com/eccenca/cmem-package-template/blob/main/CLAUDE.md>

   That section is the list of findings that were considered and rejected on
   purpose. If the finding is there, it is settled. Say so and stop.

3. Skim the template's `CHANGELOG.md` for the `## [Unreleased]` section. It may
   already be fixed and waiting for a release, in which case the answer is to
   update once that release is out.

## Draft the issue

Never file without showing the user the exact title and body first, and never
file without their explicit go-ahead in that turn. This is the only step in
this project that publishes something, it is permanent, and the tracker is
public while most generated packages are not.

**Do not name this repository, and do not paste content from it.** Many
packages generated from this template are private, some of them customer
specific, and naming one on a public tracker publishes a relationship that was
not yours to publish. Describe the finding in general terms; write a minimal
synthetic reproduction if one helps. If naming the project is genuinely useful,
let the user add it when they confirm - they know whether it is public.

What the maintainer needs instead of a name, taken from `.copier-answers.yml`:

- `_commit` - the template version this project was rendered from
- `package_type` - `vocabulary` or `project`
- whether `marketplace` and `github_page` are answered

Title: short and imperative, describing the change to the template - not the
symptom here. Body, following the repository's issue form:

```text
### The finding
<what got in the way, in general terms>

### Why this generalises
<at least one other kind of package this would help>

### Which part of the template
<the file under src/, if known>

### Suggested change
<what the template should do instead>

### Environment
Template version: <_commit>
package_type: <vocabulary|project>
marketplace answered: <yes|no>
github_page answered: <yes|no>
```

## File it

After the user confirms:

```bash
gh issue create --repo eccenca/cmem-package-template \
    --label template-feedback --title "<title>" --body "<body>"
```

This one is not pre-approved in `.claude/settings.json`, so it will ask for
permission. That is deliberate - the prompt is the last checkpoint before
something becomes public.

If `gh` is missing or not authenticated, do not stall and do not look for
another way to publish it. Print the finished title and body together with the
command above, and let the user file it. They can also use the form directly:
<https://github.com/eccenca/cmem-package-template/issues/new?template=template-feedback.yml>

## Turning it off

A project that does not want the session end check can create an empty
`.claude/no-template-feedback` file. This skill still works when invoked
directly; only the automatic reminder goes away.
```

- [ ] **Step 3: Verify it renders and the frontmatter survives**

```bash
TEST_CASE=eccenca-testing-vocab task check:generate:case
head -5 eccenca-testing-vocab_dir/.claude/skills/template-feedback/SKILL.md
```

Expected: the YAML frontmatter with `name: template-feedback`, intact.

- [ ] **Step 4: Commit**

```bash
git add "src/{{ '.claude' }}/skills"
git commit -S -m "ship a skill that drafts template feedback and files it after confirmation"
```

---

### Task 4: The issue form and its label

**Files:**
- Create: `.github/ISSUE_TEMPLATE/template-feedback.yml`

**Interfaces:**
- Consumes: the body layout drafted by Task 3's skill — the headings here and there must match, or a filed issue reads as a mismatch.
- Produces: the `template-feedback` label and the fields Task 5's triage skill reads: the finding, the generalisation argument, the target file, the suggestion, `_commit`, `package_type`, `marketplace`, `github_page`.

- [ ] **Step 1: Write the form**

```bash
mkdir -p .github/ISSUE_TEMPLATE
```

`.github/ISSUE_TEMPLATE/template-feedback.yml`:

```yaml
---
name: Template feedback
description: Report something learned in a generated package that could improve this template
title: "[feedback] "
labels: ["template-feedback"]
body:
  - type: markdown
    attributes:
      value: |
        Use this form for findings that came out of working in a package
        generated from this template - a pipeline step that fails the same way
        everywhere, a missing task, a manifest field every package has to add
        by hand, a statement in the shipped `.claude/` rules or skills that
        turned out to be wrong.

        **Do not name a private or customer specific repository, and do not
        paste content from one.** Most generated packages are private; this
        tracker is public. Describe the finding in general terms and, where a
        reproduction helps, write a minimal synthetic one.

        Before filing, please check the closed issues and the *Deliberate
        decisions - please do not re-raise these* section of
        [`CLAUDE.md`](https://github.com/eccenca/cmem-package-template/blob/main/CLAUDE.md).

  - type: textarea
    id: finding
    attributes:
      label: The finding
      description: What got in the way, in general terms.
    validations:
      required: true

  - type: textarea
    id: generalises
    attributes:
      label: Why this generalises
      description: >
        Name at least one other kind of package this would help. A finding that
        only applies to the package it came from is not template feedback.
    validations:
      required: true

  - type: input
    id: target
    attributes:
      label: Which part of the template
      description: >
        The file under `src/` this concerns, if known - for example
        `src/Taskfile.yaml` or `src/{{ package_id }}/cpa-manifest.json.jinja`.
    validations:
      required: false

  - type: textarea
    id: suggestion
    attributes:
      label: Suggested change
      description: What the template should do instead.
    validations:
      required: false

  - type: input
    id: template-version
    attributes:
      label: Template version
      description: The `_commit` value from the package's `.copier-answers.yml`.
      placeholder: v1.5.0
    validations:
      required: true

  - type: dropdown
    id: package-type
    attributes:
      label: package_type
      options:
        - vocabulary
        - project
    validations:
      required: true

  - type: checkboxes
    id: answers
    attributes:
      label: Other copier answers
      options:
        - label: "`marketplace` is answered yes"
        - label: "`github_page` is answered"
```

Note: this file lives at the repository root, **not** under `src/`. It is not
rendered by copier and the `{{ package_id }}` in the description text is
literal prose for a human reader.

- [ ] **Step 2: Create the label, which does not exist yet**

```bash
gh label create template-feedback \
    --repo eccenca/cmem-package-template \
    --color BFD4F2 \
    --description "Finding reported from a generated package"
```

Expected: `✓ Label "template-feedback" created`. A form silently drops a label
the repository does not have, so this step is not optional. If the label
already exists, `gh` says so and that is fine.

- [ ] **Step 3: Verify the form parses**

```bash
python3 -c "import yaml,sys; yaml.safe_load(open('.github/ISSUE_TEMPLATE/template-feedback.yml')); print('ok')"
```

Expected: `ok`. GitHub only validates on push, so this catches the syntax half
early; confirm the form renders after the branch is pushed by opening
<https://github.com/eccenca/cmem-package-template/issues/new/choose>.

- [ ] **Step 4: Commit**

```bash
git add .github/ISSUE_TEMPLATE/template-feedback.yml
git commit -S -m "add an issue form for findings reported from generated packages"
```

---

### Task 5: The maintainer-side `template-triage` skill

**Files:**
- Create: `.claude/skills/template-triage/SKILL.md`

**Interfaces:**
- Consumes: the issue fields from Task 4 and the `template-feedback` label.
- Produces: the procedure that turns an issue into either a `src/` commit or an entry in the *Deliberate decisions* section that Task 6 creates. It references that section by name; Task 6 must use exactly that heading.

- [ ] **Step 1: Read the upstream original**

```bash
cat /Users/seebi/Repositories/plugins/cmem-plugin-template/.claude/skills/template-triage/SKILL.md
```

- [ ] **Step 2: Write the file**

```bash
mkdir -p .claude/skills/template-triage
```

`.claude/skills/template-triage/SKILL.md`:

```markdown
---
name: template-triage
description: Triage template-feedback issues reported from generated packages - decide each one against the deliberate decisions, implement the accepted ones in src/ with changelog entries on a feature branch, and draft the decline text for the rest. Use when asked to triage, review or work through the template-feedback issues.
---

# Triaging template feedback

Packages generated from this template report findings back as issues labelled
`template-feedback`, filed through
`.github/ISSUE_TEMPLATE/template-feedback.yml`. The reporting side is the
`template-feedback` skill shipped in `src/{{ '.claude' }}/skills/`.

**This skill belongs to this repository, not to generated packages.** Unlike
`release`, it has no twin under `src/` - triage edits `src/`, which would be
nonsense inside a generated package. See the root / `src/` split in
`CLAUDE.md`.

A finding arrives from a package you cannot see, filtered through an agent that
could not name it. Treat the report as a claim to verify, not as a fact.

## What triage is for

Every accepted finding changes `src/`, and everything in `src/` reaches every
downstream package on its next `copier update`. Every declined finding has to
end up somewhere the *next* package's agent will look, or the same report
arrives again from the next repository, and the one after that. Both halves
matter; the decline half is the one that gets skipped.

## Preconditions

1. The working tree is clean and you are on `develop`.
2. Create a feature branch - never work on `develop` directly:

   ```bash
   git switch -c feature/template-feedback-triage
   ```

3. List what is waiting:

   ```bash
   gh issue list --repo eccenca/cmem-package-template \
       --state open --label template-feedback
   ```

## Decide each issue

Read the issue in full, then check it in this order and stop at the first hit:

1. **Already decided.** Compare against *Deliberate decisions - please do not
   re-raise these* in `CLAUDE.md`. If it is there, **decline it and do not
   implement it**, however well the issue argues its case. Re-opening a settled
   decision from a triage sweep is exactly how that section stops being worth
   reading. Changing one of those decisions is a human call, made deliberately,
   not a side effect of working through a list.
2. **Already fixed.** Check `## [Unreleased]` in `CHANGELOG.md` and the current
   state of `src/`. If it is fixed and waiting for a release, say so and close
   the issue pointing at the entry.
3. **Not template material.** The finding only holds for the package it came
   from, or it asks for something a package should put in `TaskfileCustom.yaml`
   or its own `CLAUDE.md`. Decline.
4. **Wrong side of the split.** The finding is about this repository's own CI,
   its own `Taskfile.yaml` or its own `.claude/` - not about `src/`. That is a
   real report, but it is not a change to what users receive. Handle it as
   ordinary work and drop the `template-feedback` framing.
5. Otherwise, **accept**.

Weigh an accepted finding against both `package_type`s and against
`marketplace` and `github_page` being answered either way. A change that only
makes sense for project packages belongs behind a
`package_type != 'vocabulary'` condition, not in the shared path - vocabulary
packages cannot declare dependencies at all, which is why the dependency
questions are already conditional.

## Implement an accepted finding

One issue, one commit. A sweep that lands several findings in a single diff
cannot be reviewed finding by finding, and a bad one cannot be dropped without
unpicking the good ones.

For each accepted issue:

1. Make the change in `src/`. Remember that filenames there are Jinja, that
   `.gitlab-ci.yml.jinja` and `cpa-manifest.json.jinja` are rendered and need
   literal `{{` and `{%` escaped, and that `_preserve_symlinks` keeps the links
   inside the package directory pointing at the top level originals.
2. Add a `CHANGELOG.md` entry under `## [Unreleased]`, following the
   conventions in `CLAUDE.md`. Say what a template user notices and leave why
   the old code was wrong to the commit message, and extend an existing entry
   rather than adding a parallel one when two findings land in the same file.
3. Commit both together, closing the issue from the subject:

   ```bash
   git commit -S -m "<what changed>, fixes #<issue>"
   ```

   The closing keyword has to be in the commit subject. A `Fixes #…` line in a
   pull request body does nothing here, because the pull request targets
   `develop` and GitHub only creates closing references against the default
   branch.

Do not tag and do not release. Releasing is `/release`, and it is a separate,
deliberate step.

Note when the issue actually closes: the keyword fires when the commit reaches
`main`, which happens at release time, not when the pull request is merged into
`develop`. Say so when reporting, so nobody reads the delay as broken
automation. Anything that needs closing sooner has to be closed by hand.

## Decline an issue

Declining is not just closing. Add the reasoning to the *Deliberate decisions -
please do not re-raise these* section of `CLAUDE.md`, in the same voice as the
entries already there: what it looks like, why it is not that, and what was
weighed. That section is what the reporting skill tells generated packages to
read before filing, so an entry there is what stops the finding coming back.

Then close the issue with a comment that says the same thing in short and links
to the section.

Skip the `CLAUDE.md` entry only for a finding nobody could reasonably repeat -
a one-off mistake in the report itself, not a judgement call about the
template.

## Finish

```bash
task check
```

This renders every test case, smoke tests the shipped hook and runs each
generated package's own checks against a live Corporate Memory deployment, so
it needs `CMEM_BASE_URI` and `OAUTH_CLIENT_SECRET` and serialises against the
nightly run. It must be green before you report done. Note what it does *not*
cover: it never runs a generated package's GitLab pipeline, and beyond the
`check:hook:case` smoke test it never exercises the shipped agent files. A
finding about a skill or the pipeline needs a hand run in a rendered case.

Before summarising, read `## [Unreleased]` as a whole. Repetition is invisible
while writing one entry at a time and obvious once the section is read end to
end. Condense it in its own commit.

Then summarise: what was accepted and implemented, what was declined and where
the reasoning now lives, and what still needs a human decision.
```

- [ ] **Step 3: Verify the skill is discoverable**

```bash
head -5 .claude/skills/template-triage/SKILL.md
ls .claude/skills
```

Expected: `release` and `template-triage` side by side, and valid frontmatter.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/template-triage
git commit -S -m "add a triage skill for feedback arriving from generated packages"
```

---

### Task 6: Document the loop and record the first decisions

**Files:**
- Modify: `CLAUDE.md` (two new sections, one amended section)
- Modify: `CHANGELOG.md` (replace the `## [Unreleased]` placeholder)

**Interfaces:**
- Consumes: every file created in Tasks 1–5.
- Produces: the *Deliberate decisions — please do not re-raise these* heading that Task 3's skill links to and Task 5's skill writes into. The heading text must match exactly.

- [ ] **Step 1: Add the feedback section to `CLAUDE.md`**

Insert after the *Generated package anatomy* section and before *Branching and release process*:

```markdown
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
changelog entry; declined ones become an entry in the section below, which is
what stops them coming back.

`task check` covers exactly one part of this: `check:hook:case` asserts that
the shipped hook stays silent on a clean tree and respects `stop_hook_active`.
It cannot tell you the hook fires on the right evidence — that needs a hand run
in a rendered case, piping a `Stop` payload into
`<case>_dir/.claude/hooks/template-feedback.py`.
```

- [ ] **Step 2: Add the decisions section to `CLAUDE.md`**

Append at the end of the file:

```markdown
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
```

- [ ] **Step 3: Mention the shipped payload in *Generated package anatomy***

Add as a final bullet of that section:

```markdown
- `src/{{ '.claude' }}/` ships agent support into every generated package —
  rules, the `template-feedback` skill, the `Stop` hook and `settings.json`.
  The quoted-expression directory name is deliberate; see *Feedback from
  generated packages*.
```

- [ ] **Step 4: Replace the changelog placeholder**

In `CHANGELOG.md`, replace

```markdown
## [Unreleased]

TODO: add at least one Added, Changed, Deprecated, Removed, Fixed or Security section
```

with

```markdown
## [Unreleased]

### Added

- Generated packages now ship a `.claude/` directory: rules describing which files the template owns and where project specific additions go, a `template-feedback` skill that drafts an issue for the template's tracker, and a session end check that notices when a template owned file got in the way
  - the check is a blocking `Stop` hook and speaks only on evidence; a package switches it off with an empty `.claude/no-template-feedback` file
  - nothing is filed without the user seeing the exact issue text and confirming it
```

- [ ] **Step 5: Verify the cross-references resolve**

```bash
grep -n "Deliberate decisions" CLAUDE.md .claude/skills/template-triage/SKILL.md
grep -rn "Deliberate decisions" "src/{{ '.claude' }}/skills/template-feedback/SKILL.md"
```

Expected: the heading in `CLAUDE.md` and both references use the same wording,
*Deliberate decisions - please do not re-raise these*. The `CLAUDE.md` heading
uses an em dash and the skills use a hyphen inside running prose; that is fine,
but the phrase must otherwise match.

- [ ] **Step 6: Run the full suite**

```bash
task check
```

Expected: PASS. Needs `CMEM_BASE_URI` and `OAUTH_CLIENT_SECRET`, and must not
run while the nightly GitHub check is in flight. If credentials are not
available, run `task check:generate:cases` plus
`TEST_CASE=<case> task check:hook:case` for both cases and say explicitly in
the report that the live half was not run.

- [ ] **Step 7: Commit**

```bash
git add CLAUDE.md CHANGELOG.md
git commit -S -m "document the feedback cycle and seed the deliberate decisions"
```

---

## After the plan

The branch is ready for a pull request into `develop`. Do not tag and do not
release; `/release` is a separate, deliberate step, and a release is what
actually delivers the shipped `.claude/` payload to users, because
`copier copy` resolves the newest tag.

One step lives outside git and outside CI: `gh label create template-feedback`
in Task 4. Confirm the label exists before the first report arrives.
