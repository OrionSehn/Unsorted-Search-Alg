'''
BMSSPRecorder: records a run of bmssp as animation frames for the Manim
visualization in visualization/ (format described in visualization/schema.py).

unsorted_search.py calls the recorder at a few points of the algorithm
(entering/leaving a call, after FindPivots, after each Pull, after each round
of relaxations). The recorder only reads the algorithm's state, it never
changes it, so a recorded run gives exactly the same result as an unrecorded one.

Each frame holds:
  - graph_state: every node's state and cost, and the edges relaxed since the
    previous frame (highlighted)
  - block_state: the block structure D of the innermost call that has one
    (heap tree of blocks, the B block, and the prepend blocks D0)
  - call_stack:  the chain of BMSSP / BaseCase calls currently running
'''

import json
import math

import networkx as nx


# node states, matching visualization/schema.py
UNEXPLORED = "unexplored"   # no path found yet (cost inf)
OPEN = "open"               # has a cost, but it may still improve
CLOSED = "closed"           # complete: returned in some call's U, cost is final
ACTIVE = "active"           # in the set the current step is working on


def format_number(x):
    if x == float('inf'):
        return "∞"
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x)


def format_bound(bound):
    '''(B,) -> "B"; a key (cost, hops, node) -> "cost (node)" (the node breaks ties).'''
    if isinstance(bound, tuple):
        if len(bound) == 1:
            return format_number(bound[0])
        return f"{format_number(bound[0])} ({bound[2]})"
    return format_number(bound)


def format_nodes(nodes, limit=6):
    names = sorted(str(n) for n in nodes)
    if not names:
        return "nothing"
    if len(names) > limit:
        names = names[:limit] + [f"+{len(names) - limit}"]
    return "{" + ", ".join(names) + "}"


class BMSSPRecorder:
    def __init__(self, bmssp_ws):
        self.ws = bmssp_ws
        self.frames = []
        # one entry per running call: {'label', 'level', 'structure' (BlockHeap or None), 'structure_id'}
        self.call_stack = []
        self._next_structure_id = 0
        self.complete = set()          # nodes returned in some U
        self.active = set()
        self.relaxed_edges = []        # (u, v) relaxed since the last frame
        # items shown in the previous frame, per structure, to highlight new ones
        self._previous_items = {}
        self._graph_def = self._build_graph_def()

    # ------------------------------------------------------------------
    # Hooks called by the algorithm
    # ------------------------------------------------------------------

    def on_relax(self, u, v):
        self.relaxed_edges.append((u, v))

    def enter_call(self, level, bound_B, closed_S):
        if level == 0:
            label = f"BaseCase(B={format_bound(bound_B)})"
        else:
            label = f"BMSSP(l={level}, B={format_bound(bound_B)})"
        self.call_stack.append({'label': label, 'level': level, 'structure': None, 'structure_id': None})
        self.active = set(closed_S)
        # base cases get a single frame, when they finish
        if level > 0:
            self.frame(f"{label} on S = {format_nodes(closed_S)}")

    def attach_structure(self, block_data_struct_D):
        self.call_stack[-1]['structure'] = block_data_struct_D
        self.call_stack[-1]['structure_id'] = self._next_structure_id
        self._next_structure_id += 1

    def exit_call(self, level, start_nodes, bound_B_prime, resolved_U):
        self.complete |= set(resolved_U)
        self.active = set(resolved_U)
        if level == 0:
            description = (f"BaseCase from {format_nodes(start_nodes)}: "
                           f"U = {format_nodes(resolved_U)}, B' = {format_bound(bound_B_prime)}")
        else:
            description = (f"return from level {level}: "
                           f"B' = {format_bound(bound_B_prime)}, |U| = {len(resolved_U)}")
        self.frame(description)
        self.call_stack.pop()
        self.active = set()

    # ------------------------------------------------------------------
    # Frames
    # ------------------------------------------------------------------

    def frame(self, description, active=None):
        if active is not None:
            self.active = set(active)
        self.frames.append({
            'description': description,
            'call_stack': [entry['label'] for entry in self.call_stack],
            'graph_state': self._graph_state(),
            'block_state': self._block_state(),
        })
        self.relaxed_edges = []

    def _graph_state(self):
        nodes = []
        for node in self.ws.graph.nodes:
            cost = self.ws.g_cost[node]
            if node in self.active:
                state = ACTIVE
            elif node in self.complete:
                state = CLOSED
            elif cost != float('inf'):
                state = OPEN
            else:
                state = UNEXPLORED
            nodes.append({
                'id': str(node),
                'state': state,
                'label_extra': f"d={format_number(cost)}" if cost != float('inf') else "",
            })
        highlighted = set()
        for u, v in self.relaxed_edges:
            key = self._edge_key(u, v)
            if key is not None:
                highlighted.add(key)
        edges = [{'source': s, 'target': t, 'highlight': True} for s, t in sorted(highlighted)]
        return {'nodes': nodes, 'edges': edges}

    def _block_state(self):
        # the structure of the innermost call that has one
        entry = next((e for e in reversed(self.call_stack) if e['structure'] is not None), None)
        if entry is None:
            return None
        structure = entry['structure']
        snap = structure.snapshot()

        structure_id = entry['structure_id']
        # None the first time this structure is shown: then nothing counts as "new"
        previous = self._previous_items.get(structure_id)
        current = set()

        def items_json(items):
            out = []
            for key in sorted(items):
                cost, hops, node = key
                item_id = f"{node}@{format_number(cost)}#{hops}"
                current.add(item_id)
                out.append({
                    'id': item_id,
                    'label': f"{node}:{format_number(cost)}",
                    'priority': cost,
                    # an outdated copy: the node's cost has improved since this was inserted
                    'stale': key != self.ws.key(node),
                    'highlight': previous is not None and item_id not in previous,
                })
            return out

        def block_json(block_id, bound, items):
            return {'id': block_id, 'bound': format_bound(bound), 'items': items_json(items)}

        state = {
            'title': f"D at level {entry['level']}: M = {snap['m_limit']}, B = {format_bound(snap['bound'])}",
            'heap_blocks': [block_json(*block) for block in snap['heap_blocks']],
            'b_block': block_json(*snap['b_block']),
            'prepend_blocks': [
                block_json(f"d0-{structure_id}-{i}", max(items), items)
                for i, items in enumerate(snap['prepend_blocks'])
            ],
        }
        self._previous_items[structure_id] = current
        return state

    # ------------------------------------------------------------------
    # Static graph definition
    # ------------------------------------------------------------------

    def _build_graph_def(self):
        graph = self.ws.graph
        if all('pos' in graph.nodes[n] for n in graph.nodes):
            positions = {n: graph.nodes[n]['pos'] for n in graph.nodes}
        else:
            try:
                positions = nx.kamada_kawai_layout(graph)
            except Exception:
                positions = nx.spring_layout(graph, seed=0)
        positions = _normalise_positions(positions)

        nodes = [{'id': str(n), 'label': str(n), 'x': positions[n][0], 'y': positions[n][1]}
                 for n in graph.nodes]
        self._directed = graph.is_directed()
        edges = []
        self._edge_ids = set()
        for u, v, weight in graph.edges(data='weight', default=1):
            edges.append({'source': str(u), 'target': str(v), 'weight': weight})
            self._edge_ids.add((str(u), str(v)))
        return {'directed': self._directed, 'nodes': nodes, 'edges': edges}

    def _edge_key(self, u, v):
        # undirected edges are stored once, in whichever direction networkx gave
        key = (str(u), str(v))
        if key in self._edge_ids:
            return key
        if not self._directed and (str(v), str(u)) in self._edge_ids:
            return (str(v), str(u))
        return None

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def to_dict(self):
        return {'algorithm': 'bmssp', 'graph': self._graph_def, 'frames': self.frames}

    def write(self, path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=1, ensure_ascii=False, default=_json_number)


def _normalise_positions(positions, extent=0.9):
    # scale each axis to [-extent, extent] (a single node or a flat axis goes to 0)
    xs = [p[0] for p in positions.values()]
    ys = [p[1] for p in positions.values()]

    def scale(value, lo, hi):
        return 0.0 if hi - lo < 1e-12 else round((2 * (value - lo) / (hi - lo) - 1) * extent, 4)

    return {n: (scale(p[0], min(xs), max(xs)), scale(p[1], min(ys), max(ys)))
            for n, p in positions.items()}


def _json_number(value):
    # numpy floats from networkx layouts
    try:
        return float(value)
    except (TypeError, ValueError):
        raise TypeError(f"not JSON serialisable: {value!r}")
