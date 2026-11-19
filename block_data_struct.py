

from uuid import uuid4

from collections import deque

from math import ceil

import networkx as nx

from heapq import heappush, heappop

from red_black_tree import RedBlackTree

# create a tree of blocks
#
# Items stored in the structure must be DISTINCT. Blocks rely on covering
# disjoint value ranges (no two blocks share a bound), which duplicates break.
# To store values that may repeat (e.g. equal distances), insert tuples with a
# unique tiebreaker, e.g. (distance, vertex_id). Tuples compare element-wise,
# so the rest of the code works unchanged.

class Block:
    def __init__(self, items=None, bound=None, ID=None):
        # items: list of values (a fresh list each time if not given)
        # bound: upper bound on the values this block may hold. Defaults to
        #        max(items); pass it explicitly for an empty block (e.g. the B block)
        self.ID = ID if ID is not None else uuid4()
        self.items = items if items is not None else []
        if bound is not None:
            self.bound = bound
        else:
            self.bound = max(self.items) if self.items else None

    def add_item(self, item, m_limit):
        # m_limit: max items per block, passed in by the owning BlockHeap
        self.items.append(item)
        num_items = len(self.items)
        if num_items > m_limit:
            new_block = self.split_block()
            return new_block
        else:
            return None

    def split_block(self):
        # Splits around the median in O(n): the smaller half moves to a new block,
        # the larger half stays here (so this block's bound is unchanged).
        # Because items are distinct, every item in the new block is strictly less
        # than every item kept here, and both halves are non-empty.
        lower, upper = pull_n_smallest(self.items, len(self.items) // 2)
        self.items = upper
        return Block(items=lower)

    def __repr__(self):
        header = f"\n{'*'* 15} Block {'*'* 15}\n"
        body = f"ID: {self.ID},\nitems: {self.items},\nbound: {self.bound}\n"
        footer = f"{'*'* 40}\n"
        string = header + body + footer
        return string


class BlockHeap:
    '''
    Block-based structure D from Duan et al. (Lemma 3.3).

    Two parts, matching the paper:
      - D1 (insert):  blocks found by bound. The heap of blocks (self.blocks)
                      plus the B block (self.b_block), which always has bound B
                      and holds the largest values. Every block in the heap has a
                      bound below B and covers a smaller, separate range.
      - D0 (prepend): self.prepend_blocks, a sequence of blocks (lists) filled by
                      batch_prepend, smallest values first.

    All values must be strictly below bound_B.
    '''
    def __init__(self, m_limit, bound_B):
        # m_limit: max items per block, and the number of items pull() returns (M in the paper)
        # bound_B: upper bound on every value in the structure (B in the paper).
        #          Must be comparable with the items, e.g. (B,) when items are tuples
        if m_limit < 1:
            raise ValueError(f"m_limit must be at least 1, got {m_limit}")
        self.m_limit = m_limit
        self.bound = bound_B
        self.blocks = []
        self.num_blocks = 0
        self.bin_search_tree = RedBlackTree() # key is the index of the block in the heap, and value is the block's bound
        # D1 starts as a single empty block with upper bound B. It is kept out of
        # the heap so pop() never removes it
        self.b_block = Block(bound=bound_B)
        # D0: blocks added by batch_prepend, front = smallest values
        self.prepend_blocks = deque()

    def pull(self):
        '''
        Removes the m_limit smallest values (fewer if the structure holds fewer)
        and returns (bound, values), like the paper's "B_i, S_i <- D.Pull()".

        values: the pulled values, in no particular order.
        bound:  a bound x separating them from what is left:
                    max(values) < x <= min(remaining values)
                It is the smallest remaining value, or B if nothing is left.
                BMSSP uses it as the bound B_i for the recursive call on values.

        Like the paper's Pull: take up to m_limit of the smallest values from D0
        and up to m_limit of the smallest from D1, then return the m_limit smallest
        of those. Both parts must be checked, because a value inserted into D1
        after a batch_prepend can be smaller than values in D0.
        '''
        from_d0 = self._take_smallest_from_prepend(self.m_limit)
        from_d1 = self._take_smallest_from_blocks(self.m_limit)
        result, leftover = pull_n_smallest(from_d0 + from_d1, self.m_limit)

        if leftover:
            # values are distinct, so the leftovers are exactly those above the
            # largest returned value; put each back where it came from. They are
            # the smallest values left in their part, so they go at its front
            threshold = max(result)
            leftover_d0 = [x for x in from_d0 if x > threshold]
            leftover_d1 = [x for x in from_d1 if x > threshold]
            if leftover_d0:
                self.prepend_blocks.appendleft(leftover_d0)
            if leftover_d1:
                self._push_block(Block(items=leftover_d1))
        return self._smallest_remaining(), result

    def _smallest_remaining(self):
        '''
        The smallest value stored, or B if the structure is empty. O(M).
        D0's smallest value is in its front block. D1's is in the heap block
        with the smallest bound (blocks cover separate, increasing ranges), or
        in the B block if the heap is empty.
        '''
        candidates = []
        if self.prepend_blocks:
            candidates.append(min(self.prepend_blocks[0]))
        if self.num_blocks > 0:
            candidates.append(min(self.blocks[0].items))
        elif self.b_block.items:
            candidates.append(min(self.b_block.items))
        return min(candidates) if candidates else self.bound

    def is_empty(self):
        '''
        True if the structure holds no values. O(1).
        Relies on heap blocks and prepend blocks never being empty: pull()
        removes blocks it empties and only puts back non-empty leftovers,
        splits always leave both halves non-empty, and batch_prepend ignores
        empty batches. The B block is the only block allowed to be empty.
        '''
        return self.num_blocks == 0 and not self.prepend_blocks and not self.b_block.items

    def _take_smallest_from_prepend(self, n):
        # removes and returns the n smallest values in D0 (fewer if D0 is smaller)
        taken = []
        while self.prepend_blocks and len(taken) < n:
            front = self.prepend_blocks[0]
            needed = n - len(taken)
            if len(front) <= needed:
                taken.extend(front)
                self.prepend_blocks.popleft()
            else:
                smallest, rest = pull_n_smallest(front, needed)
                taken.extend(smallest)
                self.prepend_blocks[0] = rest
        return taken

    def _take_smallest_from_blocks(self, n):
        # removes and returns the n smallest values in D1 (fewer if D1 is smaller)
        taken = []
        while len(taken) < n:
            needed = n - len(taken)
            top_block = self.pop()
            if top_block is None:
                # heap is empty: only the B block is left. Take from it in place,
                # so it stays in the structure with its bound B
                smallest, rest = pull_n_smallest(self.b_block.items, needed)
                taken.extend(smallest)
                self.b_block.items = rest
                break
            if len(top_block.items) <= needed:
                taken.extend(top_block.items)
            else:
                # take part of the block, and put the rest back (its bound still holds)
                smallest, rest = pull_n_smallest(top_block.items, needed)
                taken.extend(smallest)
                top_block.items = rest
                self._push_block(top_block)
        return taken

    def batch_prepend(self, values):
        '''
        Adds values that are all smaller than every value currently stored
        (the caller must guarantee this, as in the paper's BatchPrepend).

        Like the paper: if there are at most m_limit values they form one block;
        otherwise they are split by repeated medians into blocks of at most
        ceil(m_limit / 2), in increasing order. The new blocks go in front of D0.
        '''
        values = list(values)
        if not values:
            return
        for value in values:
            if not value < self.bound:
                raise ValueError(f"value {value} is not below the bound {self.bound}")

        if len(values) <= self.m_limit:
            new_blocks = [values]
        else:
            new_blocks = self._split_into_ordered_blocks(values, max(1, ceil(self.m_limit / 2)))
        # extendleft adds one at a time to the front, so reverse to keep order
        self.prepend_blocks.extendleft(reversed(new_blocks))

    @staticmethod
    def _split_into_ordered_blocks(values, max_size):
        # repeatedly split at the median until every piece fits; pieces come out
        # in increasing order (every value in a piece < every value in the next)
        if len(values) <= max_size:
            return [values]
        lower, upper = pull_n_smallest(values, len(values) // 2)
        return (BlockHeap._split_into_ordered_blocks(lower, max_size)
                + BlockHeap._split_into_ordered_blocks(upper, max_size))

    def _push_block(self, block):
        if len(block.items) > self.m_limit:
            raise ValueError(f"Block exceeds maximum limit of items: {self.m_limit}")
        self.blocks.append(block)
        self.bin_search_tree.insert(self.num_blocks, block.bound)
        self._sift_up(self.num_blocks)
        self.num_blocks += 1

    def pop(self):
        # pops the heap block with the smallest bound (never the B block);
        # returns None when the heap is empty
        if not self.blocks:
            return None
        top_block = self.blocks[0]
        last = self.num_blocks - 1

        # remove the top block's entry (key 0) from the binary search tree
        self.bin_search_tree.delete(0, top_block.bound)

        if last > 0:
            # move the last block to the root, and re-key its tree entry from `last` to 0
            moved_block = self.blocks[last]
            self.bin_search_tree.delete(last, moved_block.bound)
            self.blocks[0] = moved_block
            self.bin_search_tree.insert(0, moved_block.bound)

        self.blocks.pop()
        self.num_blocks -= 1
        # tree is in sync with the heap here; _sift_down keeps it in sync on each swap
        self._sift_down(0)

        return top_block

    def peek(self):
        return self.blocks[0]

    def insert(self, value):
        if not value < self.bound:
            raise ValueError(f"value {value} is not below the bound {self.bound}")

        # find the heap block with the smallest bound >= value
        bound_node = self.bin_search_tree.find_bound(value)
        # if no heap block's bound is high enough, the value belongs in the B block
        if bound_node is None:
            relevant_block = self.b_block
        else:
            relevant_block = self.blocks[bound_node.key]

        # add it, splitting the block if it now holds more than m_limit items.
        # the split-off lower half becomes a new heap block (for the B block too:
        # the B block keeps the upper half and its bound B)
        new_block = relevant_block.add_item(value, self.m_limit)
        if new_block is not None:
            self._push_block(new_block)

    def _sift_down(self, index):
        while True:
            left = 2 * index + 1
            right = 2 * index + 2
            smallest = index
            if left < self.num_blocks and self.blocks[left].bound < self.blocks[smallest].bound:
                smallest = left
            if right < self.num_blocks and self.blocks[right].bound < self.blocks[smallest].bound:
                smallest = right
            if smallest == index:
                break
            self.blocks[index], self.blocks[smallest] = self.blocks[smallest], self.blocks[index]
            self.bin_search_tree.update_value(index, self.blocks[index].bound)
            self.bin_search_tree.update_value(smallest, self.blocks[smallest].bound)
            index = smallest

    def _sift_up(self, index):
        while index > 0:
            parent = (index - 1) // 2
            if self.blocks[index].bound < self.blocks[parent].bound:
                self.blocks[index], self.blocks[parent] = self.blocks[parent], self.blocks[index]
                self.bin_search_tree.update_value(index, self.blocks[index].bound)
                self.bin_search_tree.update_value(parent, self.blocks[parent].bound)
                index = parent
            else:
                break

    def __repr__(self):
        header= f"{'='* 20} block_heap {'='* 20}\n"
        body = f"m_limit:{self.m_limit},\nbound:{self.bound},\nnum_blocks:{self.num_blocks},\n\nblocks:{self.blocks}\n"
        b_block = f"B block: {self.b_block}"
        footer = f"{'='* 50}\n"
        prepend = f"Prepend blocks: {list(self.prepend_blocks)}\n"

        string = header + body + b_block + footer + prepend

        return string


# all tests below use a block limit of 5 and a bound B of 100 unless they say otherwise
TEST_M_LIMIT = 5
TEST_BOUND = 100


def _pull_items(bh):
    # most tests only check which values come out; this drops the bound
    bound, items = bh.pull()
    return items


def test_block_heap_size_1():
    bh = BlockHeap(TEST_M_LIMIT, TEST_BOUND)
    b1 = Block(items=[1, 2, 3])
    b2 = Block(items=[4, 5, 6])
    bh._push_block(b1)
    bh._push_block(b2)
    assert bh.pop() == b1
    assert bh.pop() == b2
    assert bh.pop() is None

def test_block_heap_size_2():
    bh = BlockHeap(TEST_M_LIMIT, TEST_BOUND)
    b1 = Block(items=[1, 2, 3])
    b2 = Block(items=[4, 5, 6])
    b3 = Block(items=[7, 8, 9])
    bh._push_block(b1)
    bh._push_block(b2)
    bh._push_block(b3)
    assert bh.pop() == b1
    assert bh.pop() == b2
    assert bh.pop() == b3
    assert bh.pop() is None

def test_block_heap_split_1():
    bh = BlockHeap(TEST_M_LIMIT, TEST_BOUND)
    b1 = Block(items=[1, 2, 4, 5, 6])
    b2 = Block(items=[7, 8, 9, 10, 11])
    bh._push_block(b1)
    bh._push_block(b2)

    bh.insert(3)  # b1 now has 6 items -> splits into its 3 smallest and 3 largest

    assert sorted(bh.pop().items) == [1, 2, 3]
    assert sorted(bh.pop().items) == [4, 5, 6]
    assert sorted(bh.pop().items) == [7, 8, 9, 10, 11]
    assert bh.pop() is None


def test_block_heap_insert_above_all_bounds_goes_to_b_block():
    bh = BlockHeap(TEST_M_LIMIT, TEST_BOUND)
    b1 = Block(items=[1, 2, 3])
    b2 = Block(items=[4, 5, 6])
    bh._push_block(b1)
    bh._push_block(b2)

    bh.insert(0)  # fits under b1's bound (3)
    bh.insert(7)  # larger than every heap block's bound -> goes into the B block

    assert sorted(bh.pop().items) == [0, 1, 2, 3]
    assert bh.pop().items == [4, 5, 6]
    assert bh.pop() is None          # pop() never returns the B block
    assert bh.b_block.items == [7]
    assert bh.b_block.bound == TEST_BOUND


# ---------------------------------------------------------------------------
# Block with an explicit bound
# ---------------------------------------------------------------------------

def test_block_explicit_bound():
    b = Block(bound=10)
    assert b.items == [] and b.bound == 10
    b = Block(items=[1, 2], bound=10)
    assert b.bound == 10            # explicit bound wins over max(items)


def test_block_default_bound_is_max():
    assert Block(items=[3, 1, 2]).bound == 3
    assert Block().bound is None


def test_blocks_do_not_share_items_or_ids():
    # each Block gets its own list and its own ID
    a, b = Block(), Block()
    a.items.append(1)
    assert b.items == []
    assert a.ID != b.ID


# ---------------------------------------------------------------------------
# The B block
# ---------------------------------------------------------------------------

def test_starts_with_single_empty_b_block():
    bh = BlockHeap(TEST_M_LIMIT, TEST_BOUND)
    assert bh.b_block.items == []
    assert bh.b_block.bound == TEST_BOUND
    assert bh.num_blocks == 0
    assert _pull_items(bh) == []


def test_insert_into_empty_structure_goes_to_b_block():
    bh = BlockHeap(TEST_M_LIMIT, TEST_BOUND)
    bh.insert(42)
    assert bh.b_block.items == [42]
    assert bh.num_blocks == 0


def test_insert_at_or_above_bound_rejected():
    bh = BlockHeap(TEST_M_LIMIT, TEST_BOUND)
    for bad in (TEST_BOUND, TEST_BOUND + 1):
        try:
            bh.insert(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for value {bad}")


def test_b_block_splits_and_keeps_bound():
    # m_limit = 3: 4, 3, 2 fill the B block; 1 makes 4 items, so it splits.
    # the lower half [1, 2] becomes a heap block, the B block keeps [3, 4] and bound B
    bh = BlockHeap(3, TEST_BOUND)
    for v in (4, 3, 2):
        bh.insert(v)
    assert bh.num_blocks == 0 and sorted(bh.b_block.items) == [2, 3, 4]
    bh.insert(1)
    assert bh.num_blocks == 1
    assert sorted(bh.blocks[0].items) == [1, 2]
    assert sorted(bh.b_block.items) == [3, 4]
    assert bh.b_block.bound == TEST_BOUND


def test_b_block_survives_being_emptied():
    # pulling everything out must leave the B block in place, so later inserts still work
    bh = BlockHeap(TEST_M_LIMIT, TEST_BOUND)
    for v in (5, 9, 1):
        bh.insert(v)
    assert sorted(_pull_items(bh)) == [1, 5, 9]
    assert bh.b_block.items == [] and bh.b_block.bound == TEST_BOUND
    bh.insert(50)
    assert _pull_items(bh) == [50]


def test_tuple_items_with_tuple_bound():
    # items as (cost, hops, node) keys, with B given as (B,)
    bh = BlockHeap(2, (10,))
    bh.insert((3, 1, 7))
    bh.insert((9, 2, 4))
    try:
        bh.insert((10, 0, 0))   # cost 10 is not below B = 10
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for cost == B")
    assert sorted(_pull_items(bh)) == [(3, 1, 7), (9, 2, 4)]


# ---------------------------------------------------------------------------
# pull() tests
# pull() should return the m_limit smallest items currently stored (in any
# order), remove them from the structure, and never lose or duplicate items.
# ---------------------------------------------------------------------------

def _heap_from_blocks(*item_lists, m_limit=TEST_M_LIMIT, bound=TEST_BOUND):
    bh = BlockHeap(m_limit, bound)
    for items in item_lists:
        bh._push_block(Block(items=list(items)))
    return bh


def test_pull_empty_heap():
    bh = BlockHeap(TEST_M_LIMIT, TEST_BOUND)
    assert _pull_items(bh) == []


def test_pull_single_full_block():
    # a block with exactly m_limit items should be returned whole
    bh = _heap_from_blocks([5, 3, 1, 4, 2])
    assert sorted(_pull_items(bh)) == [1, 2, 3, 4, 5]
    assert _pull_items(bh) == []


def test_pull_fewer_than_m_items_total():
    bh = _heap_from_blocks([2, 1], [3])
    assert sorted(_pull_items(bh)) == [1, 2, 3]
    assert _pull_items(bh) == []


def test_pull_takes_whole_block_then_part_of_next():
    # needs all of [1, 2, 3] plus the 2 smallest of [4, 5, 6]
    bh = _heap_from_blocks([1, 2, 3], [4, 5, 6])
    assert sorted(_pull_items(bh)) == [1, 2, 3, 4, 5]
    assert sorted(_pull_items(bh)) == [6]
    assert _pull_items(bh) == []


def test_pull_partial_block_keeps_leftovers():
    # takes [1, 2], then the 3 smallest of [6, 3, 5, 4]; 6 must be kept
    bh = _heap_from_blocks([2, 1], [6, 3, 5, 4])
    assert sorted(_pull_items(bh)) == [1, 2, 3, 4, 5]
    assert sorted(_pull_items(bh)) == [6]
    assert _pull_items(bh) == []


def test_pull_takes_from_heap_blocks_then_b_block():
    bh = _heap_from_blocks([1, 2], [3])
    bh.insert(50)   # above every heap bound -> B block
    bh.insert(60)
    assert sorted(_pull_items(bh)) == [1, 2, 3, 50, 60]
    assert _pull_items(bh) == []


def test_pull_after_insert_smaller_than_leftovers():
    # after the first pull, [11, 12] are left over; inserting 5 afterwards
    # means 5 is now among the smallest and must come out next
    bh = _heap_from_blocks([1, 2, 3, 4], [10, 11, 12])
    assert sorted(_pull_items(bh)) == [1, 2, 3, 4, 10]
    bh.insert(5)
    assert sorted(_pull_items(bh)) == [5, 11, 12]
    assert _pull_items(bh) == []


def test_block_split_with_duplicates():
    # equal distances are made distinct with a tiebreaker: (distance, id).
    # splitting must never produce an empty block or one over m_limit, and
    # the two halves must not overlap.
    b = Block(items=[(3, i) for i in range(5)])
    new_block = b.add_item((3, 5), TEST_M_LIMIT)
    assert new_block is not None
    assert len(new_block.items) > 0 and len(b.items) > 0
    assert len(new_block.items) <= TEST_M_LIMIT and len(b.items) <= TEST_M_LIMIT
    assert max(new_block.items) < min(b.items)
    assert sorted(new_block.items + b.items) == [(3, i) for i in range(6)]


def test_pull_drains_inserted_values_in_order():
    import random
    rng = random.Random(0)
    for m_limit in (1, 2, 3, 5, 8):
        for _ in range(300):
            # small value range -> lots of repeated distances; the index makes each item unique
            values = [(rng.randint(0, 10), i) for i in range(rng.randint(0, 40))]
            bh = BlockHeap(m_limit, (float('inf'),))
            for v in values:
                bh.insert(v)
            assert all(len(b.items) <= m_limit for b in bh.blocks)
            assert len(bh.b_block.items) <= m_limit

            expected = sorted(values)
            while expected:
                batch = _pull_items(bh)
                assert sorted(batch) == expected[:m_limit], (m_limit, values, batch, expected[:m_limit])
                expected = expected[m_limit:]
            assert _pull_items(bh) == []


# ---------------------------------------------------------------------------
# batch_prepend tests
# ---------------------------------------------------------------------------

def test_batch_prepend_small_batch_is_one_block():
    bh = BlockHeap(TEST_M_LIMIT, TEST_BOUND)
    bh.batch_prepend([3, 1, 2])
    assert len(bh.prepend_blocks) == 1
    assert sorted(bh.prepend_blocks[0]) == [1, 2, 3]
    assert sorted(_pull_items(bh)) == [1, 2, 3]


def test_batch_prepend_large_batch_split_into_ordered_half_blocks():
    # m_limit = 4: a batch of 10 is split into blocks of at most ceil(4 / 2) = 2,
    # each block entirely below the next
    bh = BlockHeap(4, TEST_BOUND)
    values = [9, 2, 7, 0, 5, 3, 8, 1, 6, 4]
    bh.batch_prepend(values)
    blocks = list(bh.prepend_blocks)
    assert all(1 <= len(block) <= 2 for block in blocks)
    for lower, upper in zip(blocks, blocks[1:]):
        assert max(lower) < min(upper)
    assert sorted(x for block in blocks for x in block) == sorted(values)


def test_batch_prepend_pulls_in_order():
    bh = BlockHeap(TEST_M_LIMIT, TEST_BOUND)
    bh.batch_prepend([7, 1, 3, 6, 2, 5, 4])
    assert sorted(_pull_items(bh)) == [1, 2, 3, 4, 5]
    assert sorted(_pull_items(bh)) == [6, 7]
    assert _pull_items(bh) == []


def test_batch_prepend_goes_in_front_of_earlier_batches():
    bh = BlockHeap(TEST_M_LIMIT, TEST_BOUND)
    bh.batch_prepend([8, 9])
    bh.batch_prepend([3, 4])      # all smaller than 8, 9 -> in front
    bh.batch_prepend([1])
    assert sorted(_pull_items(bh)) == [1, 3, 4, 8, 9]


def test_batch_prepend_combined_with_blocks():
    bh = _heap_from_blocks([4, 5, 6])
    bh.batch_prepend([1, 2])
    assert sorted(_pull_items(bh)) == [1, 2, 4, 5, 6]
    assert _pull_items(bh) == []


def test_pull_checks_blocks_even_when_prepend_is_full():
    # prepend holds 5 values (a full pull's worth), but a later insert is
    # smaller than some of them, so pull must still look at the blocks
    bh = BlockHeap(TEST_M_LIMIT, TEST_BOUND)
    bh.batch_prepend([10, 11, 12, 13, 14])
    bh.insert(1)
    bh.insert(2)
    assert sorted(_pull_items(bh)) == [1, 2, 10, 11, 12]
    assert sorted(_pull_items(bh)) == [13, 14]
    assert _pull_items(bh) == []


def test_batch_prepend_empty_is_noop():
    bh = BlockHeap(TEST_M_LIMIT, TEST_BOUND)
    bh.batch_prepend([])
    assert len(bh.prepend_blocks) == 0
    assert _pull_items(bh) == []


def test_batch_prepend_rejects_values_at_or_above_bound():
    bh = BlockHeap(TEST_M_LIMIT, TEST_BOUND)
    try:
        bh.batch_prepend([1, TEST_BOUND])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for a value equal to B")


def test_random_mix_of_insert_prepend_and_pull():
    # random sequences of all three operations, checked against a sorted reference.
    # batch_prepend values are generated below everything stored, as required
    import random
    rng = random.Random(1)
    for m_limit in (1, 2, 3, 5, 8):
        for _ in range(200):
            bh = BlockHeap(m_limit, (float('inf'),))
            stored = []
            counter = 0
            for _ in range(rng.randint(0, 60)):
                op = rng.random()
                if op < 0.5:
                    counter += 1
                    value = (rng.randint(0, 50), counter)
                    bh.insert(value)
                    stored.append(value)
                elif op < 0.75:
                    floor = min(stored)[0] if stored else 0
                    batch = []
                    for _ in range(rng.randint(0, 2 * m_limit + 3)):
                        counter += 1
                        batch.append((floor - rng.randint(1, 20), counter))
                    bh.batch_prepend(batch)
                    stored.extend(batch)
                else:
                    stored.sort()
                    expected, stored = stored[:m_limit], stored[m_limit:]
                    assert sorted(_pull_items(bh)) == expected
            stored.sort()
            while stored:
                expected, stored = stored[:m_limit], stored[m_limit:]
                assert sorted(_pull_items(bh)) == expected
            assert _pull_items(bh) == []


# ---------------------------------------------------------------------------
# pull() bound tests
# the paper requires: max(pulled) < bound <= min(remaining), and bound = B
# when nothing is left
# ---------------------------------------------------------------------------

def test_pull_bound_is_b_when_structure_empty():
    bh = BlockHeap(TEST_M_LIMIT, TEST_BOUND)
    assert bh.pull() == (TEST_BOUND, [])


def test_pull_bound_is_b_when_everything_pulled():
    bh = _heap_from_blocks([1, 2], [3])
    bound, items = bh.pull()
    assert sorted(items) == [1, 2, 3]
    assert bound == TEST_BOUND


def test_pull_bound_is_smallest_remaining_in_heap_block():
    # pulls 1..5; 6 is left over in a heap block
    bh = _heap_from_blocks([2, 1], [6, 3, 5, 4])
    bound, items = bh.pull()
    assert sorted(items) == [1, 2, 3, 4, 5]
    assert bound == 6


def test_pull_bound_is_smallest_remaining_in_b_block():
    bh = _heap_from_blocks([1, 2, 3, 4, 5])
    bh.insert(40)    # above every heap bound -> B block
    bh.insert(30)
    bound, items = bh.pull()
    assert sorted(items) == [1, 2, 3, 4, 5]
    assert bound == 30


def test_pull_bound_is_smallest_remaining_in_prepend():
    bh = BlockHeap(TEST_M_LIMIT, TEST_BOUND)
    bh.batch_prepend([7, 1, 3, 6, 2, 5, 4])
    bound, items = bh.pull()
    assert sorted(items) == [1, 2, 3, 4, 5]
    assert bound == 6


def test_pull_bound_takes_smaller_of_prepend_and_blocks():
    # D0 holds 20..25; 1..6 are inserted afterwards into D1. pull returns 1..5,
    # leaving 20..25 in D0 and 6 in D1, so the bound must be 6 (from D1), not 20
    bh = BlockHeap(TEST_M_LIMIT, TEST_BOUND)
    bh.batch_prepend([20, 21, 22, 23, 24, 25])
    for v in (1, 2, 3, 4, 5, 6):
        bh.insert(v)
    bound, items = bh.pull()
    assert sorted(items) == [1, 2, 3, 4, 5]
    assert bound == 6
    # next pull: 6 and 20..23; the bound now comes from D0
    bound, items = bh.pull()
    assert sorted(items) == [6, 20, 21, 22, 23]
    assert bound == 24


def test_pull_bound_with_tuple_keys():
    # with (cost, hops, node) keys and B = (B,), the bound is a key, or (B,) at the end
    bh = BlockHeap(2, (10,))
    for key in [(1, 1, 5), (1, 1, 6), (4, 2, 3)]:
        bh.insert(key)
    bound, items = bh.pull()
    assert sorted(items) == [(1, 1, 5), (1, 1, 6)]
    assert bound == (4, 2, 3)
    bound, items = bh.pull()
    assert items == [(4, 2, 3)]
    assert bound == (10,)


def test_pull_bound_property_in_random_use():
    # max(pulled) < bound <= min(remaining) after every pull, and bound = B when empty
    import random
    rng = random.Random(3)
    big_bound = (float('inf'),)
    for m_limit in (1, 2, 3, 5, 8):
        for _ in range(200):
            bh = BlockHeap(m_limit, big_bound)
            stored = []
            counter = 0
            for _ in range(rng.randint(0, 60)):
                op = rng.random()
                if op < 0.5:
                    counter += 1
                    value = (rng.randint(0, 50), counter)
                    bh.insert(value)
                    stored.append(value)
                elif op < 0.7:
                    floor = min(stored)[0] if stored else 0
                    batch = []
                    for _ in range(rng.randint(0, 2 * m_limit + 3)):
                        counter += 1
                        batch.append((floor - rng.randint(1, 20), counter))
                    bh.batch_prepend(batch)
                    stored.extend(batch)
                else:
                    bound, items = bh.pull()
                    for x in items:
                        stored.remove(x)
                    if items:
                        assert max(items) < bound
                    if stored:
                        assert bound == min(stored)
                    else:
                        assert bound == big_bound


# ---------------------------------------------------------------------------
# is_empty tests
# ---------------------------------------------------------------------------

def test_is_empty_new_structure():
    assert BlockHeap(TEST_M_LIMIT, TEST_BOUND).is_empty()


def test_is_empty_false_with_value_in_each_part():
    # a value only in the B block
    bh = BlockHeap(TEST_M_LIMIT, TEST_BOUND)
    bh.insert(5)
    assert not bh.is_empty()

    # a value only in a heap block
    bh = _heap_from_blocks([1, 2])
    assert not bh.is_empty()

    # a value only in the prepend blocks
    bh = BlockHeap(TEST_M_LIMIT, TEST_BOUND)
    bh.batch_prepend([3])
    assert not bh.is_empty()


def test_is_empty_after_pulling_everything():
    bh = BlockHeap(2, TEST_BOUND)
    for v in (9, 4, 7, 1, 3):          # spreads over heap blocks and the B block
        bh.insert(v)
    bh.batch_prepend([0])
    while not bh.is_empty():
        assert _pull_items(bh) != []         # never reports non-empty when there's nothing left
    assert _pull_items(bh) == []


def test_is_empty_matches_contents_in_random_use():
    import random
    rng = random.Random(2)
    for m_limit in (1, 2, 3, 5):
        for _ in range(200):
            bh = BlockHeap(m_limit, (float('inf'),))
            count = 0
            counter = 0
            for _ in range(rng.randint(0, 40)):
                op = rng.random()
                if op < 0.5:
                    counter += 1
                    bh.insert((rng.randint(0, 50), counter))
                    count += 1
                elif op < 0.7:
                    batch = []
                    for _ in range(rng.randint(0, 2 * m_limit)):
                        counter += 1
                        batch.append((-counter, counter))   # always below everything stored
                    bh.batch_prepend(batch)
                    count += len(batch)
                else:
                    count -= len(_pull_items(bh))
                assert bh.is_empty() == (count == 0)


# ---------------------------------------------------------------------------
# m_limit parameter
# ---------------------------------------------------------------------------

def test_m_limit_controls_pull_size():
    bh = _heap_from_blocks([1, 2], [3, 4], [5, 6], m_limit=2)
    assert sorted(_pull_items(bh)) == [1, 2]
    assert sorted(_pull_items(bh)) == [3, 4]
    assert sorted(_pull_items(bh)) == [5, 6]
    assert _pull_items(bh) == []


def test_heaps_with_different_limits_are_independent():
    small, large = BlockHeap(2, TEST_BOUND), BlockHeap(4, TEST_BOUND)
    for v in (5, 4, 3, 2, 1):
        small.insert(v)
        large.insert(v)
    assert len(_pull_items(small)) == 2
    assert len(_pull_items(large)) == 4


def test_m_limit_must_be_positive():
    for bad in (0, -1):
        try:
            BlockHeap(bad, TEST_BOUND)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for m_limit={bad}")


def pull_n_smallest(elements, n):
    ''' 
    Returns two lists, 1 containing the n smallest elements that are found in the provided
    list elements to pull from
    n: number of smallest elements to pull
    Returns a tuple of two lists: (smallest_elements, remaining_elements)
    smallest_elements: list of the n smallest elements
    remaining_elements: list of the remaining elements

    does this in O(n) time

    Note: the two returned lists are NOT sorted -- only partitioned.
    Sorting them would cost O(n log n).
    '''
    if n <= 0:
        return [], list(elements)
    if n >= len(elements):
        return list(elements), []

    # value of the n-th smallest element (0-indexed rank n-1)
    kth = _select(list(elements), n - 1)

    # three-way partition around kth; handles duplicates of kth correctly
    smaller = [x for x in elements if x < kth]
    equal = [x for x in elements if x == kth]
    larger = [x for x in elements if x > kth]

    needed = n - len(smaller)  # how many copies of kth go into the smallest set
    return smaller + equal[:needed], equal[needed:] + larger


def _select(items, k):
    '''Return the k-th smallest (0-indexed) value in items, worst-case O(n).'''
    while True:
        if len(items) <= 5:
            return sorted(items)[k]
        pivot = _median_of_medians(items)
        lows = [x for x in items if x < pivot]
        num_pivots = sum(1 for x in items if x == pivot)
        if k < len(lows):
            items = lows
        elif k < len(lows) + num_pivots:
            return pivot
        else:
            k -= len(lows) + num_pivots
            items = [x for x in items if x > pivot]


def _median_of_medians(items):
    '''Pivot guaranteed to be within the 30th-70th percentile of items.'''
    medians = []
    for i in range(0, len(items), 5):
        group = sorted(items[i:i + 5])
        medians.append(group[len(group) // 2])
    return _select(medians, len(medians) // 2)



def test_pull_n_smallest():
    elements = [5, 3, 1, 4, 2]
    smallest, remaining = pull_n_smallest(elements, 3)
    assert sorted(smallest) == [1, 2, 3]
    assert sorted(remaining) == [4, 5]

def test_pull_n_smallest_edge_cases():
    # Test with n = 0
    elements = [5, 3, 1, 4, 2]
    smallest, remaining = pull_n_smallest(elements, 0)
    assert smallest == []
    assert remaining == [5, 3, 1, 4, 2]

    # Test with n >= len(elements)
    smallest, remaining = pull_n_smallest(elements, 5)
    assert smallest == [5, 3, 1, 4, 2]
    assert remaining == []

    # Test with n > len(elements)
    smallest, remaining = pull_n_smallest(elements, 10)
    assert smallest == [5, 3, 1, 4, 2]
    assert remaining == []

def test_pull_n_smallest_random_order():
    elements = [10, 7, 8, 3, 2, 5, 1, 4, 6, 9]
    smallest, remaining = pull_n_smallest(elements, 5)
    assert sorted(smallest) == [1, 2, 3, 4, 5]
    assert sorted(remaining) == [6, 7, 8, 9, 10]


if __name__ == "__main__":

    test_block_heap_size_1()
    test_block_heap_size_2()
    test_block_heap_split_1()
    test_block_heap_insert_above_all_bounds_goes_to_b_block()
    test_block_explicit_bound()
    test_block_default_bound_is_max()
    test_blocks_do_not_share_items_or_ids()
    test_starts_with_single_empty_b_block()
    test_insert_into_empty_structure_goes_to_b_block()
    test_insert_at_or_above_bound_rejected()
    test_b_block_splits_and_keeps_bound()
    test_b_block_survives_being_emptied()
    test_tuple_items_with_tuple_bound()
    test_pull_empty_heap()
    test_pull_single_full_block()
    test_pull_fewer_than_m_items_total()
    test_pull_takes_whole_block_then_part_of_next()
    test_pull_partial_block_keeps_leftovers()
    test_pull_takes_from_heap_blocks_then_b_block()
    test_pull_after_insert_smaller_than_leftovers()
    test_block_split_with_duplicates()
    test_pull_drains_inserted_values_in_order()
    test_batch_prepend_small_batch_is_one_block()
    test_batch_prepend_large_batch_split_into_ordered_half_blocks()
    test_batch_prepend_pulls_in_order()
    test_batch_prepend_goes_in_front_of_earlier_batches()
    test_batch_prepend_combined_with_blocks()
    test_pull_checks_blocks_even_when_prepend_is_full()
    test_batch_prepend_empty_is_noop()
    test_batch_prepend_rejects_values_at_or_above_bound()
    test_random_mix_of_insert_prepend_and_pull()
    test_pull_bound_is_b_when_structure_empty()
    test_pull_bound_is_b_when_everything_pulled()
    test_pull_bound_is_smallest_remaining_in_heap_block()
    test_pull_bound_is_smallest_remaining_in_b_block()
    test_pull_bound_is_smallest_remaining_in_prepend()
    test_pull_bound_takes_smaller_of_prepend_and_blocks()
    test_pull_bound_with_tuple_keys()
    test_pull_bound_property_in_random_use()
    test_is_empty_new_structure()
    test_is_empty_false_with_value_in_each_part()
    test_is_empty_after_pulling_everything()
    test_is_empty_matches_contents_in_random_use()
    test_m_limit_controls_pull_size()
    test_heaps_with_different_limits_are_independent()
    test_m_limit_must_be_positive()
    test_pull_n_smallest()
    test_pull_n_smallest_edge_cases()
    test_pull_n_smallest_random_order()

    print("All tests passed")
