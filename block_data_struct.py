

from uuid import uuid4

import networkx as nx

from heapq import heappush, heappop

from red_black_tree import RedBlackTree

M_LIMIT = 5

# create a tree of blocks
#
# Items stored in the structure must be DISTINCT. Blocks rely on covering
# disjoint value ranges (no two blocks share a bound), which duplicates break.
# To store values that may repeat (e.g. equal distances), insert tuples with a
# unique tiebreaker, e.g. (distance, vertex_id). Tuples compare element-wise,
# so the rest of the code works unchanged.

class Block:
    def __init__(self, items = [], ID = uuid4()):
        self.ID = ID
        self.items = items
        self.bound = max(self.items) if self.items else None

    def add_item(self, item):
        self.items.append(item)
        num_items = len(self.items)
        if num_items is not None and num_items > M_LIMIT:
            new_block = self.split_block()
            return new_block
        else:
            return None

    def split_block(self):
        # Splits around the median in O(n): the smaller half moves to a new block,
        # the larger half stays here (so this block's bound, the max, is unchanged).
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
    # Maintains a heap of blocks, kept track by the bound on items
    def __init__(self):
        self.blocks = []
        self.num_blocks = 0
        self.bin_search_tree = RedBlackTree() # key is the index of the block in the heap, and value is the block's bound
        self.prepend_array = []

    def pull(self):
        if len(self.prepend_array) >= M_LIMIT:
            # return M items from the prepend_array
            result = self.prepend_array[:M_LIMIT]
            self.prepend_array = self.prepend_array[M_LIMIT:]
            return result
        else: # must fetch from the block heap in order to get M elements
            result = self.prepend_array[:]
            self.prepend_array = []
            # find the smallest elements in the top of the block heap
            number_of_elements_to_pull = M_LIMIT - len(result)
            while number_of_elements_to_pull > 0:
                top_block = self.pop()
                if top_block is None:
                    break

                # pull smallest items from the top block
                if number_of_elements_to_pull < len(top_block.items):
                    smallest_items, remaining_items = pull_n_smallest(top_block.items, number_of_elements_to_pull)
                    result.extend(smallest_items)
                    self.prepend_array.extend(remaining_items)
                else:
                    result.extend(top_block.items)

                number_of_elements_to_pull = M_LIMIT - len(result)

            return result


    def _push_block(self, block):
        if len(block.items) > M_LIMIT:
            raise ValueError(f"Block exceeds maximum limit of items: {M_LIMIT}")
        self.blocks.append(block)
        self.bin_search_tree.insert(self.num_blocks, block.bound)
        self._sift_up(self.num_blocks)
        self.num_blocks += 1

    def pop(self):
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
        # find appropriate block to insert the value, where the block's bound is less than or equal to the value
        bound_node = self.bin_search_tree.find_bound(value)
        # if no block has a bound >= value, create a new block with that bound
        # (_push_block adds it to both the heap and the binary search tree)
        if bound_node is None:
            new_block = Block(items=[value])
            self._push_block(new_block)
            return

        # check if block is not too big > M_LIMIT, if so split it
        relevant_block = self.blocks[bound_node.key]
        new_block = relevant_block.add_item(value) # if the block was split, this will be the new block
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
        body = f"num_blocks:{self.num_blocks},\n\nblocks:{self.blocks}\n"
        footer = f"{'='* 50}\n"
        prepend_array = f"Prepend array: {self.prepend_array}\n"
        
        string = header + body + footer + prepend_array

        return string






    

def test_block_heap_size_1():
    bh = BlockHeap()
    b1 = Block(items=[1, 2, 3])
    b2 = Block(items=[4, 5, 6])
    bh._push_block(b1)
    bh._push_block(b2)
    assert bh.pop() == b1
    assert bh.pop() == b2
    assert bh.pop() is None

def test_block_heap_size_2():
    bh = BlockHeap()
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
    bh = BlockHeap()
    b1 = Block(items=[1, 2, 4, 5, 6])
    b2 = Block(items=[7, 8, 9, 10, 11])
    bh._push_block(b1)
    bh._push_block(b2)

    bh.insert(3)  # b1 now has 6 items -> splits into its 3 smallest and 3 largest

    assert sorted(bh.pop().items) == [1, 2, 3]
    assert sorted(bh.pop().items) == [4, 5, 6]
    assert sorted(bh.pop().items) == [7, 8, 9, 10, 11]
    assert bh.pop() is None


def test_block_heap_pull_with_prepend_array():
    bh = BlockHeap()
    b1 = Block(items=[1, 2, 3])
    b2 = Block(items=[4, 5, 6])
    bh._push_block(b1)
    bh._push_block(b2)

    bh.insert(0)  # fits under b1's bound (3)
    bh.insert(7)  # larger than every bound -> goes into a new block

    assert sorted(bh.pop().items) == [0, 1, 2, 3]
    assert bh.pop().items == [4, 5, 6]
    assert bh.pop().items == [7]
    assert bh.pop() is None


# ---------------------------------------------------------------------------
# pull() tests
# pull() should return the M_LIMIT smallest items currently stored (in any
# order), remove them from the structure, and never lose or duplicate items.
# ---------------------------------------------------------------------------

def _heap_from_blocks(*item_lists):
    bh = BlockHeap()
    for items in item_lists:
        bh._push_block(Block(items=list(items)))
    return bh


def test_pull_empty_heap():
    bh = BlockHeap()
    assert bh.pull() == []


def test_pull_from_prepend_array_only():
    bh = BlockHeap()
    bh.prepend_array = [1, 2, 3, 4, 5, 6, 7]
    assert sorted(bh.pull()) == [1, 2, 3, 4, 5]
    assert sorted(bh.prepend_array) == [6, 7]
    assert sorted(bh.pull()) == [6, 7]
    assert bh.pull() == []


def test_pull_single_full_block():
    # a block with exactly M_LIMIT items should be returned whole
    bh = _heap_from_blocks([5, 3, 1, 4, 2])
    assert sorted(bh.pull()) == [1, 2, 3, 4, 5]
    assert bh.pull() == []


def test_pull_fewer_than_m_items_total():
    bh = _heap_from_blocks([2, 1], [3])
    assert sorted(bh.pull()) == [1, 2, 3]
    assert bh.pull() == []


def test_pull_takes_whole_block_then_part_of_next():
    # needs all of [1, 2, 3] plus the 2 smallest of [4, 5, 6]
    bh = _heap_from_blocks([1, 2, 3], [4, 5, 6])
    assert sorted(bh.pull()) == [1, 2, 3, 4, 5]
    assert sorted(bh.pull()) == [6]
    assert bh.pull() == []


def test_pull_leftovers_go_to_prepend_array():
    # takes [1, 2], then the 3 smallest of [6, 3, 5, 4]; 6 must be kept
    bh = _heap_from_blocks([2, 1], [6, 3, 5, 4])
    assert sorted(bh.pull()) == [1, 2, 3, 4, 5]
    assert sorted(bh.prepend_array) == [6]
    assert sorted(bh.pull()) == [6]
    assert bh.pull() == []


def test_pull_combines_prepend_array_and_blocks():
    bh = _heap_from_blocks([4, 5, 6])
    bh.prepend_array = [1, 2]
    assert sorted(bh.pull()) == [1, 2, 4, 5, 6]
    assert bh.pull() == []


def test_pull_after_insert_smaller_than_prepend_array():
    # after the first pull, [11, 12] sit in the prepend array; inserting 5
    # afterwards means 5 is now among the smallest and must come out next
    bh = _heap_from_blocks([1, 2, 3, 4], [10, 11, 12])
    assert sorted(bh.pull()) == [1, 2, 3, 4, 10]
    bh.insert(5)
    assert sorted(bh.pull()) == [5, 11, 12]
    assert bh.pull() == []


def test_block_split_with_duplicates():
    # equal distances are made distinct with a tiebreaker: (distance, id).
    # splitting must never produce an empty block or one over M_LIMIT, and
    # the two halves must not overlap.
    b = Block(items=[(3, i) for i in range(5)])
    new_block = b.add_item((3, 5))
    assert new_block is not None
    assert len(new_block.items) > 0 and len(b.items) > 0
    assert len(new_block.items) <= M_LIMIT and len(b.items) <= M_LIMIT
    assert max(new_block.items) < min(b.items)
    assert sorted(new_block.items + b.items) == [(3, i) for i in range(6)]


def test_pull_drains_inserted_values_in_order():
    import random
    rng = random.Random(0)
    for _ in range(1000):
        # small value range -> lots of repeated distances; the index makes each item unique
        values = [(rng.randint(0, 10), i) for i in range(rng.randint(0, 40))]
        bh = BlockHeap()
        for v in values:
            bh.insert(v)

        expected = sorted(values)
        while expected:
            batch = bh.pull()
            assert sorted(batch) == expected[:M_LIMIT], (values, batch, expected[:M_LIMIT])
            expected = expected[M_LIMIT:]
        assert bh.pull() == []





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

    # Test for pulling n smallest elements in O(n) time
    test_pull_n_smallest()
    test_pull_n_smallest_edge_cases()
    test_pull_n_smallest_random_order()

    # Block Heap
    test_block_heap_size_1()
    test_block_heap_size_2()
    test_block_heap_split_1()

    # Test with prepend array
    test_block_heap_pull_with_prepend_array()

    # pull()
    test_pull_empty_heap()
    test_pull_from_prepend_array_only()
    test_pull_single_full_block()
    test_pull_fewer_than_m_items_total()
    test_pull_takes_whole_block_then_part_of_next()
    test_pull_leftovers_go_to_prepend_array()
    test_pull_combines_prepend_array_and_blocks()
    test_pull_after_insert_smaller_than_prepend_array()
    test_block_split_with_duplicates()
    test_pull_drains_inserted_values_in_order()

    print("All tests passed")



