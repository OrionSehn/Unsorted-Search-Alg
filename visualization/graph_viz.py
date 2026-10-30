"""
GraphViz — Manim VGroup that renders a directed graph and supports
animated transitions between node states (unexplored / open / closed).
"""

from __future__ import annotations
from manim import *
from schema import (
    GraphDef, GraphState, NodeState,
    NODE_STATE_UNEXPLORED, NODE_STATE_OPEN, NODE_STATE_CLOSED,
)

# ---------------------------------------------------------------------------
# Visual constants — override by subclassing or monkey-patching
# ---------------------------------------------------------------------------

NODE_RADIUS = 0.38
NODE_COLORS = {
    NODE_STATE_UNEXPLORED: ManimColor("#4a4e69"),   # muted indigo-grey
    NODE_STATE_OPEN:       ManimColor("#f4a261"),   # warm orange
    NODE_STATE_CLOSED:     ManimColor("#2a9d8f"),   # teal
}
NODE_STROKE_COLOR = WHITE
NODE_STROKE_WIDTH = 2
NODE_FONT_SIZE    = 22
EXTRA_FONT_SIZE   = 16
EDGE_COLOR        = ManimColor("#9a8c98")
EDGE_HIGHLIGHT    = ManimColor("#e9c46a")
EDGE_STROKE_WIDTH = 2.5
WEIGHT_FONT_SIZE  = 18
SCALE_X = 3.0   # world-units corresponding to x=1.0 in schema
SCALE_Y = 2.5


class GraphViz(VGroup):
    """
    Renders a directed graph with weighted edges.

    Usage::

        gv = GraphViz(graph_def, scale=(3.0, 2.5))
        self.add(gv)
        # later:
        anims = gv.apply_state(graph_state)
        self.play(*anims)
    """

    def __init__(self, graph_def: GraphDef, scale: tuple[float, float] = (SCALE_X, SCALE_Y), **kwargs):
        super().__init__(**kwargs)
        self.graph_def = graph_def
        self.sx, self.sy = scale

        # id -> VGroup containing circle + labels
        self._node_groups: dict[str, VGroup] = {}
        # (src, tgt) -> Arrow
        self._edge_arrows: dict[tuple[str, str], VMobject] = {}
        # (src, tgt) -> Text weight label
        self._weight_labels: dict[tuple[str, str], Text] = {}

        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _node_pos(self, node_id: str) -> np.ndarray:
        nd = next(n for n in self.graph_def.nodes if n.id == node_id)
        return np.array([nd.x * self.sx, nd.y * self.sy, 0.0])

    def _build(self):
        # Edges first so nodes render on top
        for edge in self.graph_def.edges:
            self._add_edge(edge.source, edge.target, edge.weight)
        for node in self.graph_def.nodes:
            self._add_node(node.id, node.label)

    def _add_node(self, node_id: str, label: str):
        pos = self._node_pos(node_id)
        circle = Circle(
            radius=NODE_RADIUS,
            fill_color=NODE_COLORS[NODE_STATE_UNEXPLORED],
            fill_opacity=1,
            stroke_color=NODE_STROKE_COLOR,
            stroke_width=NODE_STROKE_WIDTH,
        ).move_to(pos)

        text = Text(label, font_size=NODE_FONT_SIZE, color=WHITE).move_to(pos)

        # extra_label placeholder (empty at build time)
        extra = Text("", font_size=EXTRA_FONT_SIZE, color=YELLOW).next_to(circle, DOWN, buff=0.08)

        group = VGroup(circle, text, extra)
        self._node_groups[node_id] = group
        self.add(group)

    def _add_edge(self, src: str, tgt: str, weight: float):
        src_pos = self._node_pos(src)
        tgt_pos = self._node_pos(tgt)

        direction = tgt_pos - src_pos
        norm = np.linalg.norm(direction)
        if norm < 1e-6:
            return
        unit = direction / norm

        # Shorten to avoid overlapping node circles
        start = src_pos + unit * NODE_RADIUS
        end   = tgt_pos - unit * NODE_RADIUS

        arrow = Arrow(
            start=start,
            end=end,
            buff=0,
            stroke_color=EDGE_COLOR,
            stroke_width=EDGE_STROKE_WIDTH,
            tip_length=0.18,
            max_tip_length_to_length_ratio=0.4,
        )

        mid = (start + end) / 2
        perp = np.array([-unit[1], unit[0], 0]) * 0.18
        w_label = Text(str(weight), font_size=WEIGHT_FONT_SIZE, color=EDGE_COLOR).move_to(mid + perp)

        self._edge_arrows[(src, tgt)] = arrow
        self._weight_labels[(src, tgt)] = w_label
        self.add(arrow, w_label)

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def apply_state(self, state: GraphState) -> list[Animation]:
        """
        Return a list of animations that transition the graph to `state`.
        Pass the result directly to self.play(*anims).
        """
        anims: list[Animation] = []

        # Build lookup
        ns_map: dict[str, NodeState] = {ns.id: ns for ns in state.nodes}
        es_map = {(es.source, es.target): es for es in state.edges}

        for node_id, group in self._node_groups.items():
            circle, text, extra = group[0], group[1], group[2]
            ns = ns_map.get(node_id)
            if ns is None:
                continue

            target_color = NODE_COLORS[ns.state]
            if circle.fill_color != target_color:
                anims.append(circle.animate.set_fill(target_color))

            if ns.label_extra != extra.text:
                new_extra = Text(ns.label_extra, font_size=EXTRA_FONT_SIZE, color=YELLOW)
                new_extra.next_to(circle, DOWN, buff=0.08)
                anims.append(Transform(extra, new_extra))

        for key, arrow in self._edge_arrows.items():
            es = es_map.get(key)
            target_color = EDGE_HIGHLIGHT if (es and es.highlight) else EDGE_COLOR
            if arrow.stroke_color != target_color:
                anims.append(arrow.animate.set_color(target_color))

            w_label = self._weight_labels.get(key)
            if w_label:
                anims.append(w_label.animate.set_color(target_color))

        return anims

    def get_node_position(self, node_id: str) -> np.ndarray:
        return self._node_groups[node_id][0].get_center()
