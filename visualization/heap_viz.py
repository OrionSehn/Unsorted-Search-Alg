"""
HeapViz — Manim VGroup that renders a binary min-heap as a tree.

Each node can display:
  - A primary label (e.g. node id)
  - A numeric priority (e.g. distance)
  - Optional extra lines of text below (e.g. "via: B")

Transitions between HeapState snapshots produce swap animations.
"""

from __future__ import annotations
from manim import *
from schema import HeapState, HeapNodeState

# ---------------------------------------------------------------------------
# Visual constants
# ---------------------------------------------------------------------------

HEAP_BOX_W         = 0.52   # half-width of each heap node box
HEAP_BOX_H         = 0.38   # half-height
HEAP_BOX_CORNER    = 0.08   # corner radius for RoundedRectangle
HEAP_NODE_COLOR    = ManimColor("#264653")
HEAP_HIGHLIGHT_COLOR = ManimColor("#e76f51")
HEAP_STROKE_COLOR  = WHITE
HEAP_STROKE_WIDTH  = 2
LABEL_FONT_SIZE    = 20
PRIORITY_FONT_SIZE = 17
EXTRA_FONT_SIZE    = 14
EDGE_COLOR         = ManimColor("#6d6875")
EDGE_STROKE_WIDTH  = 2.0

# Layout
LEVEL_SPACING  = 1.35   # vertical distance between tree levels
SIBLING_SPACING = 1.15  # base horizontal spacing (multiplied by 2^level_gap)


def _box_exit(unit: np.ndarray, half_w: float, half_h: float) -> float:
    """Distance along `unit` from box center to the box boundary."""
    ux, uy = abs(unit[0]), abs(unit[1])
    if ux < 1e-9:
        return half_h
    if uy < 1e-9:
        return half_w
    return min(half_w / ux, half_h / uy)


def _tree_positions(n: int, level_spacing: float = LEVEL_SPACING,
                    sibling_spacing: float = SIBLING_SPACING) -> list[np.ndarray]:
    """Return world positions for a 0-indexed flat heap of size n, root at top."""
    if n == 0:
        return []
    positions = []
    for i in range(n):
        level = int(np.log2(i + 1))
        nodes_in_level = 2 ** level
        pos_in_level = i - (nodes_in_level - 1)
        total_width = sibling_spacing * (nodes_in_level - 1) if nodes_in_level > 1 else 0
        x = pos_in_level * sibling_spacing - total_width / 2
        y = -level * level_spacing
        positions.append(np.array([x, y, 0.0]))
    return positions


class HeapNodeVGroup(VGroup):
    """Visual representation of a single heap node."""

    def __init__(self, hnode: HeapNodeState, pos: np.ndarray, **kwargs):
        super().__init__(**kwargs)
        self.heap_id = hnode.id

        fill = HEAP_HIGHLIGHT_COLOR if hnode.highlight else HEAP_NODE_COLOR
        self.box = RoundedRectangle(
            width=HEAP_BOX_W * 2,
            height=HEAP_BOX_H * 2,
            corner_radius=HEAP_BOX_CORNER,
            fill_color=fill,
            fill_opacity=1,
            stroke_color=HEAP_STROKE_COLOR,
            stroke_width=HEAP_STROKE_WIDTH,
        ).move_to(pos)

        self.label_text = Text(hnode.label, font_size=LABEL_FONT_SIZE, color=WHITE)
        self.priority_text = Text(str(hnode.priority), font_size=PRIORITY_FONT_SIZE, color=YELLOW)

        inner = VGroup(self.label_text, self.priority_text).arrange(DOWN, buff=0.04)
        inner.move_to(pos)

        self.extra_group = VGroup()
        if hnode.extra_lines:
            lines = [Text(l, font_size=EXTRA_FONT_SIZE, color=LIGHT_GREY) for l in hnode.extra_lines]
            self.extra_group = VGroup(*lines).arrange(DOWN, buff=0.03)
            self.extra_group.next_to(self.box, DOWN, buff=0.06)

        self.add(self.box, inner, self.extra_group)


class HeapViz(VGroup):
    """
    Renders a binary heap as a positioned tree.

    Usage::

        hv = HeapViz(initial_heap_state, center=ORIGIN)
        self.add(hv)
        anims = hv.apply_state(next_heap_state)
        self.play(*anims)
    """

    def __init__(self, initial_state: HeapState, center: np.ndarray = ORIGIN, **kwargs):
        super().__init__(**kwargs)
        self.center_offset = center

        # Indexed list of HeapNodeVGroup (heap order)
        self._nodes: list[HeapNodeVGroup] = []
        # Lines connecting parent->child
        self._edges: list[Line] = []

        self._build(initial_state)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _world_pos(self, raw_pos: np.ndarray) -> np.ndarray:
        return raw_pos + self.center_offset

    def _build(self, state: HeapState):
        self._nodes.clear()
        self._edges.clear()
        self.submobjects.clear()

        positions = _tree_positions(len(state.nodes))
        for i, hnode in enumerate(state.nodes):
            pos = self._world_pos(positions[i])
            vnode = HeapNodeVGroup(hnode, pos)
            self._nodes.append(vnode)
            self.add(vnode)

        # Compute initial edges — stored in self._edges so the scene can
        # add them directly to scene.mobjects via get_initial_edges().
        for i in range(len(state.nodes)):
            for child_idx in (2 * i + 1, 2 * i + 2):
                if child_idx < len(state.nodes):
                    p_pos = self._world_pos(positions[i])
                    c_pos = self._world_pos(positions[child_idx])
                    self._edges.append(self._make_edge(p_pos, c_pos))

    def get_initial_edges(self) -> list:
        """Return the edge Lines built during __init__ for the scene to add."""
        return list(self._edges)

    def _make_edge(self, p: np.ndarray, c: np.ndarray) -> Line:
        direction = c - p
        norm = np.linalg.norm(direction)
        if norm < 1e-6:
            return Line(p, c, stroke_color=EDGE_COLOR, stroke_width=EDGE_STROKE_WIDTH)
        unit = direction / norm
        start = p + unit * _box_exit(unit,  HEAP_BOX_W, HEAP_BOX_H)
        end   = c - unit * _box_exit(unit,  HEAP_BOX_W, HEAP_BOX_H)
        return Line(start, end, stroke_color=EDGE_COLOR, stroke_width=EDGE_STROKE_WIDTH)

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def apply_state(self, new_state: HeapState) -> list[Animation]:
        """
        Diff old heap vs new heap, return node animations.

        Edges are removed synchronously here (before the animation plays)
        and re-added synchronously in finish_apply() (after nodes settle).
        This keeps edges visible only during pauses, never mid-transition.
        """
        new_count = len(new_state.nodes)
        new_positions = _tree_positions(new_count)

        # Remove edges immediately — they'll be rebuilt in finish_apply()
        for edge in self._edges:
            if edge in self.submobjects:
                self.remove(edge)
        self._edges.clear()

        anims: list[Animation] = []

        old_id_to_idx: dict[str, int] = {vn.heap_id: i for i, vn in enumerate(self._nodes)}

        handled_old: set[int] = set()
        new_vnodes: list[HeapNodeVGroup] = []

        for new_idx, hnode in enumerate(new_state.nodes):
            target_pos = self._world_pos(new_positions[new_idx])

            if hnode.id in old_id_to_idx:
                old_idx = old_id_to_idx[hnode.id]
                old_vnode = self._nodes[old_idx]
                handled_old.add(old_idx)
                replacement = HeapNodeVGroup(hnode, target_pos)

                if old_idx == new_idx:
                    old_priority = old_vnode.priority_text.text
                    old_label    = old_vnode.label_text.text
                    if str(hnode.priority) != old_priority or hnode.label != old_label or hnode.highlight:
                        anims.append(Transform(old_vnode, replacement))
                else:
                    anims.append(Transform(old_vnode, replacement))
                new_vnodes.append(old_vnode)
            else:
                new_vnode = HeapNodeVGroup(hnode, target_pos)
                # Add to VGroup before FadeIn so the node is already in the
                # scene context — prevents Manim's introducer mechanism from
                # bypassing the VGroup and adding it to scene.mobjects directly.
                self.add(new_vnode)
                anims.append(FadeIn(new_vnode))
                new_vnodes.append(new_vnode)

        for old_idx, old_vnode in enumerate(self._nodes):
            if old_idx not in handled_old:
                anims.append(FadeOut(old_vnode))

        self._pending_state = new_state
        self._pending_vnodes = new_vnodes
        self._pending_new_positions = new_positions

        return anims

    def finish_apply(self) -> list:
        """
        Call this after self.play(*anims).  Returns the new edge Line objects;
        the caller (scene) must add them to the scene directly so they are
        visible during the subsequent wait().  The scene is also responsible
        for removing them before the next step's animations begin.
        """
        if not hasattr(self, "_pending_state"):
            return []
        edges = self._finish_apply(
            self._pending_state,
            self._pending_vnodes,
            self._pending_new_positions,
        )
        del self._pending_state, self._pending_vnodes, self._pending_new_positions
        return edges

    def _finish_apply(self, new_state, new_vnodes, new_positions) -> list:
        self._nodes = new_vnodes

        # Remove stale node VGroups
        for old_vn in list(self.submobjects):
            if isinstance(old_vn, HeapNodeVGroup) and old_vn not in new_vnodes:
                self.remove(old_vn)

        n = len(new_state.nodes)
        new_edges = []
        for i in range(n):
            for child_idx in (2 * i + 1, 2 * i + 2):
                if child_idx < n:
                    p_pos = self._world_pos(new_positions[i])
                    c_pos = self._world_pos(new_positions[child_idx])
                    new_edges.append(self._make_edge(p_pos, c_pos))

        self._edges = new_edges
        # Edges are returned to the caller (scene) to be added to scene.mobjects
        # directly — this is the only reliable way to ensure they render during
        # wait() in Manim's Cairo renderer.
        return new_edges
