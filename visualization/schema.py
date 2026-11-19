"""
JSON schema dataclasses for graph-algorithm visualizations.

Top-level structure:
{
  "algorithm": "...",        # optional: "dijkstra" (default) or "bmssp"
  "graph": { ... },          # static graph definition
  "frames": [ ... ]          # ordered animation frames
}

Frame structure:
{
  "description": "...",       # optional label shown in step counter
  "graph_state": { ... },     # node/edge state overrides
  "heap_state": { ... },      # current binary-heap contents (Dijkstra)
  "block_state": { ... },     # current block structure D (BMSSP), or null
  "call_stack": ["..."]       # running calls, outermost first (BMSSP)
}

A frame uses heap_state (Dijkstra) or block_state (BMSSP); both are optional,
so replays written before block_state existed still load unchanged.
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
    # False: edges are drawn without arrowheads and each is listed once
    directed: bool = True

    @staticmethod
    def from_dict(d: dict) -> "GraphDef":
        return GraphDef(
            nodes=[NodeDef.from_dict(n) for n in d["nodes"]],
            edges=[EdgeDef.from_dict(e) for e in d["edges"]],
            directed=d.get("directed", True),
        )


# ---------------------------------------------------------------------------
# Per-frame state
# ---------------------------------------------------------------------------

NODE_STATE_UNEXPLORED = "unexplored"
NODE_STATE_OPEN       = "open"
NODE_STATE_CLOSED     = "closed"
NODE_STATE_ACTIVE     = "active"    # the nodes the current step works on (BMSSP)


@dataclass
class NodeState:
    """State of one graph node in a frame."""
    id: str
    state: str          # unexplored | open | closed | active
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
# Heap state (Dijkstra)
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
# Block structure state (BMSSP)
# The block-based structure D from Duan et al. (Lemma 3.3):
#   - heap_blocks:    a binary heap of blocks ordered by bound, in heap order
#                     (index 0 is the root; children of i are 2i+1 and 2i+2)
#   - b_block:        the last block, whose bound is always B
#   - prepend_blocks: D0, blocks added by BatchPrepend, smallest first
# ---------------------------------------------------------------------------

@dataclass
class BlockItemState:
    """One value stored in a block."""
    id: str                   # unique within the structure
    label: str                # e.g. "C:3" (node C at cost 3)
    priority: float           # the value's cost
    stale: bool = False       # outdated copy: the node's cost improved since it was added
    highlight: bool = False   # added since the previous frame

    @staticmethod
    def from_dict(d: dict) -> "BlockItemState":
        return BlockItemState(
            id=d["id"],
            label=d.get("label", d["id"]),
            priority=d["priority"],
            stale=d.get("stale", False),
            highlight=d.get("highlight", False),
        )


@dataclass
class BlockState:
    """One block: an upper bound and the (unsorted) values it holds."""
    id: str
    bound: str                # display text for the block's upper bound
    items: list[BlockItemState] = field(default_factory=list)

    @staticmethod
    def from_dict(d: dict) -> "BlockState":
        return BlockState(
            id=d["id"],
            bound=str(d.get("bound", "")),
            items=[BlockItemState.from_dict(i) for i in d.get("items", [])],
        )


@dataclass
class BlockStructureState:
    title: str
    heap_blocks: list[BlockState]
    b_block: Optional[BlockState]
    prepend_blocks: list[BlockState] = field(default_factory=list)

    @staticmethod
    def from_dict(d: dict) -> "BlockStructureState":
        return BlockStructureState(
            title=d.get("title", ""),
            heap_blocks=[BlockState.from_dict(b) for b in d.get("heap_blocks", [])],
            b_block=BlockState.from_dict(d["b_block"]) if d.get("b_block") else None,
            prepend_blocks=[BlockState.from_dict(b) for b in d.get("prepend_blocks", [])],
        )


# ---------------------------------------------------------------------------
# Animation frame
# ---------------------------------------------------------------------------

@dataclass
class AnimFrame:
    description: str
    graph_state: GraphState
    heap_state: HeapState = field(default_factory=lambda: HeapState(nodes=[]))
    block_state: Optional[BlockStructureState] = None
    call_stack: list[str] = field(default_factory=list)

    @staticmethod
    def from_dict(d: dict) -> "AnimFrame":
        return AnimFrame(
            description=d.get("description", ""),
            graph_state=GraphState.from_dict(d.get("graph_state", {"nodes": []})),
            heap_state=HeapState.from_dict(d.get("heap_state") or {"nodes": []}),
            block_state=BlockStructureState.from_dict(d["block_state"]) if d.get("block_state") else None,
            call_stack=list(d.get("call_stack", [])),
        )


# ---------------------------------------------------------------------------
# Top-level replay data
# ---------------------------------------------------------------------------

@dataclass
class AlgorithmReplay:
    graph: GraphDef
    frames: list[AnimFrame]
    algorithm: str = "dijkstra"

    @staticmethod
    def load(path: str) -> "AlgorithmReplay":
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return AlgorithmReplay(
            graph=GraphDef.from_dict(raw["graph"]),
            frames=[AnimFrame.from_dict(fr) for fr in raw["frames"]],
            algorithm=raw.get("algorithm", "dijkstra"),
        )
