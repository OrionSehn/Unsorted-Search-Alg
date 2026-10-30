# Manim Algorithm Visualization

Split-screen visualization: directed graph (left) + binary heap (right).

## Setup

```powershell
pip install manim
```

Manim also needs Cairo, FFmpeg, and LaTeX for full-quality renders.
Quickest path on Windows: `winget install Gyan.FFmpeg`, then `pip install manim`.

## Run

```powershell
# Low quality (fast preview)
manim -pql dijkstra_scene.py DijkstraScene

# High quality
manim -pqh dijkstra_scene.py DijkstraScene
```

## File layout

| File | Purpose |
|---|---|
| `schema.py` | Dataclasses that parse the JSON replay format |
| `graph_viz.py` | `GraphViz` — directed graph Manim VGroup |
| `heap_viz.py` | `HeapViz` — binary heap tree Manim VGroup |
| `dijkstra_scene.py` | Main `DijkstraScene`; drives both from a JSON file |
| `sample_graph.json` | 6-node directed graph + full Dijkstra replay |

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

## Reusing with a different algorithm

1. Produce a JSON file matching the schema above.
2. Either change `REPLAY_FILE` in `dijkstra_scene.py`, or subclass `DijkstraScene`:

```python
class AStarScene(DijkstraScene):
    replay_file = "astar_replay.json"
```

Node states available: `unexplored`, `open`, `closed`.  
Each heap node supports `extra_lines` for algorithm-specific metadata (e.g. `["f=12", "g=5", "h=7"]`).
