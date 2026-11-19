# Manim Algorithm Visualization

Split-screen visualizations: graph (left) + the algorithm's priority structure
(right) — a binary heap for Dijkstra, the block structure D for BMSSP.

## Setup

```powershell
pip install manim
```

Manim also needs Cairo, FFmpeg, and LaTeX for full-quality renders.
Quickest path on Windows: `winget install "FFmpeg (Essentials Build)"`, then `pip install manim`
(open a new terminal afterwards so `ffmpeg` is on PATH). LaTeX isn't needed.

## Run

```powershell
# Low quality (fast preview)
manim -pql dijkstra_scene.py DijkstraScene

# High quality
manim -pqh dijkstra_scene.py DijkstraScene
```

## BMSSP

Split-screen visualization of BMSSP (Duan et al., *Breaking the Sorting Barrier
for Directed Single-Source Shortest Paths*): the graph on the left, and on the
right the running calls plus the block structure D of the innermost call
(D0 prepend blocks, the heap of blocks ordered by bound, and the B block).

```powershell
python make_bmssp_replay.py                      # 13 nodes -> bmssp_replay.json
python make_bmssp_replay.py --large              # 26 nodes -> bmssp_replay_large.json
manim -pql bmssp_scene.py BMSSPScene             # fast preview
manim -pqh bmssp_scene.py BMSSPScene             # high quality

# the 26-node example (three levels of D: M = 16, 4 and 1)
$env:BMSSP_REPLAY="bmssp_replay_large.json"; manim -pql -o BMSSPSceneLarge bmssp_scene.py BMSSPScene

# a still of one frame (index from 0), to check the layout; manim writes it
# under media/images/ (copy it into stills/, which is git-ignored)
$env:BMSSP_STILL_FRAME=50; manim -s -qm bmssp_scene.py BMSSPStill
```

To record your own graph, pass a path to `bmssp_shortest_paths` in
`../unsorted_search.py`:

```python
cost, pred = bmssp_shortest_paths(G, source, visualization_path="my_replay.json")
```

then render with `$env:BMSSP_REPLAY="my_replay.json"; manim -pql bmssp_scene.py BMSSPScene`.
Keep graphs small (10–30 nodes; above 15 nodes they're drawn with smaller nodes). Give nodes a `pos=(x, y)` attribute to control
the layout; otherwise one is computed. Node ids must be comparable (they break ties).

Colours: graph nodes are *unexplored*, *has a cost*, *current set* (the set the
step works on) or *complete* (returned in some call's U). In D, each value is a
chip `node:cost`; *just added* chips are highlighted and *outdated copies*
(the node's cost improved after the value went in) are dimmed.

## File layout

| File | Purpose |
|---|---|
| `schema.py` | Dataclasses that parse the JSON replay format |
| `graph_viz.py` | `GraphViz` — directed (or undirected) graph Manim VGroup |
| `heap_viz.py` | `HeapViz` — binary heap tree Manim VGroup |
| `dijkstra_scene.py` | Main `DijkstraScene`; drives both from a JSON file |
| `sample_graph.json` | 6-node directed graph + full Dijkstra replay |
| `block_heap_viz.py` | `BlockHeapViz` — BMSSP's block structure D |
| `bmssp_scene.py` | `BMSSPScene` (and `BMSSPStill` for single frames) |
| `make_bmssp_replay.py` | Records BMSSP on a 13-node sample graph → `bmssp_replay.json`, or a 26-node one with `--large` → `bmssp_replay_large.json` |
| `../bmssp_recorder.py` | Turns a BMSSP run into replay frames (used by `unsorted_search.py`) |

## JSON schema

```jsonc
{
  "graph": {
    "nodes": [{ "id": "A", "label": "A", "x": -0.9, "y": 0.8 }],
    "edges": [{ "source": "A", "target": "B", "weight": 4 }]
  },
  "frames": [
    {
      "description": "Step description",
      "graph_state": {
        "nodes": [{ "id": "A", "state": "open|closed|unexplored", "label_extra": "d=0" }],
        "edges": [{ "source": "A", "target": "B", "highlight": true }]
      },
      "heap_state": {
        "nodes": [{ "id": "A", "priority": 0, "label": "A", "extra_lines": ["via: —"] }]
      }
    }
  ]
}
```

### Additions for BMSSP

All optional, so Dijkstra replays load unchanged:

```jsonc
{
  "algorithm": "bmssp",                 // default "dijkstra"
  "graph": { "directed": true, ... },   // false: lines without arrowheads, each edge listed once
  "frames": [
    {
      "description": "Pull: S_i = {C}, B_i = 2 (B)",
      "call_stack": ["BMSSP(l=2, B=∞)", "BMSSP(l=1, B=∞)"],   // outermost first
      "graph_state": { "nodes": [{ "id": "C", "state": "active", "label_extra": "d=1" }] },
      "block_state": {                  // null when no call has a D yet
        "title": "D at level 1: M = 1, B = ∞",
        "prepend_blocks": [ BLOCK, ... ],   // D0, smallest first
        "heap_blocks":    [ BLOCK, ... ],   // heap order: children of i are 2i+1, 2i+2
        "b_block": BLOCK                    // bound B, largest values
      }
    }
  ]
}
// BLOCK = { "id": "...", "bound": "4 (D)",
//           "items": [{ "id": "D@4#2", "label": "D:4", "priority": 4,
//                       "stale": false, "highlight": true }] }
```

Bounds are display strings: a key `(cost, hops, node)` is shown as `cost (node)`,
since the node is what breaks ties between equal costs.

## Reusing with a different algorithm

1. Produce a JSON file matching the schema above.
2. Either change `REPLAY_FILE` in `dijkstra_scene.py`, or subclass `DijkstraScene`:

```python
class AStarScene(DijkstraScene):
    replay_file = "astar_replay.json"
```

Node states available: `unexplored`, `open`, `closed`, `active`.  
Each heap node supports `extra_lines` for algorithm-specific metadata (e.g. `["f=12", "g=5", "h=7"]`).
