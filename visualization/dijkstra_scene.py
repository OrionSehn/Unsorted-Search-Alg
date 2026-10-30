"""
DijkstraScene — drives the split-screen visualization:
  left  half: directed graph with node state coloring
  right half: binary min-heap tree showing swaps

Run with:
    manim -pql dijkstra_scene.py DijkstraScene
    manim -pqh dijkstra_scene.py DijkstraScene   # high quality

Pass a different JSON file via REPLAY_FILE to reuse with other algorithms.
"""

from __future__ import annotations
import os
from manim import *
from schema import AlgorithmReplay
from graph_viz import GraphViz
from heap_viz import HeapViz

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPLAY_FILE = os.path.join(os.path.dirname(__file__), "sample_graph.json")

GRAPH_CENTER   = np.array([-3.2, 0.0, 0.0])
HEAP_CENTER    = np.array([ 2.8, 0.5, 0.0])

STEP_ANIM_TIME = 0.6   # seconds per state transition
STEP_HOLD_TIME = 0.8   # pause between steps

DIVIDER_COLOR  = ManimColor("#555566")

TITLE_FONT_SIZE    = 30
SUBTITLE_FONT_SIZE = 20
LABEL_FONT_SIZE    = 22


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------

class DijkstraScene(Scene):
    """
    Generic split-screen algorithm scene driven by a JSON replay file.

    To adapt for a different algorithm:
    1. Produce a JSON file with the same schema (see schema.py).
    2. Point REPLAY_FILE at it (or override the class attribute).
    """

    replay_file: str = REPLAY_FILE

    def construct(self):
        replay = AlgorithmReplay.load(self.replay_file)

        # --- Structural chrome ---
        self._build_chrome()

        # --- Graph visualization (left) ---
        graph_viz = GraphViz(replay.graph, scale=(2.6, 2.2))
        graph_viz.shift(GRAPH_CENTER)
        self.add(graph_viz)

        # --- Heap visualization (right) ---
        initial_heap = replay.frames[0].heap_state
        heap_viz = HeapViz(initial_heap, center=HEAP_CENTER)
        self.add(heap_viz)
        # Edges live as direct scene mobjects (not VGroup submobjects) so that
        # scene.add() / scene.remove() guarantee they render during wait().
        heap_edges: list = heap_viz.get_initial_edges()
        for edge in heap_edges:
            self.add(edge)

        # --- Step counter + description ---
        step_label = self._make_step_label(0, len(replay.frames), "")
        self.add(step_label)

        # Wait a beat before starting
        self.wait(0.6)

        # --- Animate each frame ---
        for i, frame in enumerate(replay.frames):
            # Remove edges from scene before this step's animations begin
            if heap_edges:
                self.remove(*heap_edges)
            heap_edges = []

            # Update step label
            new_label = self._make_step_label(i + 1, len(replay.frames), frame.description)
            self.play(Transform(step_label, new_label), run_time=0.3)

            # Graph transition
            graph_anims = graph_viz.apply_state(frame.graph_state)

            # Heap transition (edges removed inside apply_state, nodes animated)
            heap_anims = heap_viz.apply_state(frame.heap_state)

            all_anims = graph_anims + heap_anims
            if all_anims:
                self.play(*all_anims, run_time=STEP_ANIM_TIME)

            # Add new edges directly to scene — visible during wait()
            heap_edges = heap_viz.finish_apply()
            if heap_edges:
                self.add(*heap_edges)

            self.wait(STEP_HOLD_TIME)

        self.wait(1.0)

    # ------------------------------------------------------------------
    # Helper builders
    # ------------------------------------------------------------------

    def _build_chrome(self):
        # Vertical divider
        divider = Line(
            start=np.array([0.0,  3.8, 0.0]),
            end  =np.array([0.0, -3.8, 0.0]),
            stroke_color=DIVIDER_COLOR,
            stroke_width=1.5,
        )
        self.add(divider)

        # Section headings
        graph_heading = Text("Graph", font_size=LABEL_FONT_SIZE, color=GREY).move_to(
            np.array([GRAPH_CENTER[0], 3.3, 0.0])
        )
        heap_heading = Text("Priority Queue (Min-Heap)", font_size=LABEL_FONT_SIZE, color=GREY).move_to(
            np.array([HEAP_CENTER[0], 3.3, 0.0])
        )

        # Legend
        legend = self._build_legend(np.array([GRAPH_CENTER[0], -3.4, 0.0]))

        self.add(graph_heading, heap_heading, legend)

    def _build_legend(self, center: np.ndarray) -> VGroup:
        from graph_viz import NODE_COLORS
        from schema import NODE_STATE_UNEXPLORED, NODE_STATE_OPEN, NODE_STATE_CLOSED

        items = [
            (NODE_STATE_UNEXPLORED, "Unexplored"),
            (NODE_STATE_OPEN,       "Open"),
            (NODE_STATE_CLOSED,     "Closed"),
        ]
        entries = []
        for state, name in items:
            dot = Dot(radius=0.12, color=NODE_COLORS[state])
            lbl = Text(name, font_size=16, color=GREY)
            entry = VGroup(dot, lbl).arrange(RIGHT, buff=0.12)
            entries.append(entry)

        legend = VGroup(*entries).arrange(RIGHT, buff=0.4).move_to(center)
        return legend

    def _make_step_label(self, step: int, total: int, description: str) -> VGroup:
        counter = Text(f"Step {step}/{total}", font_size=SUBTITLE_FONT_SIZE, color=GREY_B)
        desc    = Text(description, font_size=SUBTITLE_FONT_SIZE - 2, color=WHITE)
        group   = VGroup(counter, desc).arrange(DOWN, buff=0.1)
        group.move_to(np.array([HEAP_CENTER[0], -3.1, 0.0]))
        return group
