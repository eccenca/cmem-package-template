#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Keep the tags of a package's build projects in one register, task-tags.json.

  task_tags.py [--write | --check | --from-exports] <package-dir> [<register>]

The register (default: task-tags.json in the working directory, the repository root - the package
directory may hold only files the manifest declares) lists the tags of every dataset, transform,
linking task, custom task and workflow per project, the project's own tags, and the names of the
external systems the package talks to:

  {"project-tags": {"<project>": ["<package tag>", "operational", "from-repository"]},
   "systems": ["<system>"],
   "projects": {"<project>": {"<task id>": ["source", "production-data"]}}}

Optional, each with a one-line use case per entry:

  "roles":  {"training": "data for training people"}   roles next to bootstrap and operational;
            demo is always one. Each is a project role, a lifecycle tag and, as <role>-data, a data kind.
  "topics": {"localization": "everything about translations"}   the subject axis of datasets
  "graph-roles": {"<project>/<dataset>": "entity"}   the kind of graph a placeholder dataset stands for

--write sets the <Tags> of every task in the exports under <package-dir>/projects/*/ (and build/*/) to
what the register lists for it (none when not listed), the project's <Tags> in config.xml to its
project tags, and each project's tags.xml to the tags it uses. A task created through the API often
loses its tags on export, so run it after every export.
--check writes nothing and exits 1 when an export differs from the register. Tags are a set: an
export that only reorders them does not differ.
--from-exports writes a first register from the tags the exports carry today, for a package that
starts using one. Review it: --check then reports every tag that breaks the axes.

Every mode but --from-exports first checks the register against the tag axes of the build-projects
skill and stops when it fails: every tag on an axis, at most one tag per axis (except position and
writes-), every persistent dataset with a position (source, target or both) and a temporary one
without, a subject only on a dataset, no read-only tag (DataIntegration's readOnly flag says it), a
graph role that names a writes- role, and a project with exactly one role and from-repository.
"""
import json
import re
import sys
from pathlib import Path

TAG = "urn:silkframework:tag:"
TAGS = re.compile(r"(<MetaData>.*?)<Tags>.*?</Tags>", re.S)
TAG_URI = re.compile(r"<Tag>" + re.escape(TAG) + r"([^<]+)</Tag>")

GRAPH_ROLES = ("term", "entity", "rule", "inference", "categorization", "relation", "integration",
               "settings", "views", "shapes")
SEVERAL = {"position", "writes", "system"}
KINDS = ("dataset", "custom", "workflow")
DEFAULT_ROLES = {"demo": "example data for showing the package; never runs in production"}


def axes(spec: dict) -> dict[str, set[str]]:
    """The tag axes, with the roles and topics the register declares."""
    roles = set(DEFAULT_ROLES) | set(spec.get("roles", {}))
    return {
        "position": {"source", "target"},
        "writes": {f"writes-{r}" for r in GRAPH_ROLES},
        "warning": {"reads-imports"},
        "lifetime": {"temporary", "rebuilt", "clean-up"},
        "data kind": {"master-data", "production-data"} | {f"{r}-data" for r in roles},
        "subject": set(spec.get("topics", {})),
        "started by": {"by-person", "by-skill", "by-form", "by-schedule", "by-workflow", "by-api"},
        "lifecycle": {"bootstrap", "run-after-import", "migration"} | roles,
        "external": {"consume", "produce"},
        "bookkeeping": {"metadata", "generated", "shared-logic"},
        "entry": {"entry-point"},
        "system": set(spec.get("systems", [])),
    }


def project_roles(spec: dict) -> set[str]:
    return {"bootstrap", "operational"} | set(DEFAULT_ROLES) | set(spec.get("roles", {}))


KINDS = ("dataset", "custom", "workflow")
# a transform or linking task is a directory of its own; its tags sit in the first <MetaData> of this file
TASK_DIRS = {"transform": "rules.xml", "linking": "linkSpec.xml"}


def project_dirs(package: Path) -> dict[str, Path]:
    return {p.name: p for top in ("projects", "build") for p in sorted((package / top).glob("*/"))
            if (p / "config.xml").exists()}


def task_files(folder: Path) -> dict[str, Path]:
    files = {p.stem: p for kind in KINDS for p in sorted((folder / kind).glob("*.xml"))}
    for kind, name in TASK_DIRS.items():
        files.update({p.parent.name: p for p in sorted((folder / kind).glob(f"*/{name}"))})
    return files


def tags_in(text: str) -> list[str]:
    block = TAGS.search(text)
    return TAG_URI.findall(block.group(0)) if block else []


def axis_errors(spec: dict, projects: dict[str, Path]) -> list[str]:
    axes_of = axes(spec)
    roles = project_roles(spec)
    errors = [f"{name}: \"{key}\" needs a one-line use case per entry"
              for key in ("roles", "topics") for name, case in spec.get(key, {}).items()
              if not str(case).strip()]
    for project, tags in spec.get("project-tags", {}).items():
        if len([t for t in tags if t in roles]) != 1:
            errors.append(f"{project}: the project needs exactly one role of {', '.join(sorted(roles))}")
        if "from-repository" not in tags:
            errors.append(f"{project}: the project lacks the tag from-repository")
    for key, role in spec.get("graph-roles", {}).items():
        if role not in GRAPH_ROLES:
            errors.append(f"{key}: graph role {role} is none of {', '.join(GRAPH_ROLES)}")
    for project, register in spec.get("projects", {}).items():
        folder = projects.get(project)
        datasets = {p.stem for p in (folder / "dataset").glob("*.xml")} if folder else set()
        for task in sorted(set(register) | datasets):
            tags = register.get(task, [])
            if "read-only" in tags:
                errors.append(f"{project}/{task}: read-only is no tag - set the dataset's readOnly flag")
                tags = [t for t in tags if t != "read-only"]
            on = [next((a for a, known in axes_of.items() if t in known), None) for t in tags]
            errors += [f"{project}/{task}: {t} is on no axis (a system name goes into \"systems\", a role "
                       f"into \"roles\", a topic into \"topics\")" for t, a in zip(tags, on) if a is None]
            errors += [f"{project}/{task}: two tags on the {a} axis"
                       for a in sorted(set(on) - SEVERAL - {None}) if on.count(a) > 1]
            if "subject" in on and task not in datasets:
                errors.append(f"{project}/{task}: a subject belongs on a dataset - a task's subject follows "
                              f"from its datasets")
            if task in datasets and "temporary" in tags and "position" in on:
                errors.append(f"{project}/{task}: a temporary dataset with source or target")
            if task in datasets and "temporary" not in tags and "position" not in on:
                errors.append(f"{project}/{task}: a persistent dataset without source or target")
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
    spec = {"project-tags": {}, "systems": [], "projects": {}}
    known = set().union(*axes({}).values()) | {"read-only"}
    for project, folder in projects.items():
        spec["project-tags"][project] = tags_in((folder / "config.xml").read_text())
        tasks = {task: tags_in(path.read_text()) for task, path in task_files(folder).items()}
        spec["projects"][project] = {task: tags for task, tags in tasks.items() if tags}
    unknown = {t for p in spec["projects"].values() for tags in p.values() for t in tags} - known
    spec["systems"] = sorted(unknown)
    register.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {register} from {len(projects)} project(s); every tag on no axis is listed under "
          f"\"systems\" - move what is no system name onto an axis")


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
    errors = axis_errors(spec, projects)
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
        files = task_files(folder)
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
