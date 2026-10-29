#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Keep the tags of a package's build projects in one register, task-tags.json.

  task_tags.py [--write | --check | --from-exports] <package-dir> [<register>]

The register (default: task-tags.json in the working directory, the repository root - the package
directory may hold only files the manifest declares) declares the package's tag axes and lists the
tags of every dataset, transform, linking task, custom task and workflow per project, and the
project's own tags:

  {"include": ["<preset>.json"],
   "axes": {"<axis>": {"use": "<who searches by it, for what>",
                       "on": ["dataset", "custom", "workflow", "transform", "linking", "project"],
                       "several": false,
                       "values": {"<tag>": "<one-line use case>"}}},
   "project-tags": {"<project>": ["<tag>"]},
   "projects": {"<project>": {"<task id>": ["<tag>"]}}}

The template declares no axis: which tags a package uses, and what they mean, is the package's (or
its organisation's) convention. "include" merges the axes of preset files, relative to the register,
so several packages share one convention; an axis the register declares again adds its values to the
preset's.

--write sets the <Tags> of every task in the exports under <package-dir>/projects/*/ (and build/*/) to
what the register lists for it (none when not listed), the project's <Tags> in config.xml to its
project tags, and each project's tags.xml to the tags it uses. A task created through the API often
loses its tags on export, so run it after every export.
--check writes nothing and exits 1 when an export differs from the register. Tags are a set: an
export that only reorders them does not differ.
--from-exports writes a first register from the tags the exports carry today, all on one axis to
sort; --check then reports every tag without its use case.

Every mode but --from-exports first checks the register against its axes and stops when it fails:
every axis and every value has a use case, every tag is a value of an axis declared for that kind of
task (or for projects), and at most one tag per axis unless the axis allows several.
"""
import json
import re
import sys
from pathlib import Path

TAG = "urn:silkframework:tag:"
TAGS = re.compile(r"(<MetaData>.*?)<Tags>.*?</Tags>", re.S)
TAG_URI = re.compile(r"<Tag>" + re.escape(TAG) + r"([^<]+)</Tag>")

KINDS = ("dataset", "custom", "workflow")
# a transform or linking task is a directory of its own; its tags sit in the first <MetaData> of this file
TASK_DIRS = {"transform": "rules.xml", "linking": "linkSpec.xml"}
ON = set(KINDS) | set(TASK_DIRS) | {"project"}


def axes(spec: dict, base: Path = Path(".")) -> dict[str, dict]:
    """The axes of the register's includes, then its own. An axis declared again adds its values to the
    earlier one and replaces what else it says, so a package extends a preset's axis."""
    merged: dict[str, dict] = {}
    sources = [axes(json.loads((base / i).read_text()), (base / i).parent) for i in spec.get("include", [])]
    for source in sources + [spec.get("axes", {})]:
        for name, decl in source.items():
            earlier = merged.get(name, {})
            merged[name] = {**earlier, **decl,
                            "values": {**earlier.get("values", {}), **decl.get("values", {})}}
    return merged


def project_dirs(package: Path) -> dict[str, Path]:
    return {p.name: p for top in ("projects", "build") for p in sorted((package / top).glob("*/"))
            if (p / "config.xml").exists()}


def task_files(folder: Path) -> dict[str, tuple[str, Path]]:
    """Task id -> (kind, the file holding its tags)."""
    files = {p.stem: (kind, p) for kind in KINDS for p in sorted((folder / kind).glob("*.xml"))}
    for kind, name in TASK_DIRS.items():
        files.update({p.parent.name: (kind, p) for p in sorted((folder / kind).glob(f"*/{name}"))})
    return files


def tags_in(text: str) -> list[str]:
    block = TAGS.search(text)
    return TAG_URI.findall(block.group(0)) if block else []


def declaration_errors(axes_of: dict[str, dict]) -> list[str]:
    errors = []
    for axis, decl in axes_of.items():
        if not str(decl.get("use", "")).strip():
            errors.append(f"axis {axis}: needs \"use\" - who searches by it, for what")
        unknown = set(decl.get("on", [])) - ON
        if not decl.get("on") or unknown:
            errors.append(f"axis {axis}: \"on\" lists what it tags, out of {', '.join(sorted(ON))}")
        errors += [f"axis {axis}: {tag} needs a one-line use case"
                   for tag, case in decl.get("values", {}).items() if not str(case).strip()]
    return errors


def tag_errors(where: str, kind: str, tags: list[str], axes_of: dict[str, dict]) -> list[str]:
    errors, on = [], []
    for tag in tags:
        holding = [a for a, d in axes_of.items() if tag in d.get("values", {})]
        fitting = [a for a in holding if kind in axes_of[a].get("on", [])]
        if not holding:
            errors.append(f"{where}: {tag} is declared on no axis")
        elif not fitting:
            errors.append(f"{where}: {tag} is on the {', '.join(holding)} axis, which tags no {kind}")
        # a value may sit on several axes - one for tasks, one for projects; the one tagging this kind counts
        on.append(fitting[0] if fitting else None)
    errors += [f"{where}: two tags on the {a} axis" for a in sorted(set(on) - {None})
               if on.count(a) > 1 and not axes_of[a].get("several")]
    return errors


def axis_errors(spec: dict, projects: dict[str, Path], base: Path = Path(".")) -> list[str]:
    axes_of = axes(spec, base)
    errors = declaration_errors(axes_of)
    for project, tags in spec.get("project-tags", {}).items():
        errors += tag_errors(project, "project", tags, axes_of)
    for project, register in spec.get("projects", {}).items():
        files = task_files(projects[project]) if project in projects else {}
        for task, tags in register.items():
            kind = files[task][0] if task in files else None
            if kind:
                errors += tag_errors(f"{project}/{task}", kind, tags, axes_of)
    return errors


def tags_block(tags: list[str]) -> str:
    if not tags:
        return "<Tags> </Tags>"
    return "<Tags>\n" + "".join(f"      <Tag>{TAG}{t}</Tag>\n" for t in tags) + "    </Tags>"


def tags_xml(tags: set[str]) -> str:
    return "<Tags>\n" + "".join(f'  <Tag uri="{TAG}{t}">\n    <Label>{t}</Label>\n  </Tag>\n'
                                for t in sorted(tags)) + "</Tags>"


def declared(path: Path) -> set[str]:
    return set(re.findall(r'uri="' + re.escape(TAG) + r'([^"]+)"', path.read_text())) if path.exists() else set()


def from_exports(projects: dict[str, Path], register: Path) -> None:
    spec = {"axes": {}, "project-tags": {}, "projects": {}}
    found = set()
    for project, folder in projects.items():
        spec["project-tags"][project] = tags_in((folder / "config.xml").read_text())
        tasks = {task: tags_in(path.read_text()) for task, (_, path) in task_files(folder).items()}
        spec["projects"][project] = {task: tags for task, tags in tasks.items() if tags}
        found |= {t for tags in tasks.values() for t in tags} | set(spec["project-tags"][project])
    spec["axes"]["unsorted"] = {"use": "", "on": sorted(ON), "several": True,
                                "values": {t: "" for t in sorted(found)}}
    register.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {register} from {len(projects)} project(s); every tag sits on the axis \"unsorted\" - "
          f"sort them onto axes of your own, or include a preset, and give each a use case")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mode = next((a for a in sys.argv[1:] if a.startswith("--")), "--write")
    if mode not in ("--write", "--check", "--from-exports") or not 1 <= len(args) <= 2:
        sys.exit(__doc__)
    package = Path(args[0])
    register = Path(args[1] if len(args) > 1 else "task-tags.json")
    projects = project_dirs(package)
    if mode == "--from-exports":
        if register.exists():
            sys.exit(f"{register} exists - remove it first to write a new one from the exports")
        from_exports(projects, register)
        return
    if not register.exists():
        print(f"no {register}: the tags are kept in the exports only - nothing to check")
        return
    spec = json.loads(register.read_text())
    errors = axis_errors(spec, projects, register.parent)
    for project in sorted(set(projects) - set(spec.get("projects", {}))):
        errors.append(f"{project}: a build project the register does not list")
    for project in sorted(set(spec.get("projects", {})) - set(projects)):
        errors.append(f"{project}: listed in {register}, but no export of it under {package}")
    for e in errors:
        print(e, file=sys.stderr)
    if errors:
        sys.exit(1)
    stale = []
    for project, folder in projects.items():
        register_tasks = spec["projects"][project]
        files = {task: path for task, (_, path) in task_files(folder).items()}
        for task in sorted(set(register_tasks) - set(files)):
            print(f"{project}: {register} names {task}, which the export does not have", file=sys.stderr)
            stale.append(f"{project}/{task}")
        targets = [(f"{project}/{task}", path, register_tasks.get(task, [])) for task, path in files.items()]
        targets.append((f"{project}/config.xml", folder / "config.xml", spec["project-tags"].get(project, [])))
        for name, path, tags in targets:
            text = path.read_text()
            if set(tags_in(text)) != set(tags) or (TAGS.search(text) is None and tags):
                stale.append(name)
                if mode == "--write":
                    path.write_text(TAGS.sub(lambda m: m.group(1) + tags_block(tags), text, count=1))
        used = {t for tags in register_tasks.values() for t in tags} | set(spec["project-tags"].get(project, []))
        if declared(folder / "tags.xml") != used:
            stale.append(f"{project}/tags.xml")
            if mode == "--write":
                (folder / "tags.xml").write_text(tags_xml(used))
    if stale:
        print(("out of date: " if mode == "--check" else "written: ") + ", ".join(stale), file=sys.stderr)
    if mode == "--check" and stale:
        sys.exit(1)


if __name__ == "__main__":
    main()
