# unsorted_routing

A learning implementation of BMSSP (Bounded Multi-Source Shortest Path) from
Duan et al., [*Breaking the Sorting Barrier for Directed Single-Source Shortest
Paths*](https://arxiv.org/abs/2504.17033) (arXiv:2504.17033). It computes
single-source shortest paths on a directed graph with non-negative edge weights.
The code follows the paper line by line so the algorithm is easy to study. It is
**slower than Dijkstra** in practice and is not meant as a fast solver.

## Setup

Developed with Python 3.15. In Windows PowerShell, from the project root:

```powershell
python -m venv env
.\env\Scripts\Activate.ps1
pip install -r requirements.txt
```

The solver only needs `networkx`. `manim` is only for the visualization, which
also needs FFmpeg:

```powershell
winget install "FFmpeg (Essentials Build)"
```

LaTeX is not needed; the scenes don't use `Tex`/`MathTex`.

## Usage

```python
import networkx as nx
from unsorted_search import bmssp_shortest_paths

G = nx.DiGraph()
G.add_weighted_edges_from([
    ("a", "b", 4), ("a", "c", 1), ("c", "b", 2),
    ("b", "d", 1), ("c", "d", 5),
])
G.add_node("e")  # not reachable from "a"

cost, pred = bmssp_shortest_paths(G, "a")
print(cost)  # {'a': 0, 'b': 3, 'c': 1, 'd': 4, 'e': inf}
print(pred)  # {'b': 'c', 'c': 'a', 'd': 'b'}
```

`bmssp_shortest_paths(graph, source, visualization_path=None)` returns
`(cost, predecessors)`:

- `cost`: `{node: shortest path cost}`, `inf` for unreachable nodes.
- `predecessors`: `{node: previous node on its shortest path}`; the source and
  unreachable nodes have no entry.
- Edge weights come from the `weight` attribute (default 1). A negative weight
  raises `ValueError`. Undirected graphs also work (each edge counts both ways).
- `visualization_path`: if given, the run is also recorded to that JSON file for
  the Manim scene (see [Visualization](#visualization)). The result is the same.

## How it is structured

`unsorted_search.py` maps onto the paper's algorithms:

- `bmssp_workspace`: shared state (costs, predecessors, hop counts) and the
  parameters `k = floor(log2(n)^(1/3))` and `t = floor(log2(n)^(2/3))`. Ties are
  broken by the key `(cost, hops, node)` (the paper's Assumption 2.1).
- `find_pivots` (Algorithm 1): k rounds of Bellman-Ford style relaxation from S,
  then the pivots are the roots of large trees in the shortest-path forest.
- `base_case` (Algorithm 2): Dijkstra from a single node, stopped after k + 1 nodes.
- `bmssp` (Algorithm 3): the recursive bounded call, using the block data
  structure D from `block_data_struct.py`.
- `bmssp_shortest_paths`: the top-level call, with `l = ceil(log2(n) / t)`,
  `S = {source}`, `B = inf`.

## Running the tests

The test files are plain scripts (each prints `All tests passed`), plus one
`unittest` module:

```powershell
python unsorted_search.py              # solver; checked against networkx Dijkstra
python block_data_struct.py            # block data structure D
python -m unittest test_red_black_tree # red-black tree
```

## Files

| File | Purpose |
|---|---|
| `unsorted_search.py` | The solver: `bmssp_shortest_paths`, `bmssp`, `find_pivots`, `base_case`, plus its tests |
| `block_data_struct.py` | `BlockHeap`, the block-based structure D (paper's Lemma 3.3), and `pull_n_smallest` (median of medians), plus tests |
| `red_black_tree.py` | Red-black tree used by `BlockHeap` to look up blocks by bound |
| `test_red_black_tree.py` | `unittest` tests for the red-black tree |
| `bmssp_recorder.py` | Records a BMSSP run as frames for the visualization |
| `visualization/` | Manim scenes for Dijkstra and BMSSP |

## Visualization

Manim scenes show the graph next to the algorithm's priority structure (the
block structure D for BMSSP). From `visualization/`:

```powershell
python make_bmssp_replay.py               # 13-node example -> bmssp_replay.json
python make_bmssp_replay.py --large       # 26-node example -> bmssp_replay_large.json
manim -pql bmssp_scene.py BMSSPScene      # fast preview of bmssp_replay.json

# render the large example instead
$env:BMSSP_REPLAY="bmssp_replay_large.json"; manim -pql bmssp_scene.py BMSSPScene
```

See [visualization/README.md](visualization/README.md) for high-quality renders,
single-frame stills, recording your own graph, and the replay format.

## Limitations

- Slower than Dijkstra: the goal is to follow the paper, not to be fast.
- The paper's transformation of the graph to constant degree is not
  implemented; the algorithm runs on the graph as given.
- Node ids must be comparable with each other (e.g. all ints or all strings),
  because ties are broken by node id.
- Edge weights must be non-negative.
