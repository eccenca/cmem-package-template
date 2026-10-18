#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Validate the project's own skill map, .claude/skill-map.custom.json.

The skill check hook (.claude/hooks/skill-check.py) reminds a session of the skill that
covers a file when the file is edited. A project adds rules for its own files and skills
in .claude/skill-map.custom.json. The hook skips a rule it cannot use and says so only in
the session that hits it, so a typo here would quietly take that rule's reminders away.
This names every problem before the package goes anywhere.

    check_skill_map.py <project-root>

Silent when the map is fine or absent; on a problem it prints each one and exits 1.
Checked: the file is JSON with a "rules" list; each rule names a skill, and "paths",
"content" and "exclude" are lists of strings; each content pattern is a regular
expression; each named skill exists in .claude/skills/ (a rule for a skill the project
does not have reminds of nothing).
"""

import json
import re
import sys
from pathlib import Path

CUSTOM_MAP = Path(".claude") / "skill-map.custom.json"
SKILLS = Path(".claude") / "skills"


def problems(root: Path) -> list[str]:
    path = root / CUSTOM_MAP
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [f"{CUSTOM_MAP} does not parse: {error}"]
    rules = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(rules, list):
        return [f'{CUSTOM_MAP} must be an object with a "rules" list']
    found = []
    for number, rule in enumerate(rules, 1):
        where = f"{CUSTOM_MAP} rule {number}"
        if not isinstance(rule, dict) or not isinstance(rule.get("skill"), str) or not rule["skill"]:
            found.append(f'{where}: a rule is an object with a "skill" name')
            continue
        for key in ("paths", "content", "exclude"):
            value = rule.get(key, [])
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                found.append(f'{where} ({rule["skill"]}): "{key}" must be a list of strings')
        for pattern in rule.get("content", []) if isinstance(rule.get("content"), list) else []:
            try:
                re.compile(pattern)
            except (re.error, TypeError) as error:
                found.append(f"{where} ({rule['skill']}): content pattern {pattern!r} is not a regular expression ({error})")
        if not (root / SKILLS / rule["skill"] / "SKILL.md").is_file():
            found.append(f"{where}: skill {rule['skill']!r} has no {SKILLS}/{rule['skill']}/SKILL.md")
        if not rule.get("paths") and not rule.get("content"):
            found.append(f"{where} ({rule['skill']}): no \"paths\" and no \"content\", so it never applies")
    return found


def main() -> int:
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_dir():
        sys.exit(__doc__)
    found = problems(Path(sys.argv[1]))
    for problem in found:
        print(f"FAIL: {problem}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
