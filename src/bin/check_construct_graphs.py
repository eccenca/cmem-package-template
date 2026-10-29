#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Check that every SPARQL Construct task reading a Knowledge Graph dataset names its graph.

    check_construct_graphs.py <package-dir>

Unlike SPARQL Select, a SPARQL Construct task does not restrict its query to the graph of its input
dataset: `CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }` on a Knowledge Graph input reads the whole
store and copies every graph into its output (measured on Corporate Memory 26.2). Construct takes no
{{ }} templates either, so the query has to name its graph with FROM or GRAPH. On an in-memory input
the opposite holds: the dataset is a single default graph, and FROM or GRAPH there finds nothing.

For each Construct task (`sparqlCopyOperator`) in the exported build projects under
<package-dir>/projects/*/ (and build/*/), the workflows tell which datasets feed it - a dataset node
listing the task among its outputs, or the task's node listing the dataset among its inputs. A task
fed by a Knowledge Graph dataset (`eccencaDataPlatform`) whose query names no graph fails the check;
a task fed only by in-memory datasets whose query names one is reported too. Other inputs (an RDF
file, a SPARQL endpoint) are not judged: only the two kinds above were measured. Exits 1 on a failure.
"""
import re
import sys
from pathlib import Path

PARAM_QUERY = re.compile(r'<Param name="query"[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</Param>', re.S)
NAMES_GRAPH = re.compile(r"\b(FROM|GRAPH)\b", re.I)
NODE = re.compile(r'<(Operator|Dataset)\b([^>]*)>')
ATTR = re.compile(r'(\w+)="([^"]*)"')


def strip_comments(query: str) -> str:
    return "\n".join(line.split("#", 1)[0] for line in query.splitlines())


def project_dirs(package: Path) -> list[Path]:
    return [p for top in ("projects", "build") for p in sorted((package / top).glob("*/"))
            if (p / "config.xml").exists()]


def dataset_types(folder: Path) -> dict[str, str]:
    types = {}
    for path in (folder / "dataset").glob("*.xml"):
        found = re.search(r'<Dataset\b[^>]*\btype="([^"]+)"', path.read_text())
        types[path.stem] = found.group(1) if found else "?"
    return types


def feeders(folder: Path) -> dict[str, set[str]]:
    """Construct task id -> dataset task ids that feed it, over every workflow of the project."""
    fed: dict[str, set[str]] = {}
    for path in (folder / "workflow").glob("*.xml"):
        nodes = [(kind, dict(ATTR.findall(attrs))) for kind, attrs in NODE.findall(path.read_text())]
        task_of = {a.get("id"): a.get("task") for _, a in nodes}
        for kind, a in nodes:
            if kind == "Dataset":
                for out in filter(None, re.split(r"[,\s]+", a.get("outputs", ""))):
                    fed.setdefault(task_of.get(out, out), set()).add(a.get("task"))
            else:
                for src in filter(None, re.split(r"[,\s]+", a.get("inputs", ""))):
                    fed.setdefault(a.get("task"), set()).add(task_of.get(src, src))
    return fed


def check(package: Path) -> int:
    failures, notes, count = [], [], 0
    for folder in project_dirs(package):
        types, fed = dataset_types(folder), feeders(folder)
        for path in sorted((folder / "custom").glob("*.xml")):
            text = path.read_text()
            if 'type="sparqlCopyOperator"' not in text:
                continue
            count += 1
            query = PARAM_QUERY.search(text)
            names = bool(query and NAMES_GRAPH.search(strip_comments(query.group(1))))
            inputs = {d for d in fed.get(path.stem, set()) if d in types}
            graph_inputs = sorted(d for d in inputs if types[d] == "eccencaDataPlatform")
            where = f"{folder.name}/{path.stem}"
            if graph_inputs and not names:
                failures.append(f"{where}: reads {', '.join(graph_inputs)} (Knowledge Graph) but names no "
                                f"graph - a Construct reads the whole store; add FROM or GRAPH <graph>")
            elif inputs and all(types[d] == "inMemory" for d in inputs) and names:
                notes.append(f"{where}: names a graph, but its input is in-memory - FROM or GRAPH finds "
                             f"nothing there")
    for line in notes:
        print(f"WARN {line}")
    if failures:
        print(f"FAIL: {len(failures)} Construct task(s) read a Knowledge Graph without naming its graph")
        for line in failures:
            print(f"  !! {line}")
        return 1
    print(f"OK: {count} Construct task(s), none reads a Knowledge Graph without naming its graph")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(check(Path(sys.argv[1])))
