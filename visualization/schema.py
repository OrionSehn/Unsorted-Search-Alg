"""
JSON schema dataclasses for graph-algorithm visualizations.

Top-level structure:
{
  "graph": { ... },          # static graph definition
  "frames": [ ... ]          # ordered animation frames
}

Frame structure:
{
  "description": "...",       # optional label shown in step counter
  "graph_state": { ... },     # node/edge state overrides
  "heap_state": { ... }       # current heap contents
}
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import json


# ---------------------------------------------------------------------------
# Static graph definition
# ---------------------------------------------------------------------------

@dataclass
class EdgeDef:
    source: str
    target: str
    weight: float

    @staticmethod
    def from_dict(d: dict) -> "EdgeDef":
        return EdgeDef(source=d["source"], target=d["target"], weight=d["weight"])


@dataclass
class NodeDef:
    id: str
    label: str
    x: float   # normalized [-1, 1] range, scaled by caller
    y: float

    @staticmethod
    def from_dict(d: dict) -> "NodeDef":
        return NodeDef(id=d["id"], label=d.get("label", d["id"]), x=d["x"], y=d["y"])


@dataclass
class GraphDef:
    nodes: list[NodeDef]
    edges: list[EdgeDef]

    @staticmethod
    def from_dict(d: dict) -> "GraphDef":
        return GraphDef(
            nodes=[NodeDef.from_dict(n) for n in d["nodes"]],
            edges=[EdgeDef.from_dict(e) for e in d["edges"]],
        )


# ---------------------------------------------------------------------------
# Per-frame state
# ---------------------------------------------------------------------------

NODE_STATE_UNEXPLORED = "unexplored"
NODE_STATE_OPEN       = "open"
NODE_STATE_CLOSED     = "closed"


@dataclass
class NodeState:
    """State of one graph node in a frame."""
    id: str
    state: str          # unexplored | open | closed
    label_extra: str = ""   # optional extra text shown beneath node label

    @staticmethod
    def from_dict(d: dict) -> "NodeState":
        return NodeState(
            id=d["id"],
            state=d.get("state", NODE_STATE_UNEXPLORED),
            label_extra=d.get("label_extra", ""),
        )


@dataclass
class EdgeState:
    """Optional highlight state for edges."""
    source: str
    target: str
    highlight: bool = False

    @staticmethod
    def from_dict(d: dict) -> "EdgeState":
        return EdgeState(
            source=d["source"],
            target=d["target"],
            highlight=d.get("highlight", False),
        )


@dataclass
class GraphState:
    nodes: list[NodeState]
    edges: list[EdgeState] = field(default_factory=list)

    @staticmethod
    def from_dict(d: dict) -> "GraphState":
        return GraphState(
            nodes=[NodeState.from_dict(n) for n in d.get("nodes", [])],
            edges=[EdgeState.from_dict(e) for e in d.get("edges", [])],
        )


# ---------------------------------------------------------------------------
# Heap state
# ---------------------------------------------------------------------------

@dataclass
class HeapNodeState:
    """One node in the heap at a given frame."""
    id: str                   # unique identifier (e.g. graph node id)
    priority: float           # numeric key (e.g. distance)
    label: str                # primary display text
    extra_lines: list[str] = field(default_factory=list)  # additional text rows
    highlight: bool = False   # briefly flash this node

    @staticmethod
    def from_dict(d: dict) -> "HeapNodeState":
        return HeapNodeState(
            id=d["id"],
            priority=d["priority"],
            label=d.get("label", d["id"]),
            extra_lines=d.get("extra_lines", []),
            highlight=d.get("highlight", False),
        )


@dataclass
class HeapState:
    """
    The heap is represented as a flat list in heap order.
    Index 0 is the root; children of index i are 2i+1 and 2i+2.
    """
    nodes: list[HeapNodeState]

    @staticmethod
    def from_dict(d: dict) -> "HeapState":
        return HeapState(nodes=[HeapNodeState.from_dict(n) for n in d.get("nodes", [])])


# ---------------------------------------------------------------------------
# Animation frame
# ---------------------------------------------------------------------------

@dataclass
class AnimFrame:
    description: str
    graph_state: GraphState
    heap_state: HeapState

    @staticmethod
    def from_dict(d: dict) -> "AnimFrame":
        return AnimFrame(
            description=d.get("description", ""),
            graph_state=GraphState.from_dict(d.get("graph_state", {"nodes": []})),
            heap_state=HeapState.from_dict(d.get("heap_state", {"nodes": []})),
        )


# ---------------------------------------------------------------------------
# Top-level replay data
# ---------------------------------------------------------------------------

@dataclass
class AlgorithmReplay:
    graph: GraphDef
    frames: list[AnimFrame]

    @staticmethod
    def load(path: str) -> "AlgorithmReplay":
        with open(path, "r") as f:
            raw = json.load(f)
        return AlgorithmReplay(
            graph=GraphDef.from_dict(raw["graph"]),
            frames=[AnimFrame.from_dict(fr) for fr in raw["frames"]],
        )
