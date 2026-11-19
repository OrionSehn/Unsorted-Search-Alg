"""
GraphViz — Manim VGroup that renders a directed (or undirected) graph and supports
animated transitions between node states (unexplored / open / closed / active).
"""

from __future__ import annotations
from manim import *
from schema import (
    GraphDef, GraphState, NodeState,
    NODE_STATE_UNEXPLORED, NODE_STATE_OPEN, NODE_STATE_CLOSED, NODE_STATE_ACTIVE,
)

# ---------------------------------------------------------------------------
# Visual constants — override by subclassing or monkey-patching
# ---------------------------------------------------------------------------

NODE_RADIUS = 0.38
NODE_COLORS = {
    NODE_STATE_UNEXPLORED: ManimColor("#4a4e69"),   # muted indigo-grey
    NODE_STATE_OPEN:       ManimColor("#f4a261"),   # warm orange
    NODE_STATE_CLOSED:     ManimColor("#2a9d8f"),   # teal
    NODE_STATE_ACTIVE:     ManimColor("#c0399d"),   # magenta (BMSSP: current set)
}
NODE_STROKE_COLOR = WHITE
NODE_STROKE_WIDTH = 2
NODE_FONT_SIZE    = 22
EXTRA_FONT_SIZE   = 16
EDGE_COLOR        = ManimColor("#9a8c98")
EDGE_HIGHLIGHT    = ManimColor("#e9c46a")
EDGE_STROKE_WIDTH = 2.5
WEIGHT_FONT_SIZE  = 18
LONG_EDGE_LENGTH  = 1.8   # world units; longer edges get their weight label placed clear of others
SCALE_X = 3.0   # world-units corresponding to x=1.0 in schema
SCALE_Y = 2.5


class GraphViz(VGroup):
    """
    Renders a directed graph with weighted edges.

    Usage::

        gv = GraphViz(graph_def, scale=(3.0, 2.5))
        self.add(gv)
        # smaller nodes and text for a bigger graph:
        gv = GraphViz(graph_def, scale=(3.0, 2.5), node_radius=0.27, font_scale=0.75)
        # later:
        anims = gv.apply_state(graph_state)
        self.play(*anims)
    """

    def __init__(self, graph_def: GraphDef, scale: tuple[float, float] = (SCALE_X, SCALE_Y),
                 node_radius: float = NODE_RADIUS, font_scale: float = 1.0, **kwargs):
        super().__init__(**kwargs)
        self.graph_def = graph_def
        self.sx, self.sy = scale
        self.node_radius = node_radius
        self.font_scale = font_scale   # multiplies all text sizes

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

    def _edge_ends(self, src: str, tgt: str):
        src_pos, tgt_pos = self._node_pos(src), self._node_pos(tgt)
        direction = tgt_pos - src_pos
        norm = np.linalg.norm(direction)
        if norm < 1e-6:
            return None
        unit = direction / norm
        return src_pos + unit * self.node_radius, tgt_pos - unit * self.node_radius, unit

    def _collect_label_obstacles(self):
        # spots a long edge's weight label should stay away from: node circles,
        # the cost labels under them, and the labels of the ordinary edges
        self._obstacles = []
        for node in self.graph_def.nodes:
            center = self._node_pos(node.id)
            self._obstacles.append(center)
            self._obstacles.append(center + np.array([0, -(self.node_radius + 0.17), 0]))
        for edge in self.graph_def.edges:
            ends = self._edge_ends(edge.source, edge.target)
            if ends and np.linalg.norm(ends[1] - ends[0]) < LONG_EDGE_LENGTH:
                start, end, unit = ends
                self._obstacles.append((start + end) / 2 + np.array([-unit[1], unit[0], 0]) * 0.18)

    def _weight_label_pos(self, start, end, unit) -> np.ndarray:
        perp = np.array([-unit[1], unit[0], 0]) * 0.18
        if np.linalg.norm(end - start) < LONG_EDGE_LENGTH:
            return (start + end) / 2 + perp
        # a long edge passes between other nodes: try a few spots along both sides
        # of it and take the one furthest from every obstacle
        candidates = [start + (end - start) * t + side * perp
                      for t in (0.3, 0.4, 0.5, 0.6, 0.7) for side in (1, -1)]
        return max(candidates, key=lambda p: min(np.linalg.norm(p - o) for o in self._obstacles))

    def _build(self):
        self._collect_label_obstacles()
        # Edges first so nodes render on top
        for edge in self.graph_def.edges:
            self._add_edge(edge.source, edge.target, edge.weight)
        for node in self.graph_def.nodes:
            self._add_node(node.id, node.label)

    def _add_node(self, node_id: str, label: str):
        pos = self._node_pos(node_id)
        circle = Circle(
            radius=self.node_radius,
            fill_color=NODE_COLORS[NODE_STATE_UNEXPLORED],
            fill_opacity=1,
            stroke_color=NODE_STROKE_COLOR,
            stroke_width=NODE_STROKE_WIDTH,
        ).move_to(pos)

        text = Text(label, font_size=NODE_FONT_SIZE * self.font_scale, color=WHITE).move_to(pos)

        # extra_label placeholder (empty at build time)
        extra = Text("", font_size=EXTRA_FONT_SIZE * self.font_scale, color=YELLOW).next_to(circle, DOWN, buff=0.08)

        group = VGroup(circle, text, extra)
        self._node_groups[node_id] = group
        self.add(group)

    def _add_edge(self, src: str, tgt: str, weight: float):
        # shortened at both ends to avoid overlapping the node circles
        ends = self._edge_ends(src, tgt)
        if ends is None:
            return
        start, end, unit = ends

        if self.graph_def.directed:
            arrow = Arrow(
                start=start,
                end=end,
                buff=0,
                stroke_color=EDGE_COLOR,
                stroke_width=EDGE_STROKE_WIDTH,
                tip_length=0.18 * min(1.0, self.font_scale + 0.1),
                max_tip_length_to_length_ratio=0.4,
            )
        else:
            arrow = Line(start, end, stroke_color=EDGE_COLOR, stroke_width=EDGE_STROKE_WIDTH)

        w_label = Text(str(weight), font_size=WEIGHT_FONT_SIZE * self.font_scale, color=EDGE_COLOR)
        w_label.move_to(self._weight_label_pos(start, end, unit))

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
                new_extra = Text(ns.label_extra, font_size=EXTRA_FONT_SIZE * self.font_scale, color=YELLOW)
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
