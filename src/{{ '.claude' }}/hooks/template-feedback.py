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


def owned(path: str) -> bool:
    """Say whether a path is one the template writes.

    A plain prefix test is wrong here: `Taskfile.yaml.rej` starts with
    `Taskfile.yaml` without being it, and reporting a rejected hunk as an edit
    to a template owned file describes something that did not happen. A
    directory entry matches everything below it; a file entry matches only
    itself.
    """
    return any(
        path.startswith(entry) if entry.endswith("/") else path == entry
        for entry in TEMPLATE_OWNED
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

    touched = sorted({path for _, path in listed if owned(path)})
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
