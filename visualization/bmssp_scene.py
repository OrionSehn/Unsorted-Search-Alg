"""
BMSSPScene — split-screen visualization of BMSSP (Duan et al., "Breaking the
Sorting Barrier for Directed Single-Source Shortest Paths"):
  left  half: the graph, coloured by node state, with each node's cost
  right half: the call stack and the block structure D of the innermost call

Make a replay first (writes bmssp_replay.json next to this file):
    python make_bmssp_replay.py

Then render:
    manim -pql bmssp_scene.py BMSSPScene          # fast preview
    manim -pqh bmssp_scene.py BMSSPScene          # high quality

    # a still image of one frame, to check the layout (frame index from 0);
    # manim writes it under media/images/ (stills/ is git-ignored for copies)
    BMSSP_STILL_FRAME=12 manim -s -ql bmssp_scene.py BMSSPStill

Set BMSSP_REPLAY=path/to/replay.json to use another replay file, e.g. the
26-node example (python make_bmssp_replay.py --large):
    BMSSP_REPLAY=bmssp_replay_large.json manim -pql bmssp_scene.py BMSSPScene
"""

from __future__ import annotations
import os
from manim import *
from schema import (
    AlgorithmReplay,
    NODE_STATE_UNEXPLORED, NODE_STATE_OPEN, NODE_STATE_CLOSED, NODE_STATE_ACTIVE,
)
from graph_viz import GraphViz, NODE_COLORS
from block_heap_viz import BlockHeapViz, CHIP_COLOR, CHIP_NEW_COLOR, CHIP_STALE_COLOR

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPLAY_FILE = os.environ.get(
    "BMSSP_REPLAY", os.path.join(os.path.dirname(os.path.abspath(__file__)), "bmssp_replay.json"))

GRAPH_CENTER = np.array([-3.55, 0.15, 0.0])
GRAPH_SCALE  = (2.95, 2.55)
# graphs with more nodes than this get smaller nodes and text, spread wider
LARGE_GRAPH_NODES = 15
LARGE_GRAPH_STYLE = dict(scale=(3.15, 2.65), node_radius=0.26, font_scale=0.72)
PANEL_X      = 3.65          # centre of the right half
PANEL_WIDTH  = 6.5

HEADING_Y    = 3.6
STACK_TOP_Y  = 3.18
STACK_LINE_H = 0.24

STEP_ANIM_TIME = 1.0   # seconds per transition
STEP_HOLD_TIME = 1.8   # pause on each step, to read it

DIVIDER_COLOR = ManimColor("#555566")
HEADING_FONT_SIZE = 22
STACK_FONT_SIZE   = 14
DESC_FONT_SIZE    = 18


def make_graph_viz(graph_def) -> GraphViz:
    if len(graph_def.nodes) > LARGE_GRAPH_NODES:
        return GraphViz(graph_def, **LARGE_GRAPH_STYLE)
    return GraphViz(graph_def, scale=GRAPH_SCALE)


class BMSSPScene(Scene):
    replay_file: str = REPLAY_FILE

    def construct(self):
        replay = AlgorithmReplay.load(self.replay_file)
        self._build_chrome()

        self.graph_viz = make_graph_viz(replay.graph)
        self.graph_viz.shift(GRAPH_CENTER)
        self.add(self.graph_viz)

        self.block_viz = BlockHeapViz(center_x=PANEL_X, width=PANEL_WIDTH)
        self.stack_text = VGroup()
        self.step_label = VGroup()
        self.add(self.stack_text, self.step_label)

        self.wait(0.5)
        for i, frame in enumerate(replay.frames):
            self._show_frame(i, len(replay.frames), frame, run_time=STEP_ANIM_TIME)
            self.wait(STEP_HOLD_TIME)
        self.wait(1.5)

    # ------------------------------------------------------------------

    def _show_frame(self, index, total, frame, run_time):
        anims = []
        anims += self.graph_viz.apply_state(frame.graph_state)
        anims += self.block_viz.apply_state(frame.block_state)

        new_stack = self._make_call_stack(frame.call_stack)
        anims.append(Transform(self.stack_text, new_stack))
        new_step = self._make_step_label(index + 1, total, frame.description)
        anims.append(Transform(self.step_label, new_step))

        if run_time > 0:
            self.play(*anims, run_time=run_time)
        else:
            self.play(*anims, run_time=1 / config.frame_rate)

    def _build_chrome(self):
        self.add(Line([0.05, 3.85, 0], [0.05, -2.95, 0], stroke_color=DIVIDER_COLOR, stroke_width=1.5))
        self.add(Text("Graph", font_size=HEADING_FONT_SIZE, color=GREY)
                 .move_to([GRAPH_CENTER[0], HEADING_Y, 0]))
        self.add(Text("BMSSP calls  /  block structure D", font_size=HEADING_FONT_SIZE, color=GREY)
                 .move_to([PANEL_X, HEADING_Y, 0]))
        self.add(self._build_legend())

    def _build_legend(self) -> VGroup:
        entries = []
        for state, name in [(NODE_STATE_UNEXPLORED, "unexplored"), (NODE_STATE_OPEN, "has a cost"),
                            (NODE_STATE_ACTIVE, "current set"), (NODE_STATE_CLOSED, "complete")]:
            dot = Dot(radius=0.1, color=NODE_COLORS[state])
            entries.append(VGroup(dot, Text(name, font_size=14, color=GREY)).arrange(RIGHT, buff=0.1))
        for color, name, opacity in [(CHIP_COLOR, "value in D", 1), (CHIP_NEW_COLOR, "just added", 1),
                                     (CHIP_STALE_COLOR, "outdated copy", 0.55)]:
            chip = RoundedRectangle(width=0.32, height=0.2, corner_radius=0.04,
                                    fill_color=color, fill_opacity=opacity, stroke_width=0)
            entries.append(VGroup(chip, Text(name, font_size=14, color=GREY)).arrange(RIGHT, buff=0.1))
        legend = VGroup(*entries).arrange(RIGHT, buff=0.32)
        if legend.width > 13.4:
            legend.scale_to_fit_width(13.4)
        return legend.move_to([0, -3.25, 0])

    def _make_call_stack(self, call_stack: list[str]) -> VGroup:
        lines = [Text(("   " * depth) + ("↳ " if depth else "") + label,
                      font_size=STACK_FONT_SIZE, color=WHITE if depth == len(call_stack) - 1 else GREY_B)
                 for depth, label in enumerate(call_stack)]
        if not lines:
            lines = [Text("(no call running)", font_size=STACK_FONT_SIZE, color=GREY)]
        group = VGroup(*lines).arrange(DOWN, buff=0.06, aligned_edge=LEFT)
        group.move_to([PANEL_X - PANEL_WIDTH / 2 + group.width / 2 + 0.05,
                       STACK_TOP_Y - group.height / 2, 0])
        return group

    def _make_step_label(self, step: int, total: int, description: str) -> VGroup:
        counter = Text(f"Step {step}/{total}", font_size=DESC_FONT_SIZE - 2, color=GREY_B)
        desc = Text(description, font_size=DESC_FONT_SIZE, color=WHITE)
        group = VGroup(counter, desc).arrange(RIGHT, buff=0.35)
        if group.width > 13.6:
            group.scale_to_fit_width(13.6)
        return group.move_to([0, -3.68, 0])


class BMSSPStill(BMSSPScene):
    """
    Renders a single frame (BMSSP_STILL_FRAME, from 0) as a still image, for
    checking the layout: manim -s -ql bmssp_scene.py BMSSPStill
    """

    def construct(self):
        replay = AlgorithmReplay.load(self.replay_file)
        index = int(os.environ.get("BMSSP_STILL_FRAME", "0"))
        index = max(0, min(index, len(replay.frames) - 1))
        self._build_chrome()
        self.graph_viz = make_graph_viz(replay.graph)
        self.graph_viz.shift(GRAPH_CENTER)
        self.add(self.graph_viz)
        self.block_viz = BlockHeapViz(center_x=PANEL_X, width=PANEL_WIDTH)
        self.stack_text = VGroup()
        self.step_label = VGroup()
        self.add(self.stack_text, self.step_label)
        # jump straight to the chosen frame ("just added" highlights are stored
        # in the replay, so they don't depend on the frames before it)
        self._show_frame(index, len(replay.frames), replay.frames[index], run_time=0)
