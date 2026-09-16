#!/usr/bin/env python3
"""Assert that a rendered test case ships the skills it should.

Run from inside a generated package directory; `check:skills:case` does that.
It answers one question only - did the right skill files arrive, intact - and
deliberately says nothing about whether their content is any good. That is a
hand read, and pretending otherwise would make `task check` look like it covers
the skills when it does not.

Exits non-zero with a one-line reason on the first failure.
"""

import re
import sys
from pathlib import Path

# Skills every generated package gets, whatever it answered.
ALWAYS = ("template-feedback", "package-content")

# Skills a vocabulary package must NOT get: a vocabulary package ships one
# ontology graph and an icon, so a build project and a shape catalog are things
# it will never have. They are dropped by a conditional directory name.
PROJECT_ONLY = ("build-projects", "shapes")

SKILLS = Path(".claude") / "skills"

# A Jinja delimiter surviving into a rendered *name* means the name was not
# treated as a template. Bodies are deliberately not checked: copier's default
# `_templates_suffix` is `.jinja`, so every file here is copied verbatim, and a
# skill may legitimately contain `{{ ... }}` - a shape query placeholder, a
# Taskfile variable, an example of the template's own syntax.
LEFTOVER = re.compile(r"\{\{|\{%")

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def fail(message: str) -> None:
    """Report one reason and stop."""
    print(f"check-skills: {message}")
    sys.exit(1)


def package_type() -> str:
    """Return the package_type this case was rendered with."""
    answers = Path(".copier-answers.yml")
    if not answers.exists():
        fail(".copier-answers.yml is missing, cannot tell which skills to expect")
    for line in answers.read_text(encoding="utf-8").splitlines():
        if line.startswith("package_type:"):
            return line.split(":", 1)[1].strip().strip("\"'")
    fail("no package_type in .copier-answers.yml")
    return ""  # unreachable, keeps type checkers quiet


def check_skill(name: str) -> None:
    """Assert one skill directory holds a well formed SKILL.md."""
    skill = SKILLS / name / "SKILL.md"
    if not skill.is_file():
        fail(f"{skill} is missing")
    text = skill.read_text(encoding="utf-8")
    match = FRONTMATTER.match(text)
    if not match:
        fail(f"{skill} has no YAML frontmatter")
    fields = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "-")):
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    if fields.get("name") != name:
        fail(f"{skill} declares name {fields.get('name')!r}, expected {name!r}")
    if not fields.get("description"):
        fail(f"{skill} has no description, so nothing will ever load it")
    for path in (SKILLS / name).rglob("*"):
        if LEFTOVER.search(str(path)):
            fail(f"{path} still has Jinja in its name")


def check_hook_agrees() -> None:
    """Assert the hook's owned-path list names exactly the shipped skills.

    The hook reports an edit to a template owned file, and it owns the skills
    this template ships - but not a skill the project wrote itself, which lives
    in the same directory. It therefore names them one by one, and that list has
    to move whenever this one does. Getting it wrong is silent in both
    directions: a missing entry stops reporting a real edit, a stale entry
    reports the project for its own work.
    """
    hook = Path(".claude") / "hooks" / "template-feedback.py"
    if not hook.is_file():
        return
    listed = set(re.findall(r'"\.claude/skills/([^/"]+)/"', hook.read_text(encoding="utf-8")))
    known = set(ALWAYS) | set(PROJECT_ONLY)
    if listed != known:
        fail(
            f"{hook} owns skills {sorted(listed)}, this check expects {sorted(known)}"
        )


def main() -> None:
    """Check the skills this package should and should not have."""
    if not SKILLS.is_dir():
        fail(f"{SKILLS} does not exist")

    kind = package_type()
    for name in ALWAYS:
        check_skill(name)

    if kind == "vocabulary":
        for name in PROJECT_ONLY:
            if (SKILLS / name).exists():
                fail(f"{SKILLS / name} shipped into a vocabulary package")
    else:
        for name in PROJECT_ONLY:
            check_skill(name)

    check_hook_agrees()

    expected = set(ALWAYS) | (set() if kind == "vocabulary" else set(PROJECT_ONLY))
    found = {d.name for d in SKILLS.iterdir() if d.is_dir()}
    if found != expected:
        fail(f"unexpected skill directories: {sorted(found - expected)}")

    print(f"check-skills: ok ({kind}: {', '.join(sorted(expected))})")


if __name__ == "__main__":
    main()
