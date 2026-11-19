"""
Writes a recorded BMSSP run on a sample directed graph, for bmssp_scene.py.

    python make_bmssp_replay.py                  # 13 nodes -> bmssp_replay.json
    python make_bmssp_replay.py --large          # 26 nodes -> bmssp_replay_large.json
    python make_bmssp_replay.py [--large] other.json   # or to another path

Small example: 13 nodes, so k = 1, t = 2 and the top-level call is at level 2:
D at level 2 holds blocks of up to M = 4 values, and level-1 calls use M = 1.
Edge weights include ties, so the (cost, hops, node) tie-break shows up,
and the level-2 heap of blocks holds blocks with several values.

Large example: 26 nodes (about twice the size), so k = 1, t = 2 but the
top-level call is at level 3. That gives three sizes of D, one per level:
M = 16 (level 3), M = 4 (level 2) and M = 1 (level 1). At level 3, D0 gets
blocks of up to ceil(16 / 2) = 8 values from BatchPrepend; the level-2 heap
of blocks holds blocks of up to 4.
"""

import os
import random
import string
import sys

import networkx as nx

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))   # the project root, for unsorted_search

from unsorted_search import bmssp_shortest_paths


def sample_graph() -> nx.DiGraph:
    # positions are in [-1, 1]; the graph flows left to right
    positions = {
        "A": (-0.95,  0.00),
        "B": (-0.50,  0.65), "C": (-0.50,  0.00), "D": (-0.50, -0.65),
        "E": (-0.02,  0.85), "F": (-0.02,  0.30), "G": (-0.02, -0.30), "H": (-0.02, -0.85),
        "I": ( 0.45,  0.60), "J": ( 0.45,  0.00), "K": ( 0.45, -0.60),
        "L": ( 0.92,  0.32), "M": ( 0.92, -0.32),
    }
    # the left-to-right edges plus two longer ones (D->K, F->L) that run between
    # other nodes; chosen so the level-2 heap of blocks holds blocks with
    # several values, not just one
    edges = [
        ("A", "B", 4), ("A", "C", 1), ("A", "D", 3),
        ("B", "E", 2), ("B", "F", 4), ("C", "F", 3), ("C", "G", 3), ("D", "G", 2), ("D", "H", 2),
        ("D", "K", 4), ("E", "I", 3), ("F", "I", 2), ("F", "J", 2), ("F", "L", 3), ("G", "J", 3),
        ("G", "K", 1), ("H", "K", 3), ("I", "L", 1), ("J", "L", 4), ("J", "M", 1), ("K", "M", 3),
    ]
    G = nx.DiGraph()
    for node, pos in positions.items():
        G.add_node(node, pos=pos)
    for u, v, w in edges:
        G.add_edge(u, v, weight=w)
    return G


# nodes per column of the large example, left to right (26 in total)
LARGE_COLUMNS = [1, 4, 5, 6, 5, 4, 1]
# weight seed; chosen (by trying seeds) so that every level's D gets used:
# level-3 D0 blocks of up to 8 values, and a level-2 heap of up to 3 blocks
LARGE_SEED = 26


def large_sample_graph(seed: int = LARGE_SEED) -> nx.DiGraph:
    '''
    26 nodes A..Z in columns (LARGE_COLUMNS). Each node has edges to the 2 or 3
    nearest nodes in the next column, so edges only join neighbouring columns
    and never cross over other nodes. Weights 1..5 from a fixed seed.
    '''
    rng = random.Random(seed)
    names = iter(string.ascii_uppercase)
    columns = []
    for c, size in enumerate(LARGE_COLUMNS):
        x = -0.95 + 1.9 * c / (len(LARGE_COLUMNS) - 1)
        ys = [0.0] if size == 1 else [0.9 - 1.8 * r / (size - 1) for r in range(size)]
        columns.append([(next(names), (round(x, 3), round(y, 3))) for y in ys])

    G = nx.DiGraph()
    for column in columns:
        for node, pos in column:
            G.add_node(node, pos=pos)
    for left, right in zip(columns, columns[1:]):
        fan_out = 3 if len(left) <= len(right) else 2
        for u, (_, uy) in left:
            nearest = sorted(right, key=lambda node_pos: abs(node_pos[1][1] - uy))[:fan_out]
            for v, _ in nearest:
                G.add_edge(u, v, weight=rng.randint(1, 5))
    return G


if __name__ == "__main__":
    args = sys.argv[1:]
    large = "--large" in args
    args = [a for a in args if a != "--large"]
    default_name = "bmssp_replay_large.json" if large else "bmssp_replay.json"
    out = args[0] if args else os.path.join(HERE, default_name)

    G = large_sample_graph() if large else sample_graph()
    cost, _ = bmssp_shortest_paths(G, "A", visualization_path=out)

    # sanity check against networkx before anyone renders it
    expected = nx.single_source_dijkstra_path_length(G, "A")
    assert all(cost[v] == d for v, d in expected.items()), "BMSSP result differs from Dijkstra"
    print(f"wrote {out} ({len(G)} nodes, {G.number_of_edges()} edges)")
