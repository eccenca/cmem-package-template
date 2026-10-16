#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Remind the session of the skills that cover a file when it is about to change it.

This is a Claude Code ``PreToolUse`` hook, registered in ``.claude/settings.json`` for
Edit, MultiEdit, Write, NotebookEdit and Bash, and run directly, not through a task,
because stdout is the hook's JSON channel.

When a rule in ``.claude/skill-map.json`` or the project's own
``.claude/skill-map.custom.json`` maps the file being edited - or a path a shell
command names - to a skill, the hook adds context to the tool call naming the skill
and its ``SKILL.md``, so the model reads the convention at the moment it applies it.
It never denies anything: whether a skill is "loaded" cannot be proven from inside a
hook (a subagent's transcript is not the one the payload names, a resumed session
carries no marker, a plugin's skill can share the name), and a refusal built on such
a proof locks a session out of its own package. A reminder that is not needed costs
one line of context.

A hand run needs a payload on stdin::

    echo '{"tool_name": "Edit", "tool_input": {"file_path": "my-pkg/cpa-manifest.json"}}' \\
        | .claude/hooks/skill-check.py

It belongs to the template - see ``.claude/rules/copier-template.md``. Project
specific rules go into ``.claude/skill-map.custom.json``, which the template never
writes and ``task check:offline`` validates. A project switches the hook off with an
empty ``.claude/no-skill-check``.

The same file also serves as a user-level hook (a symlink in ``~/.claude/hooks``) for
sessions that work on a package from outside it. It then finds the package from the
path being changed, reads the map beside itself when the package has none (packages
generated before the hook shipped), and stays quiet where the package's own copy of
the hook already runs.

Print nothing unless there is something to say, and always exit 0: a broken hook must
never stall a session.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
from pathlib import Path

# The template's rules and the project's own, both relative to the package root.
MAP = Path(".claude") / "skill-map.json"
CUSTOM_MAP = Path(".claude") / "skill-map.custom.json"

OPT_OUT = Path(".claude") / "no-skill-check"

# The package's own skills; the reminder points at their SKILL.md.
SKILLS = Path(".claude") / "skills"

# The package's own copy of this hook, registered in its settings.json.
OWN_HOOK = Path(".claude") / "hooks" / "skill-check.py"

FILE_TOOLS = ("Edit", "MultiEdit", "Write", "NotebookEdit")

# Content patterns name RDF terms, so they are matched in RDF files only. Matched
# against prose or code they fire on a changelog line about owl:Class, on this hook's
# own map, and on the checkers in bin/ that look for those terms.
RDF_SUFFIXES = (".ttl", ".trig", ".nt", ".ttl.graph", ".ttl.imports")

# A file larger than this is judged by its path only; content patterns are for the
# hand-written catalogs and vocabularies, not for mirrored data dumps.
MAX_READ = 5 * 1024 * 1024

# Words of a shell command that cannot name a file of the package.
NOT_A_PATH = re.compile(r"^-|[*?$`{}\[\]]|^\w+://")


def package_root(path: Path) -> Path | None:
    """The generated package a path belongs to: the nearest folder with copier answers that are this template's.

    A package rendered by this template has the skill map; one generated before the map
    shipped is known by its answers naming the template. Neither alone: the answers' source
    is "." or a mirror's path when the package was rendered from a local checkout, and any
    copier project has answers.
    """
    for folder in (path, *path.parents):
        answers = folder / ".copier-answers.yml"
        try:
            if answers.is_file() and ((folder / MAP).is_file()
                                      or "cmem-package-template" in answers.read_text(errors="ignore")):
                return folder
        except OSError:
            continue
    return None


def rule_problem(rule: object) -> str | None:
    if not isinstance(rule, dict) or not isinstance(rule.get("skill"), str) or not rule["skill"]:
        return 'a rule is an object with a "skill" name'
    for key in ("paths", "content", "exclude"):
        value = rule.get(key, [])
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            return f'"{key}" must be a list of strings'
    for pattern in rule.get("content", []):
        try:
            re.compile(pattern)
        except re.error as error:
            return f"content pattern {pattern!r} is not a regular expression ({error})"
    return None


def read_map(path: Path, label: str) -> tuple[list[dict], list[str]]:
    """The usable rules of one map file, and what is wrong with the rest.

    A broken rule is dropped on its own and a file that does not parse drops that file
    only, so a typo in the project's map never switches off the template's rules.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data.get("rules", []) if isinstance(data, dict) else None
        if not isinstance(entries, list):
            raise ValueError('expected an object with a "rules" list')
    except (OSError, ValueError) as error:
        return [], [f"{label} does not parse ({error}), so none of its rules apply"]
    rules, errors = [], []
    for index, rule in enumerate(entries):
        problem = rule_problem(rule)
        if problem:
            errors.append(f"rule {index + 1} of {label} is ignored: {problem}")
        else:
            rules.append(rule)
    return rules, errors


class Package:
    """One generated package: its rules, what is wrong with them, and its skills."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.rules: list[dict] = []
        self.errors: list[str] = []
        self.fallback = False
        self.sources: list[str] = []
        maps = [(root / MAP, str(MAP)), (root / CUSTOM_MAP, str(CUSTOM_MAP))]
        if not (root / MAP).is_file():
            # A package generated before the hook shipped has no map of its own; a
            # user-level copy of the hook brings one beside itself.
            beside = Path(os.path.abspath(__file__)).with_name("skill-map.json")
            if beside.is_file() and package_root(beside.parent) is None:
                maps[0] = (beside, str(beside))
                self.fallback = True
        for path, label in maps:
            if path.is_file():
                self.sources.append(label)
                rules, errors = read_map(path, label)
                self.rules += rules
                self.errors += errors

    def skill_file(self, skill: str) -> Path | None:
        path = self.root / SKILLS / skill / "SKILL.md"
        return path if path.is_file() else None

    def required(self, names: set[str], text: str) -> list[str]:
        """The skills a file needs: every rule whose path glob or content pattern matches.

        ``names`` holds every spelling of the file relative to the root - as given and
        with symlinks resolved - so a rule written against ``*/README.md`` still fires
        on the package directory's link. ``*`` in a glob crosses ``/``, which is what
        ``exclude`` is for. A skill the package does not ship is skipped, unless the
        rules came from the user-level map, whose skills live outside the package.
        """
        rdf = any(name.endswith(RDF_SUFFIXES) for name in names)
        skills = []
        for rule in self.rules:
            if any(fnmatch.fnmatch(n, p) for n in names for p in rule.get("exclude", [])):
                continue
            by_path = any(fnmatch.fnmatch(n, p) for n in names for p in rule.get("paths", []))
            by_content = rdf and bool(text) and any(re.search(p, text) for p in rule.get("content", []))
            skill = rule["skill"]
            if (by_path or by_content) and skill not in skills and (self.fallback or self.skill_file(skill)):
                skills.append(skill)
        return skills


def spellings(path: Path, root: Path) -> set[str]:
    """Every way the file is named relative to the root; empty when it lies outside."""
    names = set()
    for candidate in (path, path.resolve()):
        try:
            names.add(candidate.relative_to(root).as_posix())
        except ValueError:
            continue
    return names


def file_text(path: Path) -> str:
    try:
        if path.stat().st_size <= MAX_READ:
            return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        pass
    return ""


def edit_text(tool_input: dict, path: Path) -> str:
    """What the file will hold: its current text plus every piece being written.

    Judging the replacement alone would miss an edit inside a ``shui:queryText`` block
    and every deletion.
    """
    parts = [str(tool_input.get(k, "")) for k in ("content", "new_string", "new_source")]
    for change in tool_input.get("edits") or []:
        if isinstance(change, dict):
            parts.append(str(change.get("new_string", "")))
    parts.append(file_text(path))
    return "\n".join(parts)


def touched_by_edit(event: dict, cwd: Path) -> list[tuple[Path, str]]:
    tool_input = event.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not raw:
        return []
    path = Path(os.path.abspath(cwd / os.path.expanduser(raw)))
    return [(path, edit_text(tool_input, path))]


def touched_by_command(event: dict, cwd: Path) -> list[tuple[Path, str]]:
    """Every path a shell command names, read or written - the hook cannot tell which, and needs not."""
    command = str((event.get("tool_input") or {}).get("command", ""))
    paths: list[tuple[Path, str]] = []
    base, after_cd = cwd, False
    for word in re.findall(r"[^\s'\"`;&|<>()=,]+", command):
        if after_cd:
            # a later word is relative to where the command went, as the shell resolves it
            after_cd = False
            if not NOT_A_PATH.search(word):
                base = Path(os.path.abspath(base / os.path.expanduser(word)))
                continue
        if word == "cd":
            after_cd = True
            continue
        if NOT_A_PATH.search(word) or ("/" not in word and "." not in word and not (base / word).exists()):
            continue
        path = Path(os.path.abspath(base / os.path.expanduser(word)))
        if path not in [p for p, _ in paths]:
            paths.append((path, file_text(path) if path.name.endswith(RDF_SUFFIXES) else ""))
    return paths


def reminder(package: Package, files: list[tuple[str, list[str]]]) -> str:
    lines = []
    for name, skills in files:
        named = []
        for skill in skills:
            path = package.skill_file(skill)
            named.append(f"{skill} ({path.relative_to(package.root).as_posix()})" if path else skill)
        lines.append(f"{name} is covered by the skill(s) {', '.join(named)}.")
    # The note reaches the session with the tool's result, after an edit has already been made, so it asks for a
    # check of that change rather than for care before it (fresh-agent test, 2026-10-16: a CHANGELOG line written
    # first, the skill loaded after, the line never looked at again).
    lines.append("If this session has not loaded them yet, load them now with the Skill tool, check the change "
                 "this note comes with against them, and fix what departs. "
                 f"(Rules: {' and '.join(package.sources)})")
    return " ".join(lines)


def main() -> None:
    event = json.load(sys.stdin)
    if not isinstance(event, dict):
        return
    tool = event.get("tool_name")
    cwd = Path(event.get("cwd") or os.getcwd())
    if tool in FILE_TOOLS:
        touched = touched_by_edit(event, cwd)
    elif tool == "Bash":
        touched = touched_by_command(event, cwd)
    else:
        return

    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or cwd).resolve()
    hook = Path(os.path.abspath(__file__))
    packages: dict[Path, Package] = {}
    found: dict[Path, list[tuple[str, list[str]]]] = {}
    for path, text in touched:
        root = package_root(path.parent)
        if root is None or (root / OPT_OUT).exists():
            continue
        # A user-level copy stands down where the package's own hook runs as well.
        if not spellings(hook, root) and root.resolve() == project and (root / OWN_HOOK).is_file():
            continue
        package = packages.setdefault(root, Package(root))
        names = spellings(path, root)
        skills = package.required(names, text)
        files = found.setdefault(root, [])
        if skills:
            files.append((sorted(names)[0], skills))

    parts = []
    for root, files in found.items():
        package = packages[root]
        if files:
            parts.append(reminder(package, files))
        if package.errors:
            parts.append("The skill map cannot be read in full - " + "; ".join(package.errors) +
                         ". Fix it (task check:offline names the same), or the files its rules cover get no reminder.")
    if parts:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                 "additionalContext": " ".join(parts)}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - a broken hook must never stall a session
        pass
