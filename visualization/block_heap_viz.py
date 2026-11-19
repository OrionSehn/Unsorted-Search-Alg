"""
BlockHeapViz — draws the block-based structure D used by BMSSP (Duan et al.,
Lemma 3.3), as recorded in a frame's block_state (see schema.py):

    D title
    D0 (BatchPrepend):   [block] [block] ...        smallest first
    heap of blocks:            [root]               binary heap, ordered by bound
                           [blk]     [blk]
    B block:                  [block, bound B]

Each block shows its upper bound above a box of value chips ("C:3" = node C at
cost 3). New values are highlighted, outdated (stale) copies are dimmed.

Unlike GraphViz this is not a VGroup: it adds and removes its mobjects on the
scene directly, via the animations it returns. Blocks are matched across
frames by id: a block that only moves slides to its new place, a block whose
contents change cross-fades, new blocks fade in and removed ones fade out.

Usage::

    bv = BlockHeapViz(center_x=3.6, width=6.4)
    anims = bv.apply_state(frame.block_state)   # None = no structure
    self.play(*anims)
"""

from __future__ import annotations
from manim import *
from schema import BlockStructureState, BlockState

# ---------------------------------------------------------------------------
# Visual constants
# ---------------------------------------------------------------------------

CHIP_W, CHIP_H     = 0.66, 0.32
CHIP_GAP           = 0.06
CHIPS_PER_ROW      = 8   # an M = 16 structure's D0 blocks (up to 8 values) fit on one line
BOX_PAD            = 0.08
CHIP_FONT_SIZE     = 14
BOUND_FONT_SIZE    = 13
CAPTION_FONT_SIZE  = 15
TITLE_FONT_SIZE    = 17

CHIP_COLOR         = ManimColor("#3d5a80")
CHIP_NEW_COLOR     = ManimColor("#e76f51")
CHIP_STALE_COLOR   = ManimColor("#5c5c66")
BOX_FILL           = ManimColor("#1b263b")
BOX_STROKE = {
    "heap":    WHITE,
    "b":       ManimColor("#e9c46a"),
    "prepend": ManimColor("#8ecae6"),
}
TREE_EDGE_COLOR    = ManimColor("#6d6875")

# vertical layout (world y); each section has its caption on its own line
TITLE_Y           = 2.2
PREPEND_CAPTION_Y = 1.88
PREPEND_Y         = 1.42
TREE_CAPTION_Y    = 0.85
TREE_TOP_Y        = 0.32
TREE_BOTTOM_Y     = -1.45
B_CAPTION_Y       = -1.95
B_BOTTOM_Y        = -2.95   # lowest point the B block may reach
CAPTION_INDENT    = 0.05
CAPTION_GAP       = 0.17    # space between a caption and the top of the blocks under it


def _make_chip(item) -> VGroup:
    if item.stale:
        fill, opacity, text_color = CHIP_STALE_COLOR, 0.55, GREY_B
    elif item.highlight:
        fill, opacity, text_color = CHIP_NEW_COLOR, 1.0, WHITE
    else:
        fill, opacity, text_color = CHIP_COLOR, 1.0, WHITE
    box = RoundedRectangle(width=CHIP_W, height=CHIP_H, corner_radius=0.06,
                           fill_color=fill, fill_opacity=opacity, stroke_width=0)
    label = Text(item.label, font_size=CHIP_FONT_SIZE, color=text_color)
    if label.width > CHIP_W - 0.06:
        label.scale_to_fit_width(CHIP_W - 0.06)
    label.move_to(box)
    return VGroup(box, label)


def make_block(block: BlockState, kind: str) -> VGroup:
    """A block centred on the origin: bound label above a box of value chips."""
    if block.items:
        chips = [_make_chip(item) for item in block.items]
        rows = [VGroup(*chips[i:i + CHIPS_PER_ROW]).arrange(RIGHT, buff=CHIP_GAP)
                for i in range(0, len(chips), CHIPS_PER_ROW)]
        content = VGroup(*rows).arrange(DOWN, buff=CHIP_GAP, aligned_edge=LEFT)
    else:
        content = Text("empty", font_size=CHIP_FONT_SIZE, color=GREY)
    box = RoundedRectangle(
        width=max(content.width, CHIP_W) + 2 * BOX_PAD,
        height=max(content.height, CHIP_H) + 2 * BOX_PAD,
        corner_radius=0.08, fill_color=BOX_FILL, fill_opacity=1,
        stroke_color=BOX_STROKE[kind], stroke_width=1.8,
    )
    content.move_to(box)
    bound = Text(f"≤ {block.bound}", font_size=BOUND_FONT_SIZE, color=GREY_B)
    bound.next_to(box, UP, buff=0.04)
    group = VGroup(box, content, bound)
    group.move_to(ORIGIN)
    return group


def _hang_below(mob: Mobject, top_y: float) -> None:
    """Move mob vertically so its top edge is at top_y (taller blocks grow downward)."""
    mob.shift(UP * (top_y - mob.get_top()[1]))


def _signature(block: BlockState, kind: str) -> tuple:
    return (kind, block.bound, tuple((i.label, i.stale, i.highlight) for i in block.items))


class BlockHeapViz:
    def __init__(self, center_x: float = 3.6, width: float = 6.4):
        self.center_x = center_x
        self.width = width
        self.left_x = center_x - width / 2
        # key -> (mobject, signature, center, scale)
        self._shown: dict[str, tuple] = {}

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _layout(self, state: BlockStructureState | None) -> tuple[dict, VGroup]:
        """Returns ({key: (mobject, signature)}, chrome) for the state, positioned."""
        blocks: dict[str, tuple] = {}
        chrome = VGroup()

        if state is None:
            chrome.add(Text("no block structure yet", font_size=CAPTION_FONT_SIZE, color=GREY)
                       .move_to([self.center_x, 0.3, 0]))
            return blocks, chrome

        title = Text(state.title, font_size=TITLE_FONT_SIZE, color=WHITE)
        if title.width > self.width:
            title.scale_to_fit_width(self.width)
        chrome.add(title.move_to([self.left_x + CAPTION_INDENT + title.width / 2, TITLE_Y, 0]))

        # --- D0: prepend blocks in a row, smallest first ---
        chrome.add(self._caption("D0  (BatchPrepend), smallest first", PREPEND_CAPTION_Y))
        if state.prepend_blocks:
            row = [make_block(b, "prepend") for b in state.prepend_blocks]
            group = VGroup(*row).arrange(RIGHT, buff=0.18)
            # fit the width, and the height between this caption and the next
            top = PREPEND_CAPTION_Y - CAPTION_GAP
            room = top - (TREE_CAPTION_Y + 0.15)
            scale = min(1.0, (self.width - 0.2) / group.width, room / group.height)
            group.scale(scale).move_to([self.center_x, 0, 0])
            _hang_below(group, top)
            for block, mob in zip(state.prepend_blocks, row):
                blocks["d0:" + block.id] = (mob, _signature(block, "prepend"))
        else:
            chrome.add(Text("empty", font_size=CHIP_FONT_SIZE, color=GREY)
                       .move_to([self.center_x, PREPEND_Y, 0]))

        # --- D1: binary heap of blocks, as a tree ---
        chrome.add(self._caption("D1  heap of blocks, ordered by bound", TREE_CAPTION_Y))
        heap = [make_block(b, "heap") for b in state.heap_blocks]
        if heap:
            depth = (len(heap)).bit_length() - 1          # levels 0..depth
            slot_w = max(m.width for m in heap) + 0.22
            block_h = max(m.height for m in heap)
            leaves = 2 ** depth
            level_h = min((TREE_TOP_Y - TREE_BOTTOM_Y) / max(depth, 1), 1.0)
            # shrink to fit both the width (leaves side by side) and the height
            # (each level needs room for a block plus a gap)
            scale = min(1.0, self.width / (leaves * slot_w))
            if depth > 0:
                scale = min(scale, (level_h - 0.12) / block_h)
            total_w = leaves * slot_w * scale
            # the root's top hangs below the caption; each level is level_h lower
            root_top = TREE_CAPTION_Y - CAPTION_GAP
            for i, mob in enumerate(heap):
                level = (i + 1).bit_length() - 1
                pos_in_level = i - (2 ** level - 1)
                x = self.center_x - total_w / 2 + (pos_in_level + 0.5) * total_w / 2 ** level
                mob.scale(scale).move_to([x, 0, 0])
                _hang_below(mob, root_top - level * level_h)
            for i, mob in enumerate(heap):
                for child in (2 * i + 1, 2 * i + 2):
                    if child < len(heap):
                        chrome.add(Line(mob[0].get_bottom(), heap[child][2].get_top(),
                                        stroke_color=TREE_EDGE_COLOR, stroke_width=1.6))
            for block, mob in zip(state.heap_blocks, heap):
                blocks["blk:" + block.id] = (mob, _signature(block, "heap"))
        else:
            chrome.add(Text("empty", font_size=CHIP_FONT_SIZE, color=GREY)
                       .move_to([self.center_x, TREE_TOP_Y, 0]))

        # --- the B block ---
        chrome.add(self._caption("D1  B block: bound B, largest values", B_CAPTION_Y))
        if state.b_block is not None:
            mob = make_block(state.b_block, "b")
            top = B_CAPTION_Y - CAPTION_GAP
            scale = min(1.0, self.width / mob.width, (top - B_BOTTOM_Y) / mob.height)
            mob.scale(scale).move_to([self.center_x, 0, 0])
            _hang_below(mob, top)
            blocks["blk:" + state.b_block.id] = (mob, _signature(state.b_block, "b"))

        return blocks, chrome

    def _caption(self, text: str, y: float) -> Text:
        caption = Text(text, font_size=CAPTION_FONT_SIZE, color=GREY_B)
        return caption.move_to([self.left_x + CAPTION_INDENT + caption.width / 2, y, 0])

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def apply_state(self, state: BlockStructureState | None) -> list[Animation]:
        new_blocks, chrome = self._layout(state)
        anims: list[Animation] = []
        shown: dict[str, tuple] = {}

        for key, (mob, sig) in new_blocks.items():
            center, width = mob.get_center(), mob.width
            if key in self._shown:
                old_mob, old_sig, old_center, old_width = self._shown[key]
                if old_sig == sig:
                    moved = (np.linalg.norm(old_center - center) > 1e-3
                             or abs(old_width - width) > 1e-3)
                    if moved:
                        anims.append(Transform(old_mob, mob))   # same content: slide
                    shown[key] = (old_mob, sig, center, width)
                    continue
                anims.append(FadeOut(old_mob))                  # content changed
            anims.append(FadeIn(mob))
            shown[key] = (mob, sig, center, width)

        for key, (old_mob, *_rest) in self._shown.items():
            # (the chrome entry is handled below, not as a block)
            if key != "__chrome__" and key not in new_blocks:
                anims.append(FadeOut(old_mob))

        # chrome (title, captions, tree edges): cross-fade when it changes
        chrome_sig = self._chrome_signature(chrome)
        old_chrome = self._shown.get("__chrome__")
        if old_chrome is None or old_chrome[1] != chrome_sig:
            if old_chrome is not None:
                anims.append(FadeOut(old_chrome[0]))
            anims.append(FadeIn(chrome))
            shown["__chrome__"] = (chrome, chrome_sig, None, None)
        else:
            shown["__chrome__"] = old_chrome

        self._shown = shown
        return anims

    @staticmethod
    def _chrome_signature(chrome: VGroup) -> tuple:
        parts = []
        for mob in chrome:
            if isinstance(mob, Text):
                parts.append(("text", mob.text, tuple(np.round(mob.get_center(), 3))))
            else:
                parts.append(("line", tuple(np.round(mob.get_start(), 3)), tuple(np.round(mob.get_end(), 3))))
        return tuple(parts)
