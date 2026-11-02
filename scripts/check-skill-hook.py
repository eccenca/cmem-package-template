#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Test the skill check hook a generated package ships.

Run from inside a generated package directory; `check:skillhook:case` does that.

The hook only ever adds context, so what can go wrong is a reminder missing where a
skill covers the file, a reminder on a file nothing maps, and anything that stops a
tool call: a decision other than context, or an exit code other than 0. All three are
asserted, for file edits and for shell commands, and so are the two ways a session
works on a package from outside it: a user-level copy of the hook with its own map
for a package generated before the hook shipped, and standing down where the
package's own copy runs.

The rendered hook is run by path, as `settings.json` runs it, so the shebang and the
executable bit are exercised too. The package it judges is a throwaway one holding
the rendered package's skill map and skills.

What this cannot tell you is whether the rules in skill-map.json cover the right files
in a real package. That is a hand read.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = (Path(".claude") / "hooks" / "skill-check.py").resolve()
SETTINGS = Path(".claude") / "settings.json"

VOCAB = "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n<urn:x> a owl:Ontology .\n"
ANSWERS = "_commit: v1.0.0\n_src_path: gh:eccenca/cmem-package-template\npackage_type: project\n"


def fail(message: str) -> None:
    print(f"check-skill-hook: {message}")
    sys.exit(1)


class Case:
    """A throwaway package holding the rendered skill map and skills."""

    def __init__(self, tmpdir: str, name: str, with_map: bool = True, answers: str = ANSWERS) -> None:
        self.root = Path(tmpdir) / name
        (self.root / ".claude").mkdir(parents=True)
        if with_map:
            shutil.copy(Path(".claude") / "skill-map.json", self.root / ".claude" / "skill-map.json")
        shutil.copytree(Path(".claude") / "skills", self.root / ".claude" / "skills")
        self.write(".copier-answers.yml", answers)
        self.write("my-pkg/cpa-manifest.json", "{}\n")
        self.write("my-pkg/demo-vocab.ttl", VOCAB)
        self.write("my-pkg/data.ttl", VOCAB)

    def write(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def run(self, payload: dict, hook: Path = HOOK, project: Path | None = None) -> str:
        environment = dict(os.environ, CLAUDE_PROJECT_DIR=str(project or self.root))
        result = subprocess.run([str(hook)], input=json.dumps(payload), capture_output=True,
                                text=True, check=False, env=environment)
        if result.returncode != 0:
            fail(f"the hook exited {result.returncode}; it must always exit 0\n{result.stderr}")
        return result.stdout.strip()

    def edit(self, relative: str, tool: str = "Edit", text: str = "b", **run) -> str:
        path = relative if relative.startswith("/") else str(self.root / relative)
        tool_input = {"file_path": path, "old_string": "a", "new_string": text}
        if tool == "MultiEdit":
            tool_input = {"file_path": path, "edits": [{"old_string": "a", "new_string": text}]}
        return self.run({"hook_event_name": "PreToolUse", "tool_name": tool, "cwd": str(self.root),
                         "tool_input": tool_input, "agent_id": "a1"}, **run)

    def shell(self, command: str, cwd: Path | None = None) -> str:
        return self.run({"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(cwd or self.root),
                         "tool_input": {"command": command}})


def context(output: str) -> str:
    """The reminder the hook added; fails on anything else it might have printed."""
    if not output:
        return ""
    try:
        specific = json.loads(output)["hookSpecificOutput"]
    except (ValueError, KeyError):
        fail(f"printed something that is not a PreToolUse output: {output}")
    if set(specific) != {"hookEventName", "additionalContext"}:
        fail(f"did more than add context - it must never decide on a tool call: {output}")
    return specific["additionalContext"]


def expect(condition: bool, message: str, output: str = "") -> None:
    if not condition:
        fail(f"{message}: {output!r}")


def check_settings() -> None:
    """The registration has to keep the guarantees the hook cannot give itself."""
    hooks = json.loads(SETTINGS.read_text(encoding="utf-8"))["hooks"]
    matchers = [entry.get("matcher", "") for entry in hooks.get("PreToolUse", [])
                if any("skill-check.py" in h["command"] for h in entry["hooks"])]
    expect(len(matchers) == 1, "settings.json does not register skill-check.py for PreToolUse once", matchers)
    expect(set(matchers[0].split("|")) == {"Edit", "MultiEdit", "Write", "NotebookEdit", "Bash"},
           "the PreToolUse matcher must be the file tools and Bash", matchers[0])
    others = [event for event, entries in hooks.items() if event != "PreToolUse"
              for entry in entries for h in entry["hooks"] if "skill-check.py" in h["command"]]
    expect(not others, "skill-check.py is registered for more than PreToolUse", others)
    commands = [h["command"] for event in hooks.values() for entry in event for h in entry["hooks"]]
    # uv exits 2 when it cannot provide an interpreter, before any Python runs - and 2
    # is the blocking exit code, so every tool call would be refused.
    for command in commands:
        expect(command.endswith("|| true"), "a hook command must end in '|| true'", command)


def check_edits(tmpdir: str) -> None:
    case = Case(tmpdir, "edits")
    manifest = "my-pkg/cpa-manifest.json"

    reminder = context(case.edit(manifest))
    expect("package-content" in reminder and ".claude/skills/package-content/SKILL.md" in reminder,
           f"did not remind of package-content on {manifest}", reminder)
    # the note arrives after the edit is made, so it must ask for a check of that change
    expect("check the change" in reminder, "the reminder does not ask to check the change it comes with", reminder)
    expect("package-content" in context(case.edit(manifest, tool="MultiEdit")), "said nothing on a MultiEdit")
    expect("vocabulary" in context(case.edit("my-pkg/data.ttl")),
           "did not remind of vocabulary on a .ttl whose text declares an owl:Ontology")
    # The marketplace layout (#32) and the older build/ folder both reach build-projects.
    if (case.root / ".claude" / "skills" / "build-projects").is_dir():
        for export in ("my-pkg/projects/demo/config.xml", "my-pkg/build/demo/config.xml"):
            expect("build-projects" in context(case.edit(export)), f"did not remind of build-projects on {export}")
    if (case.root / ".claude" / "skills" / "shapes").is_dir():
        expect("shapes" in context(case.edit("my-pkg/graphs/demo-shapes.ttl")),
               "did not remind of shapes on a catalog under graphs/")
    expect(not case.edit("my-pkg/notes.txt"), "spoke on a file nothing maps")
    expect(not case.edit("/somewhere/else/my-pkg/cpa-manifest.json"), "spoke on a file outside any package")

    # Content patterns are for RDF: prose, code and the extension point itself stay quiet.
    expect(not case.edit("docs/notes.md", text="sh:NodeShape for each owl:Class in shui:queryText"),
           "reminded on prose that mentions RDF terms")
    expect(not case.edit(".claude/skill-map.custom.json", text='{"content": ["sh:NodeShape"]}'),
           "reminded on a rule in skill-map.custom.json")
    expect(not case.edit("scripts/build/fetch.py"), "reminded on a script under scripts/build/ (exclude)")

    (case.root / ".claude" / "skill-map.custom.json").write_text('{"rules": [{"skill": "x",}]}', encoding="utf-8")
    reminder = context(case.edit(manifest))
    expect("package-content" in reminder and "skill-map.custom.json does not parse" in reminder,
           "a broken custom map switched the template's rules off, or went unnamed", reminder)
    (case.root / ".claude" / "no-skill-check").touch()
    expect(not case.edit(manifest), "spoke despite .claude/no-skill-check")


def check_shell(tmpdir: str) -> None:
    case = Case(tmpdir, "shell")
    reminder = context(case.shell("sed -i '' 's/a/b/' my-pkg/cpa-manifest.json"))
    expect("package-content" in reminder, "did not remind on a command naming a mapped file", reminder)
    expect("vocabulary" in context(case.shell(f"cat > {case.root}/my-pkg/demo-vocab.ttl <<'EOF'\nx\nEOF")),
           "did not remind on a heredoc into a mapped file")
    expect("package-content" in context(case.shell("cp /elsewhere/x my-pkg/cpa-manifest.json")),
           "did not remind on a cp into a mapped file")
    expect(not case.shell("cd /elsewhere && cp x my-pkg/cpa-manifest.json"),
           "reminded on a path that, after the cd, lies outside the package")
    expect("vocabulary" in context(case.shell("cd my-pkg && rm demo-vocab.ttl")),
           "did not follow a cd to the mapped file it names")
    expect(not case.shell("git status && task check:offline"), "spoke on a command naming no mapped file")
    expect(not case.shell("grep -rn 'owl:Class' bin/"), "spoke on a grep through code")


def check_rendered() -> None:
    """The rendered case itself, with the answers copier wrote - not a synthetic answers file.

    A case rendered from a local checkout records its source as ".", so the answers do
    not name the template; the skill map is what marks the package.
    """
    root = Path(".").resolve()
    manifest = sorted(root.glob("*/cpa-manifest.json"))[0]
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Edit", "cwd": str(root),
               "tool_input": {"file_path": str(manifest), "old_string": "a", "new_string": "b"}}
    result = subprocess.run([str(HOOK)], input=json.dumps(payload), capture_output=True, text=True,
                            check=False, env=dict(os.environ, CLAUDE_PROJECT_DIR=str(root)))
    expect("package-content" in context(result.stdout.strip()),
           "the rendered package got no reminder - the hook does not recognise it as a package", result.stdout)


def check_mirror(tmpdir: str) -> None:
    """A package rendered from a checkout or a mirror: the skill map marks it, answers alone do not."""
    local = Case(tmpdir, "from-checkout", answers="_commit: v1.0.0\n_src_path: .\npackage_type: project\n")
    expect("package-content" in context(local.edit("my-pkg/cpa-manifest.json")),
           "a package rendered from a local checkout got no reminder")


def check_user_level(tmpdir: str) -> None:
    """A user-level copy: the map beside it for old packages, quiet where the package's own hook runs."""
    home = Path(tmpdir) / "home" / ".claude" / "hooks"
    home.mkdir(parents=True)
    linked = home / "skill_reminder.py"
    linked.symlink_to(HOOK)
    (home / "skill-map.json").write_text(json.dumps({"rules": [
        {"skill": "package-content", "paths": ["*/cpa-manifest.json"]},
        {"skill": "my-own-skill", "paths": ["setup/*.json"]}]}), encoding="utf-8")
    elsewhere = Path(tmpdir) / "hub"
    elsewhere.mkdir()

    old = Case(tmpdir, "old-package", with_map=False)
    reminder = context(old.edit("my-pkg/cpa-manifest.json", hook=linked, project=elsewhere))
    expect("package-content" in reminder, "the user-level copy found no map for a package without one", reminder)
    expect("my-own-skill" in context(old.edit("setup/view.json", hook=linked, project=elsewhere)),
           "the user-level map's own skills were dropped")
    expect(not old.edit("my-pkg/cpa-manifest.json"), "the package's own copy read a map from outside the package")
    # Through the user-level copy, whose map would supply rules: a copier project of another template is no
    # package. Through a package's own hook it would be quiet for want of rules - right for the wrong reason.
    other = Case(tmpdir, "other-copier-project", with_map=False,
                 answers="_commit: v2.0.0\n_src_path: gh:someone/another-template\n")
    expect(not other.edit("my-pkg/cpa-manifest.json", hook=linked, project=elsewhere),
           "the user-level copy spoke in a copier project of another template")

    new = Case(tmpdir, "new-package")
    (new.root / ".claude" / "hooks").mkdir()
    shutil.copy(HOOK, new.root / ".claude" / "hooks" / "skill-check.py")
    expect(not new.edit("my-pkg/cpa-manifest.json", hook=linked),
           "the user-level copy spoke where the package's own hook runs as well")
    # A user-level link may point at a package's own copy; it is still the user-level one there.
    into_package = home / "into-package.py"
    into_package.symlink_to(new.root / ".claude" / "hooks" / "skill-check.py")
    expect(not new.edit("my-pkg/cpa-manifest.json", hook=into_package),
           "a user-level link pointing at the package's own hook spoke as well, so the session got the reminder twice")
    expect("package-content" in context(new.edit("my-pkg/cpa-manifest.json", hook=linked, project=elsewhere)),
           "the user-level copy stayed quiet in a session outside the package")


def main() -> None:
    if not HOOK.is_file():
        fail(f"{HOOK} is missing")
    if not os.access(HOOK, os.X_OK):
        fail(f"{HOOK} is not executable in the rendered package; settings.json runs it by path")
    check_settings()
    check_rendered()
    with tempfile.TemporaryDirectory() as raw:
        # Resolved, because macOS reaches its temp directory through the /var -> /private/var link, and a
        # hook that resolved its own link would then stand down by accident and pass the stand-down test.
        tmpdir = os.path.realpath(raw)
        check_edits(tmpdir)
        check_shell(tmpdir)
        check_mirror(tmpdir)
        check_user_level(tmpdir)
    print("check-skill-hook: ok (reminds on mapped files and commands naming them, quiet elsewhere, "
          "never decides on a tool call; the user-level copy reads its own map and stands down)")


if __name__ == "__main__":
    main()
