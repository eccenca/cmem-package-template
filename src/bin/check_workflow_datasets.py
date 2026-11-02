#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Check how the workflows of a package's build projects use their datasets.

    check_workflow_datasets.py <package-dir>

Reads the exported build projects under <package-dir>/projects/*/ (and build/*/) and reports:

FAIL  an Update whose output is a Knowledge Graph dataset with clearGraphBeforeExecution, while its
      query names graphs but never the one that dataset stands for. The Update clears that graph
      before it runs, whatever it writes (measured on Corporate Memory 26.2) - the graph is emptied
      by a task that only meant to use it as an anchor.
WARN  a clearing Knowledge Graph dataset that workflows sharing no parent write, or that a
      workflow with a replaceable input or output both writes and reads - a staging graph, or a
      persistent graph rebuilt and read back in place. Such runs overlap: the run that starts last
      wipes what the others staged, or the graph ends as a mix of two runs. Stage each run apart (a
      workflow-scoped in-memory dataset, or a graph per run) and write the graph once at the end.
WARN  a dataset that is in no workflow and named by no other file of its project. It ships with
      the package and shows as a graph nobody fills; a dataset used only from outside (a form,
      cmemc) says so in its description.

A graph is "named" by its IRI, by the same {{ project.<variable> }} template the dataset's graph
parameter uses, by {{ output.config.graph }}, or by {{ input.config.graph }} when the input stands
for the same graph; the graph parameter may be a template (<Template name="graph">). A query without
GRAPH or WITH, or with a variable graph (GRAPH ?g), is not judged. Exits 1 on a failure.
"""
import re
import sys
from pathlib import Path

PARAM = re.compile(r'<(?:Param|Template) name="([^"]+)"[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</(?:Param|Template)>', re.S)
NODE = re.compile(r'<(Operator|Dataset|Workflow)\b([^>]*)>')
ATTR = re.compile(r'(\w+)="([^"]*)"')
NAMES_GRAPH = re.compile(r"\b(GRAPH|WITH)\b", re.I)
VARIABLE_GRAPH = re.compile(r"\b(GRAPH|WITH)\s+[?$]", re.I)


def project_dirs(package: Path) -> list[Path]:
    return [p for top in ("projects", "build") for p in sorted((package / top).glob("*/"))
            if (p / "config.xml").exists()]


def params(text: str) -> dict[str, str]:
    return {name: value for name, value in PARAM.findall(text)}


def squash(value: str) -> str:
    """{{ project.x }} and {{project.x}} are the same template."""
    return re.sub(r"\s+", "", value)


def strip_comments(query: str) -> str:
    return "\n".join(line.split("#", 1)[0] if not line.lstrip().startswith("prefix") else line
                     for line in query.splitlines())


def split(value: str) -> list[str]:
    return [v for v in re.split(r"[,\s]+", value) if v]


def load(folder: Path):
    datasets, tasks, workflows = {}, {}, {}
    for path in (folder / "dataset").glob("*.xml"):
        text = path.read_text()
        kind = re.search(r'<Dataset\b[^>]*\btype="([^"]+)"', text)
        datasets[path.stem] = {"type": kind.group(1) if kind else "?", "params": params(text)}
    for path in (folder / "custom").glob("*.xml"):
        text = path.read_text()
        kind = re.search(r'<CustomTask\b[^>]*\btype="([^"]+)"', text)
        tasks[path.stem] = {"type": kind.group(1) if kind else "?", "params": params(text)}
    for path in (folder / "workflow").glob("*.xml"):
        nodes = [(kind, dict(ATTR.findall(attrs))) for kind, attrs in NODE.findall(path.read_text())]
        head = next((a for k, a in nodes if k == "Workflow"), {})
        task_of = {a.get("id"): a.get("task") for k, a in nodes if k != "Workflow"}
        writes, reads, operators, edges = set(), set(), set(), []
        for kind, a in nodes:
            if kind == "Dataset":
                for out in split(a.get("outputs", "")):
                    reads.add(a["task"])
                    edges.append((a["task"], task_of.get(out, out)))
            elif kind == "Operator":
                operators.add(a.get("task"))
                for src in split(a.get("inputs", "")):
                    edges.append((task_of.get(src, src), a.get("task")))
                for out in split(a.get("outputs", "")):
                    edges.append((a.get("task"), task_of.get(out, out)))
        for kind, a in nodes:
            if kind == "Dataset":
                if split(a.get("inputs", "")) or any(dst == a["task"] for _, dst in edges):
                    writes.add(a["task"])
        workflows[path.stem] = {
            "writes": writes, "reads": reads, "operators": operators, "edges": edges,
            "payload": bool(split(head.get("replaceableInputs", "")) or split(head.get("replaceableOutputs", ""))),
        }
    return datasets, tasks, workflows


def graph_of(dataset: dict) -> str:
    return squash(dataset["params"].get("graph", ""))


def clears(dataset: dict) -> bool:
    return dataset["type"] == "eccencaDataPlatform" and dataset["params"].get("clearGraphBeforeExecution") == "true"


def names(query: str, graph: str, input_graphs: set[str]) -> bool:
    q = squash(strip_comments(query))
    if graph and graph in q:
        return True
    if "{{output.config.graph}}" in q:
        return True
    return "{{input.config.graph}}" in q and bool(graph) and graph in input_graphs


def roots(workflows: dict) -> dict[str, set[str]]:
    """Each workflow -> the top-level workflows it runs under (itself when nothing nests it)."""
    parents = {w: {p for p, info in workflows.items() if w in info["operators"]} for w in workflows}

    def up(w, seen):
        if not parents[w] or w in seen:
            return {w}
        return set().union(*(up(p, seen | {w}) for p in parents[w]))

    return {w: up(w, set()) for w in workflows}


def check(package: Path) -> int:
    failures, warnings = [], []
    for folder in project_dirs(package):
        datasets, tasks, workflows = load(folder)
        where = folder.name
        for wf, info in workflows.items():
            for src, dst in info["edges"]:
                task = tasks.get(src)
                if not task or task["type"] != "sparqlUpdateOperator" or dst not in datasets:
                    continue
                out = datasets[dst]
                query = task["params"].get("sparqlUpdateTemplate", "")
                plain = strip_comments(query)
                if not clears(out) or not NAMES_GRAPH.search(plain) or VARIABLE_GRAPH.search(plain):
                    continue
                inputs = {graph_of(datasets[s]) for s, d in info["edges"] if d == src and s in datasets}
                if not names(query, graph_of(out), inputs):
                    failures.append(f"{where}/{wf}: {src} writes into {dst}, which clears its graph "
                                    f"({graph_of(out) or '?'}) before the update, but the query never "
                                    f"names that graph - give the update a dataset of a graph it writes")
        top = roots(workflows)
        for ds, dataset in datasets.items():
            if not clears(dataset):
                continue
            writers = [w for w, info in workflows.items() if ds in info["writes"]]
            if len(writers) > 1 and not set.intersection(*(top[w] for w in writers)):
                warnings.append(f"{where}/{ds}: clears its graph and is written by {', '.join(sorted(writers))}, "
                                f"which share no parent - their runs overlap, the last to start wins")
            for w in writers:
                if workflows[w]["payload"] and ds in workflows[w]["reads"]:
                    warnings.append(f"{where}/{ds}: written and read back in {w}, which has a replaceable input "
                                    f"or output - its runs overlap and can leave a mix of two runs in the graph; "
                                    f"stage each run apart (in-memory, or a graph per run) and write the graph once")
        others = [p for p in folder.rglob("*.xml") if p.parent.name != "dataset"]
        texts = "\n".join(p.read_text() for p in others)
        for ds in datasets:
            if not re.search(rf'(?<![\w-]){re.escape(ds)}(?![\w-])', texts):
                warnings.append(f"{where}/{ds}: in no workflow and named by no task - ships as a graph "
                                f"nobody fills; remove it, or say in its description who uses it")
    for line in warnings:
        print(f"WARN {line}")
    if failures:
        print(f"FAIL: {len(failures)} update(s) clear a graph they do not write")
        for line in failures:
            print(f"  !! {line}")
        return 1
    print(f"OK: no update clears a graph it does not write ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(check(Path(sys.argv[1])))
