

from uuid import uuid4
from statistics import median

import networkx as nx

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



class block_heap:
    # Maintains a heap of blocks, kept track by the bound on items
    def __init__(self):
        self.blocks = []
        self.num_blocks = 0
        self.bin_search_tree = RedBlackTree() # key is the index of the block in the heap, and value is the block's bound


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
        string = header + body + footer
        return string
    

def test_block_heap_size_1():
    bh = block_heap()
    b1 = Block(items=[1, 2, 3])
    b2 = Block(items=[4, 5, 6])
    bh._push_block(b1)
    bh._push_block(b2)
    assert bh.pop() == b1
    assert bh.pop() == b2
    assert bh.pop() is None

def test_block_heap_size_2():
    bh = block_heap()
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
    bh = block_heap()
    b1 = Block(items=[1, 2, 3, 4, 5])
    b2 = Block(items=[6, 7, 8, 9, 10])
    bh._push_block(b1)
    bh._push_block(b2)

    bh.insert(3)

    print(bh)
    assert bh.pop().items == [1, 2]

if __name__ == "__main__":
    test_block_heap_size_1()
    test_block_heap_size_2()
    test_block_heap_split_1()