

from uuid import uuid4
from statistics import median

import networkx as nx

from heapq import heappush, heappop

from red_black_tree import RedBlackTree

M_LIMIT = 5

# create a tree of blocks

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
        # makes a smaller block with the items in the first block less than the median
        med = median(self.items)
        lt_med = []
        gte_med = []
        for i, item in enumerate(self.items):
            if item < med:
                lt_med.append(item)
            else:
                gte_med.append(item)
        self.items = gte_med
        new_block = Block(items=lt_med)
        return new_block 

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
        if self.prepend_array:
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
                        top_block.items = remaining_items
                        result.extend(smallest_items)

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
        self.num_blocks -= 1
        top_block = self.blocks[0]
        self.blocks[0] = self.blocks[-1]
        self.blocks.pop()
        self._sift_down(0)

        # remove the block from the binary search tree
        self.bin_search_tree.delete(0, top_block.bound)

        return top_block

    def peek(self):
        return self.blocks[0]

    def insert(self, value):
        # find appropriate block to insert the value, where the block's bound is less than or equal to the value
        relevant_index = self.bin_search_tree.find_bound(value).key
        # if no relevant block is found, create a new block with that bound
        if relevant_index is None:
            new_block = Block(items=[value])
            self._push_block(new_block)
            return

        # check if block is not too big > M_LIMIT, if so split it
        relevant_block = self.blocks[relevant_index]
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
    b1 = Block(items=[1, 2, 3, 4, 5])
    b2 = Block(items=[6, 7, 8, 9, 10])
    bh._push_block(b1)
    bh._push_block(b2)

    bh.insert(3)

    # print(bh)
    assert bh.pop().items == [1, 2]
    assert bh.pop().items == [3, 4, 5, 3]


def test_block_heap_pull_with_prepend_array():
    bh = BlockHeap()
    b1 = Block(items=[1, 2, 3])
    b2 = Block(items=[4, 5, 6])
    bh._push_block(b1)
    bh._push_block(b2)

    bh.insert(0)
    bh.insert(7)

    assert bh.pop().items == [0, 1, 2, 3]
    assert bh.pop().items == [4, 5, 6, 7]





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



