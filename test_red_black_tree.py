import random
import unittest

from red_black_tree import BLACK, RED, RedBlackTree


def verify_rb_invariants(tree):
    """Check all five red-black properties. Returns black-height or raises AssertionError."""
    nil = tree._nil
    root = tree._root

    if root is nil:
        return 0

    assert root.color == BLACK, "Root must be black"
    assert root.parent is nil, "Root's parent must be nil"

    def verify(node):
        if node is nil:
            assert node.color == BLACK, "Nil sentinel must be black"
            return 1

        if node.color == RED:
            assert node.left.color == BLACK, \
                f"Red node ({node.key},{node.value}) has red left child"
            assert node.right.color == BLACK, \
                f"Red node ({node.key},{node.value}) has red right child"

        if node.left is not nil:
            assert node.left.parent is node, \
                f"Left child of ({node.key},{node.value}) has broken parent pointer"
            assert (node.left.value, node.left.key) < (node.value, node.key), \
                f"BST violation: left child ({node.left.key},{node.left.value}) >= parent ({node.key},{node.value})"

        if node.right is not nil:
            assert node.right.parent is node, \
                f"Right child of ({node.key},{node.value}) has broken parent pointer"
            assert (node.right.value, node.right.key) >= (node.value, node.key), \
                f"BST violation: right child ({node.right.key},{node.right.value}) < parent ({node.key},{node.value})"

        left_bh = verify(node.left)
        right_bh = verify(node.right)
        assert left_bh == right_bh, \
            f"Black height mismatch at ({node.key},{node.value}): left={left_bh} right={right_bh}"
        return left_bh + (1 if node.color == BLACK else 0)

    return verify(root)


# ---------------------------------------------------------------------------
# Basics
# ---------------------------------------------------------------------------

class TestBasics(unittest.TestCase):

    def setUp(self):
        self.tree = RedBlackTree()

    def test_empty_tree_state(self):
        self.assertEqual(len(self.tree), 0)
        self.assertFalse(bool(self.tree))
        self.assertIsNone(self.tree.minimum())
        self.assertIsNone(self.tree.maximum())
        self.assertIsNone(self.tree.find_bound(0))
        self.assertEqual(list(self.tree), [])

    def test_insert_single(self):
        self.tree.insert('a', 10)
        self.assertEqual(len(self.tree), 1)
        self.assertTrue(bool(self.tree))
        verify_rb_invariants(self.tree)

    def test_insert_multiple(self):
        for i, v in enumerate([5, 3, 7, 1, 4, 6, 8]):
            self.tree.insert(f'k{i}', v)
        self.assertEqual(len(self.tree), 7)
        verify_rb_invariants(self.tree)

    def test_inorder_gives_sorted_values(self):
        values = [5, 3, 7, 1, 4, 6, 8]
        for i, v in enumerate(values):
            self.tree.insert(f'k{i}', v)
        result = [n.value for n in self.tree]
        self.assertEqual(result, sorted(values))

    def test_search_found(self):
        self.tree.insert('x', 42)
        node = self.tree.search('x', 42)
        self.assertIsNotNone(node)
        self.assertEqual(node.key, 'x')
        self.assertEqual(node.value, 42)

    def test_search_wrong_key(self):
        self.tree.insert('x', 42)
        self.assertIsNone(self.tree.search('y', 42))

    def test_search_wrong_value(self):
        self.tree.insert('x', 42)
        self.assertIsNone(self.tree.search('x', 99))

    def test_minimum_maximum(self):
        for v in [5, 3, 7, 1, 4, 6, 8]:
            self.tree.insert(str(v), v)
        self.assertEqual(self.tree.minimum().value, 1)
        self.assertEqual(self.tree.maximum().value, 8)

    def test_minimum_maximum_single(self):
        self.tree.insert('a', 7)
        self.assertEqual(self.tree.minimum().value, 7)
        self.assertEqual(self.tree.maximum().value, 7)

    def test_size_tracks_inserts(self):
        for i in range(10):
            self.tree.insert(str(i), i)
        self.assertEqual(len(self.tree), 10)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class TestDelete(unittest.TestCase):

    def setUp(self):
        self.tree = RedBlackTree()

    def test_delete_only_element(self):
        self.tree.insert('a', 10)
        self.assertTrue(self.tree.delete('a', 10))
        self.assertEqual(len(self.tree), 0)
        self.assertFalse(bool(self.tree))
        verify_rb_invariants(self.tree)

    def test_delete_returns_false_wrong_key(self):
        self.tree.insert('a', 10)
        self.assertFalse(self.tree.delete('b', 10))
        self.assertEqual(len(self.tree), 1)

    def test_delete_returns_false_wrong_value(self):
        self.tree.insert('a', 10)
        self.assertFalse(self.tree.delete('a', 99))
        self.assertEqual(len(self.tree), 1)

    def test_delete_returns_false_empty(self):
        self.assertFalse(self.tree.delete('a', 10))

    def test_delete_leaf(self):
        for v in [5, 3, 7]:
            self.tree.insert(str(v), v)
        self.tree.delete('3', 3)
        self.assertEqual(len(self.tree), 2)
        self.assertIsNone(self.tree.search('3', 3))
        verify_rb_invariants(self.tree)

    def test_delete_internal_node(self):
        for v in [5, 3, 7, 1, 4, 6, 8]:
            self.tree.insert(str(v), v)
        self.tree.delete('5', 5)
        self.assertEqual(len(self.tree), 6)
        self.assertIsNone(self.tree.search('5', 5))
        verify_rb_invariants(self.tree)

    def test_delete_root(self):
        self.tree.insert('r', 5)
        self.tree.delete('r', 5)
        self.assertEqual(len(self.tree), 0)
        verify_rb_invariants(self.tree)

    def test_delete_all_elements(self):
        values = [5, 3, 7, 1, 4, 6, 8]
        for v in values:
            self.tree.insert(str(v), v)
        for v in values:
            self.tree.delete(str(v), v)
            verify_rb_invariants(self.tree)
        self.assertEqual(len(self.tree), 0)

    def test_delete_maintains_sorted_order(self):
        values = [5, 3, 7, 1, 4, 6, 8]
        for v in values:
            self.tree.insert(str(v), v)
        self.tree.delete('4', 4)
        result = [n.value for n in self.tree]
        self.assertEqual(result, sorted(v for v in values if v != 4))

    def test_size_tracks_deletes(self):
        for i in range(10):
            self.tree.insert(str(i), i)
        for i in range(5):
            self.tree.delete(str(i), i)
        self.assertEqual(len(self.tree), 5)


# ---------------------------------------------------------------------------
# find_bound
# ---------------------------------------------------------------------------

class TestFindBound(unittest.TestCase):

    def setUp(self):
        self.tree = RedBlackTree()
        for v in [10, 20, 30, 40, 50]:
            self.tree.insert(str(v), v)

    def test_exact_match(self):
        self.assertEqual(self.tree.find_bound(30).value, 30)

    def test_between_elements(self):
        self.assertEqual(self.tree.find_bound(25).value, 30)

    def test_below_minimum(self):
        self.assertEqual(self.tree.find_bound(5).value, 10)

    def test_at_minimum(self):
        self.assertEqual(self.tree.find_bound(10).value, 10)

    def test_at_maximum(self):
        self.assertEqual(self.tree.find_bound(50).value, 50)

    def test_above_maximum_returns_none(self):
        self.assertIsNone(self.tree.find_bound(51))

    def test_empty_tree_returns_none(self):
        self.assertIsNone(RedBlackTree().find_bound(0))

    def test_single_element_match(self):
        tree = RedBlackTree()
        tree.insert('a', 5)
        self.assertEqual(tree.find_bound(5).value, 5)
        self.assertEqual(tree.find_bound(4).value, 5)
        self.assertIsNone(tree.find_bound(6))

    def test_returns_smallest_qualifying(self):
        # 25 is between 20 and 30 — must return 30, not 40
        node = self.tree.find_bound(25)
        self.assertEqual(node.value, 30)

    def test_find_bound_after_delete(self):
        self.tree.delete('30', 30)
        self.assertEqual(self.tree.find_bound(25).value, 40)
        self.assertEqual(self.tree.find_bound(30).value, 40)

    def test_find_bound_duplicate_values(self):
        tree = RedBlackTree()
        tree.insert('a', 10)
        tree.insert('b', 10)
        tree.insert('c', 20)
        node = tree.find_bound(10)
        self.assertIsNotNone(node)
        self.assertEqual(node.value, 10)


# ---------------------------------------------------------------------------
# Duplicate values
# ---------------------------------------------------------------------------

class TestDuplicateValues(unittest.TestCase):

    def setUp(self):
        self.tree = RedBlackTree()

    def test_insert_same_value_different_keys(self):
        self.tree.insert('a', 5)
        self.tree.insert('b', 5)
        self.tree.insert('c', 5)
        self.assertEqual(len(self.tree), 3)
        verify_rb_invariants(self.tree)

    def test_all_values_present_after_duplicate_insert(self):
        for k in ['c', 'a', 'b']:
            self.tree.insert(k, 5)
        keys = {n.key for n in self.tree}
        self.assertEqual(keys, {'a', 'b', 'c'})

    def test_delete_one_of_duplicates(self):
        self.tree.insert('a', 5)
        self.tree.insert('b', 5)
        self.tree.delete('a', 5)
        self.assertEqual(len(self.tree), 1)
        self.assertIsNone(self.tree.search('a', 5))
        self.assertIsNotNone(self.tree.search('b', 5))
        verify_rb_invariants(self.tree)

    def test_sorted_order_with_duplicate_values(self):
        self.tree.insert('b', 5)
        self.tree.insert('a', 5)
        self.tree.insert('c', 10)
        values = [n.value for n in self.tree]
        self.assertEqual(values, sorted(values))

    def test_find_bound_with_all_same_values(self):
        for k in ['a', 'b', 'c']:
            self.tree.insert(k, 5)
        self.assertEqual(self.tree.find_bound(5).value, 5)
        self.assertEqual(self.tree.find_bound(4).value, 5)
        self.assertIsNone(self.tree.find_bound(6))


# ---------------------------------------------------------------------------
# Red-black invariants under stress
# ---------------------------------------------------------------------------

class TestRedBlackInvariants(unittest.TestCase):

    def test_sequential_ascending_insert(self):
        tree = RedBlackTree()
        for i in range(64):
            tree.insert(str(i), i)
            verify_rb_invariants(tree)

    def test_sequential_descending_insert(self):
        tree = RedBlackTree()
        for i in range(63, -1, -1):
            tree.insert(str(i), i)
            verify_rb_invariants(tree)

    def test_alternating_insert(self):
        tree = RedBlackTree()
        lo, hi = 0, 99
        while lo <= hi:
            tree.insert(str(lo), lo)
            if lo != hi:
                tree.insert(str(hi), hi)
            lo += 1
            hi -= 1
        verify_rb_invariants(tree)

    def test_random_insert(self):
        tree = RedBlackTree()
        rng = random.Random(42)
        for v in rng.sample(range(1000), 200):
            tree.insert(str(v), v)
        verify_rb_invariants(tree)

    def test_random_insert_and_delete(self):
        tree = RedBlackTree()
        rng = random.Random(7)
        inserted = []
        for _ in range(150):
            v = rng.randint(0, 100)
            k = f'k{rng.randint(0, 9999)}'
            tree.insert(k, v)
            inserted.append((k, v))
            verify_rb_invariants(tree)
        rng.shuffle(inserted)
        seen = set()
        for k, v in inserted[:75]:
            if (k, v) not in seen:
                tree.delete(k, v)
                seen.add((k, v))
                verify_rb_invariants(tree)

    def test_sorted_order_preserved_after_random_ops(self):
        tree = RedBlackTree()
        rng = random.Random(13)
        values = rng.sample(range(500), 100)
        for v in values:
            tree.insert(str(v), v)
        self.assertEqual([n.value for n in tree], sorted(values))


# ---------------------------------------------------------------------------
# Exhaustive find_bound correctness
# ---------------------------------------------------------------------------

class TestFindBoundExhaustive(unittest.TestCase):

    def test_matches_naive_implementation(self):
        rng = random.Random(99)
        values = rng.sample(range(200), 50)
        tree = RedBlackTree()
        for v in values:
            tree.insert(str(v), v)

        for target in range(210):
            node = tree.find_bound(target)
            expected = min((v for v in values if v >= target), default=None)
            if expected is None:
                self.assertIsNone(
                    node,
                    f"find_bound({target}): expected None, got {node.value if node else None}"
                )
            else:
                self.assertIsNotNone(node, f"find_bound({target}): expected {expected}, got None")
                self.assertEqual(
                    node.value, expected,
                    f"find_bound({target}): got {node.value}, expected {expected}"
                )

    def test_find_bound_after_interleaved_deletes(self):
        rng = random.Random(55)
        values = sorted(rng.sample(range(300), 80))
        tree = RedBlackTree()
        for v in values:
            tree.insert(str(v), v)

        # Delete every other value
        remaining = []
        for i, v in enumerate(values):
            if i % 2 == 0:
                tree.delete(str(v), v)
            else:
                remaining.append(v)

        for target in range(310):
            node = tree.find_bound(target)
            expected = min((v for v in remaining if v >= target), default=None)
            if expected is None:
                self.assertIsNone(node)
            else:
                self.assertIsNotNone(node)
                self.assertEqual(node.value, expected)


# ---------------------------------------------------------------------------
# update_value
# ---------------------------------------------------------------------------

class TestUpdateValue(unittest.TestCase):

    def setUp(self):
        self.tree = RedBlackTree()
        for v in [10, 20, 30, 40, 50]:
            self.tree.insert(str(v), v)

    def test_update_increases_value(self):
        self.assertTrue(self.tree.update_value('20', 35))
        verify_rb_invariants(self.tree)

    def test_node_findable_at_new_value(self):
        self.tree.update_value('20', 35)
        node = self.tree.search('20', 35)
        self.assertIsNotNone(node)
        self.assertEqual(node.value, 35)

    def test_node_gone_from_old_value(self):
        self.tree.update_value('20', 35)
        self.assertIsNone(self.tree.search('20', 20))

    def test_returns_false_key_not_found(self):
        self.assertFalse(self.tree.update_value('99', 100))

    def test_equal_value_is_noop(self):
        self.assertTrue(self.tree.update_value('20', 20))
        self.assertEqual(self.tree.search('20', 20).value, 20)
        verify_rb_invariants(self.tree)

    def test_update_decreases_value(self):
        self.assertTrue(self.tree.update_value('20', 5))
        verify_rb_invariants(self.tree)
        self.assertIsNone(self.tree.search('20', 20))
        self.assertIsNotNone(self.tree.search('20', 5))
        values = [n.value for n in self.tree]
        self.assertEqual(values, sorted(values))

    def test_update_to_new_minimum(self):
        self.tree.update_value('50', 1)
        verify_rb_invariants(self.tree)
        self.assertEqual(self.tree.minimum().value, 1)
        values = [n.value for n in self.tree]
        self.assertEqual(values, sorted(values))

    def test_size_unchanged_after_update(self):
        self.tree.update_value('20', 35)
        self.assertEqual(len(self.tree), 5)

    def test_sorted_order_maintained(self):
        self.tree.update_value('20', 35)
        values = [n.value for n in self.tree]
        self.assertEqual(values, sorted(values))
        self.assertIn(35, values)
        self.assertNotIn(20, values)

    def test_update_to_new_maximum(self):
        self.tree.update_value('10', 100)
        verify_rb_invariants(self.tree)
        self.assertEqual(self.tree.maximum().value, 100)
        values = [n.value for n in self.tree]
        self.assertEqual(values, sorted(values))

    def test_update_minimum_node(self):
        self.tree.update_value('10', 25)
        verify_rb_invariants(self.tree)
        values = [n.value for n in self.tree]
        self.assertEqual(values, sorted(values))
        self.assertNotIn(10, values)
        self.assertIn(25, values)

    def test_find_bound_reflects_update(self):
        # Before: find_bound(25) -> 30
        self.tree.update_value('30', 45)
        # After: 30 is gone, replaced by 45; find_bound(31) -> 40
        node = self.tree.find_bound(31)
        self.assertIsNotNone(node)
        self.assertEqual(node.value, 40)

    def test_multiple_updates_preserve_invariants(self):
        self.tree.update_value('10', 15)
        verify_rb_invariants(self.tree)
        self.tree.update_value('15', 25)
        verify_rb_invariants(self.tree)
        self.tree.update_value('25', 55)
        verify_rb_invariants(self.tree)
        values = [n.value for n in self.tree]
        self.assertEqual(values, sorted(values))

    def test_update_single_node_tree(self):
        tree = RedBlackTree()
        tree.insert('a', 5)
        self.assertTrue(tree.update_value('a', 99))
        verify_rb_invariants(tree)
        self.assertEqual(tree.minimum().value, 99)

    def test_random_updates_maintain_invariants(self):
        tree = RedBlackTree()
        rng = random.Random(21)
        keys = [str(i) for i in range(50)]
        for k in keys:
            tree.insert(k, rng.randint(0, 100))
        rng.shuffle(keys)
        for k in keys[:25]:
            tree.update_value(k, rng.randint(0, 200))
            verify_rb_invariants(tree)
        values = [n.value for n in tree]
        self.assertEqual(values, sorted(values))


if __name__ == '__main__':
    unittest.main()
