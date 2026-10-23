#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Lay out the workflows of an exported DataIntegration project as a waterfall.

  layout_workflows.py [--write | --check] <project-dir>

x is the order: a node's column is the longest path to it over data, config and dependency edges, so
every edge points right. A source moves right to the column before its first consumer, except a
replaceable input, which stays in column 0; a replaceable output goes to the last column.
y is the tier, then the graph: configuration (branches that only feed a config port) above input
(what the run reads from outside itself; a read of a persistent graph the run also writes sits in that
graph's lane) above working
(in-memory, file, REST responses, graphs cleared per run) above one swimlane per persistent graph
written, ordered by first write, above the result lane (replaceable outputs). An operator sits in the
lane of what it writes. Within a lane, rows are permuted to minimise edge crossings; a crossing that
survives is one the rules cannot avoid. --check reports avoidable differences and exits 1.
"""
import itertools, re, sys
from pathlib import Path

COL, ROW, TOP = 300, 200, 100
NODE = re.compile(r'<(Operator|Dataset) posX="(-?\d+)" posY="(-?\d+)" task="([^"]*)" ([^>]*?)id="([^"]+)"([^>]*)/>')

def attr(text, name):
    m = re.search(name + r'="([^"]*)"', text)
    return [i for i in m.group(1).split(",") if i] if m else []

def manifest_graphs(project):
    for d in [project, *project.parents]:
        m = d / "cpa-manifest.json"
        if m.exists():
            return set(re.findall(r'"graph_iri"\s*:\s*"([^"]+)"', m.read_text()))
    return set()

def project_variables(project):
    f = project / "variables.xml"
    if not f.exists():
        return {}
    x = f.read_text()
    return {m.group(1): m.group(2) for m in re.finditer(
        r'<Variable name="([^"]+)"[^>]*>\s*<Value xml:space="preserve"><!\[CDATA\[([^\]]*)\]\]>', x)}

def resolve(text, project):
    """Replace {{project.x}} / {{ project.x }} with the variable's value, as the server does."""
    values = project_variables(project)
    return re.sub(r"\{\{\s*project\.(\w+)\s*\}\}", lambda m: values.get(m.group(1), m.group(0)), text)

def dataset_info(project, task):
    f = project / "dataset" / f"{task}.xml"
    if not f.exists():
        return "unknown", task
    x = f.read_text()
    kind = re.search(r'<Dataset [^>]*type="([^"]+)"', x).group(1)
    clear = re.search(r'name="clearGraphBeforeExecution"[^>]*><!\[CDATA\[true', x) is not None
    graph = re.search(r'name="graph"[^>]*><!\[CDATA\[([^\]]*)\]\]', x)
    g = resolve(graph.group(1), project) if graph else task
    if g in manifest_graphs(project):
        return "persistent", g      # shipped by the package: a target, even if cleared per run
    return ("working" if kind == "inMemory" or clear or kind in ("json", "csv", "xml", "file", "text", "excel", "multiCsv")
            else "persistent"), g

def crossings(pos, edges):
    def ccw(a, b, c):
        return (c[1] - a[1]) * (b[0] - a[0]) - (b[1] - a[1]) * (c[0] - a[0])
    n = 0
    segs = [(pos[a], pos[b], a, b) for a, b in edges]
    for (p1, p2, a1, b1), (q1, q2, a2, b2) in itertools.combinations(segs, 2):
        if {a1, b1} & {a2, b2}:
            continue
        d1, d2, d3, d4 = ccw(q1, q2, p1), ccw(q1, q2, p2), ccw(p1, p2, q1), ccw(p1, p2, q2)
        if d1 * d2 < 0 and d3 * d4 < 0:
            n += 1
    return n

def child_lane(path, project):
    """The lane of a nested workflow: the persistent graph it writes, else working."""
    text = path.read_text()
    written = [m.group(4) for m in NODE.finditer(text) if m.group(1) == "Dataset" and attr(m.group(5) + m.group(7), "inputs")]
    graphs = [g for tier, g in (dataset_info(project, t) for t in written) if tier == "persistent"]
    return (2, graphs[0]) if graphs else (1, "working")

NOTE_GAP = 50
NOTE_BOX = re.compile(r'<StickyNote [^>]*>.*?<Position x="(-?[\d.]+)" y="(-?[\d.]+)"/>\s*<Dimension width="([\d.]+)" height="([\d.]+)"', re.S)
NOTE = re.compile(r'(<StickyNote [^>]*>.*?<Position x=")(-?[\d.]+)(" y=")(-?[\d.]+)("/>\s*<Dimension width="[\d.]+" height=")([\d.]+)(")', re.S)

def layout(path, project):
    text = path.read_text()
    head = re.search(r'<Workflow [^>]*>', text).group(0)
    rep_in, rep_out = set(attr(head, "replaceableInputs")), set(attr(head, "replaceableOutputs"))
    nodes, old, attr_of, flow_of, ports_of = {}, {}, {}, {}, {}
    for m in NODE.finditer(text):
        rest = m.group(5) + m.group(7)
        attr_of[m.group(6)] = attr(rest, "configInputs")
        flow_of[m.group(6)] = attr(rest, "inputs") + attr(rest, "configInputs")
        ports_of[m.group(6)] = attr(rest, "inputs")
        nodes[m.group(6)] = {"kind": m.group(1), "task": m.group(4),
                             "preds": attr(rest, "inputs") + attr(rest, "configInputs") + attr(rest, "dependencyInputs")}
        old[m.group(6)] = (int(m.group(2)), int(m.group(3)))
    edges = [(p, n) for n in nodes for p in nodes[n]["preds"] if p in nodes]
    cfg_edges = {(p, n) for n in nodes for p in attr_of[n] if p in nodes}
    succ = {n: [b for a, b in edges if a == n] for n in nodes}
    # x: longest path
    col = {}
    def depth(n, seen=()):
        if n not in col:
            ps = [p for p in nodes[n]["preds"] if p in nodes and p not in seen]
            col[n] = 0 if not ps else 1 + max(depth(p, seen + (n,)) for p in ps)
        return col[n]
    for n in nodes: depth(n)
    for n in nodes:
        if not nodes[n]["preds"] and succ[n] and nodes[n]["task"] not in rep_in:
            col[n] = min(col[s] for s in succ[n]) - 1
    last = max(col.values())
    for n in nodes:
        if nodes[n]["task"] in rep_out:
            col[n] = last
    # y: lanes. The configuration tier holds every node whose paths into the rest of the workflow all
    # pass through a config edge: it reconfigures a step rather than carrying the flow, so it sits on top.
    config = set()
    changed = True
    while changed:
        changed = False
        for n in nodes:
            if n in config or not succ[n]:
                continue
            if all((n, s) in cfg_edges or s in config for s in succ[n]):
                config.add(n); changed = True
    lane = {n: (-1, "configuration") for n in config}
    # the datasets this workflow writes: a read of one of them later in the run is no outside input
    written_tasks = {nodes[m]["task"] for m in nodes if nodes[m]["kind"] == "Dataset" and flow_of[m]}
    for n in nodes:
        if nodes[n]["kind"] != "Dataset" or n in lane:
            continue
        if nodes[n]["task"] in rep_out:
            lane[n] = (3, "result")
        elif not flow_of[n] and nodes[n]["task"] in written_tasks and dataset_info(project, nodes[n]["task"])[0] == "persistent":
            # reads a persistent graph the run itself writes: it sits in that graph's lane, next to the
            # writes it follows, instead of the input row far above
            lane[n] = (2, dataset_info(project, nodes[n]["task"])[1])
        elif not flow_of[n]:
            lane[n] = (0, "input")    # nothing flows into it; a dependency only orders the read
        else:
            tier, graph = dataset_info(project, nodes[n]["task"])
            lane[n] = (1, "working") if tier == "working" else (2, graph)
    def op_lane(n, seen=()):
        if n in lane: return lane[n]
        child = project / "workflow" / f"{nodes[n]['task']}.xml"
        if child.exists():
            return child_lane(child, project)      # a nested workflow writes inside its child
        # only what an operator writes (data or config) places it; a dependency says "after", not "into"
        outs = [s for s in succ[n] if s not in seen and n in flow_of[s]]
        if not outs and not any(n in flow_of[s] or n in nodes[s]["preds"] for s in nodes if s != n):
            return (3, "result")    # a final step that writes nothing, such as a validation, is the run's verdict
        ls = [op_lane(s, seen + (n,)) for s in outs]
        return max(ls, key=lambda l: l[0]) if ls else (1, "working")
    for n in nodes:
        if n not in lane: lane[n] = op_lane(n)
    first = {}
    for n in nodes:
        first[lane[n]] = min(first.get(lane[n], 99), col[n])
    order = sorted(set(lane.values()), key=lambda l: (l[0], first[l], l[1]))
    # rows within a lane: a lane is as tall as its fullest column; every node may take any row of its
    # lane. Score: crossings first, then edges running upward (the waterfall only falls), then the
    # total vertical length of the edges.
    groups = {}
    for n in nodes:
        groups.setdefault((lane[n], col[n]), []).append(n)
    lane_rows = {l: max(len(g) for (gl, _), g in groups.items() if gl == l) for l in order}
    choices = []
    for (l, _), g in groups.items():
        opts = []
        for perm in itertools.permutations(g):
            for start in range(lane_rows[l] - len(g) + 1):
                opts.append({n: start + i for i, n in enumerate(perm)})
        choices.append(opts)
    total = 1
    for o in choices: total *= len(o)
    combos = itertools.product(*choices) if total <= 20000 else [tuple(o[0] for o in choices)]
    # Sticky notes stay with what they explain: each note is anchored to the node nearest to it on the
    # old canvas, and sits directly above that node's lane, which gets the room the note needs.
    notes = []
    for m in NOTE_BOX.finditer(text):
        x, y, w, h = (float(m.group(i)) for i in (1, 2, 3, 4))
        cx, cy = x + w / 2, y + h / 2
        # a note is drawn in the column of the step it explains, often above the whole canvas: the anchor
        # is that column's node nearest to it (an operator before a dataset), else the nearest node at all
        column = [n for n in old if abs(old[n][0] - x) < COL / 2]
        if column:
            anchor = min(column, key=lambda n: (nodes[n]["kind"] != "Operator", abs(old[n][1] - (y + h)), n))
        else:
            anchor = min(old, key=lambda n: ((old[n][0] - cx) ** 2 + (old[n][1] - cy) ** 2, n))
        notes.append((anchor, x - old[anchor][0], h))
    pad = {}
    for anchor, _, h in notes:
        pad[lane[anchor]] = max(pad.get(lane[anchor], 0), int(round(h)) + NOTE_GAP)
    offset, y = {}, 0
    for l in order:
        y += pad.get(l, 0); offset[l] = y; y += lane_rows[l] * ROW
    best = None
    for combo in combos:
        row = {n: r for part in combo for n, r in part.items()}
        pos = {n: (col[n] * COL, TOP + offset[lane[n]] + row[n] * ROW) for n in nodes}
        up = sum(1 for a, b in edges if pos[b][1] < pos[a][1])
        drop = sum(abs(pos[b][1] - pos[a][1]) for a, b in edges)
        # an input port order that runs against the rows crosses the edges right at the target
        # (user, 2026-10-08: Clear dataset on port 1 drawn below the publish on port 2)
        inverted = sum(1 for n in nodes for i, a in enumerate(ports_of[n]) for b in ports_of[n][i + 1:]
                       if a in pos and b in pos and a != b and pos[a][1] > pos[b][1])
        score = (crossings(pos, edges) + inverted, up, drop)
        if best is None or score < best[0]:
            best = (score, pos)
    (c, _, _), pos = best
    placed = iter(notes)
    def move_note(m):
        anchor, dx, h = next(placed)
        lane_top = TOP + offset[lane[anchor]]
        return f"{m.group(1)}{int(pos[anchor][0] + dx)}{m.group(3)}{int(lane_top - NOTE_GAP - h)}{m.group(5)}{m.group(6)}{m.group(7)}"
    text = NOTE.sub(move_note, text)
    new = NODE.sub(lambda m: f'<{m.group(1)} posX="{pos[m.group(6)][0]}" posY="{pos[m.group(6)][1]}" task="{m.group(4)}" {m.group(5)}id="{m.group(6)}"{m.group(7)}/>', text)
    return new, pos, old, c, order, lane, col

def main():
    mode = sys.argv[1] if sys.argv[1] in ("--write", "--check") else None
    project = Path(sys.argv[-1])
    changed = 0
    for wf in sorted((project / "workflow").glob("*.xml")):
        new, pos, old, c, order, lane, col = layout(wf, project)
        print(f"== {wf.stem}  ({c} unavoidable crossing{'s' if c != 1 else ''})")
        for l in order:
            members = sorted((n for n in pos if lane[n] == l), key=lambda n: pos[n])
            print(f"   {l[1]:52} " + "  ".join(f"{col[n]}:{n}" for n in members))
        if pos != old:
            changed += 1
            if mode == "--write":
                wf.write_text(new)
    if mode == "--check" and changed:
        print(f"{changed} workflow(s) differ from the layout"); sys.exit(1)

main()
