RED = True
BLACK = False


class Node:
    __slots__ = ('key', 'value', 'color', 'left', 'right', 'parent')

    def __init__(self, key, value, color=RED):
        self.key = key
        self.value = value
        self.color = color
        self.left = None
        self.right = None
        self.parent = None


class RedBlackTree:
    """Red-black BST ordered by (value, key). All operations are O(log n)."""

    def __init__(self):
        self._nil = Node(None, None, BLACK)
        self._nil.left = self._nil
        self._nil.right = self._nil
        self._nil.parent = self._nil
        self._root = self._nil
        self._size = 0
        self._key_map = {}  # key -> node; keys must be unique

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def insert(self, key, value):
        z = Node(key, value, RED)
        z.left = self._nil
        z.right = self._nil
        self._bst_insert(z)
        self._insert_fixup(z)
        self._size += 1
        self._key_map[key] = z

    def delete(self, key, value):
        """Remove the node matching (key, value). Returns True if found."""
        node = self._find_exact(key, value)
        if node is self._nil:
            return False
        self._delete_node(node)
        self._size -= 1
        self._key_map.pop(key, None)
        return True

    def update_value(self, key, new_value):
        """Update the value for key and reposition in the tree. Returns True if key exists."""
        node = self._key_map.get(key)
        if node is None:
            return False
        if node.value == new_value:
            return True
        self._delete_node(node)
        node.value = new_value
        node.color = RED
        node.left = self._nil
        node.right = self._nil
        node.parent = self._nil
        self._bst_insert(node)
        self._insert_fixup(node)
        return True

    def find_bound(self, value):
        """Return the node with the smallest value >= `value`, or None."""
        result = None
        current = self._root
        while current is not self._nil:
            if current.value >= value:
                result = current
                current = current.left
            else:
                current = current.right
        return result

    def search(self, key, value):
        """Return the node matching (key, value), or None."""
        node = self._find_exact(key, value)
        return None if node is self._nil else node

    def minimum(self):
        """Return the node with the smallest value, or None."""
        if self._root is self._nil:
            return None
        return self._minimum(self._root)

    def maximum(self):
        """Return the node with the largest value, or None."""
        if self._root is self._nil:
            return None
        return self._maximum(self._root)

    def __len__(self):
        return self._size

    def __bool__(self):
        return self._root is not self._nil

    def __iter__(self):
        """Yield nodes in ascending order by (value, key)."""
        yield from self._inorder(self._root)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cmp_lt(a, b):
        return (a.value, a.key) < (b.value, b.key)

    def _find_exact(self, key, value):
        current = self._root
        while current is not self._nil:
            if value < current.value or (value == current.value and key < current.key):
                current = current.left
            elif value > current.value or (value == current.value and key > current.key):
                current = current.right
            else:
                return current
        return self._nil

    def _bst_insert(self, z):
        parent = self._nil
        current = self._root
        while current is not self._nil:
            parent = current
            current = current.left if self._cmp_lt(z, current) else current.right
        z.parent = parent
        if parent is self._nil:
            self._root = z
        elif self._cmp_lt(z, parent):
            parent.left = z
        else:
            parent.right = z

    def _insert_fixup(self, z):
        while z.parent.color == RED:
            if z.parent is z.parent.parent.left:
                y = z.parent.parent.right
                if y.color == RED:
                    z.parent.color = BLACK
                    y.color = BLACK
                    z.parent.parent.color = RED
                    z = z.parent.parent
                else:
                    if z is z.parent.right:
                        z = z.parent
                        self._rotate_left(z)
                    z.parent.color = BLACK
                    z.parent.parent.color = RED
                    self._rotate_right(z.parent.parent)
            else:
                y = z.parent.parent.left
                if y.color == RED:
                    z.parent.color = BLACK
                    y.color = BLACK
                    z.parent.parent.color = RED
                    z = z.parent.parent
                else:
                    if z is z.parent.left:
                        z = z.parent
                        self._rotate_right(z)
                    z.parent.color = BLACK
                    z.parent.parent.color = RED
                    self._rotate_left(z.parent.parent)
        self._root.color = BLACK

    def _rotate_left(self, x):
        y = x.right
        x.right = y.left
        if y.left is not self._nil:
            y.left.parent = x
        y.parent = x.parent
        if x.parent is self._nil:
            self._root = y
        elif x is x.parent.left:
            x.parent.left = y
        else:
            x.parent.right = y
        y.left = x
        x.parent = y

    def _rotate_right(self, x):
        y = x.left
        x.left = y.right
        if y.right is not self._nil:
            y.right.parent = x
        y.parent = x.parent
        if x.parent is self._nil:
            self._root = y
        elif x is x.parent.right:
            x.parent.right = y
        else:
            x.parent.left = y
        y.right = x
        x.parent = y

    def _delete_node(self, z):
        y = z
        y_original_color = y.color
        if z.left is self._nil:
            x = z.right
            self._transplant(z, z.right)
        elif z.right is self._nil:
            x = z.left
            self._transplant(z, z.left)
        else:
            y = self._minimum(z.right)
            y_original_color = y.color
            x = y.right
            if y.parent is z:
                x.parent = y
            else:
                self._transplant(y, y.right)
                y.right = z.right
                y.right.parent = y
            self._transplant(z, y)
            y.left = z.left
            y.left.parent = y
            y.color = z.color
        if y_original_color == BLACK:
            self._delete_fixup(x)

    def _transplant(self, u, v):
        if u.parent is self._nil:
            self._root = v
        elif u is u.parent.left:
            u.parent.left = v
        else:
            u.parent.right = v
        v.parent = u.parent

    def _delete_fixup(self, x):
        while x is not self._root and x.color == BLACK:
            if x is x.parent.left:
                w = x.parent.right
                if w.color == RED:
                    w.color = BLACK
                    x.parent.color = RED
                    self._rotate_left(x.parent)
                    w = x.parent.right
                if w.left.color == BLACK and w.right.color == BLACK:
                    w.color = RED
                    x = x.parent
                else:
                    if w.right.color == BLACK:
                        w.left.color = BLACK
                        w.color = RED
                        self._rotate_right(w)
                        w = x.parent.right
                    w.color = x.parent.color
                    x.parent.color = BLACK
                    w.right.color = BLACK
                    self._rotate_left(x.parent)
                    x = self._root
            else:
                w = x.parent.left
                if w.color == RED:
                    w.color = BLACK
                    x.parent.color = RED
                    self._rotate_right(x.parent)
                    w = x.parent.left
                if w.right.color == BLACK and w.left.color == BLACK:
                    w.color = RED
                    x = x.parent
                else:
                    if w.left.color == BLACK:
                        w.right.color = BLACK
                        w.color = RED
                        self._rotate_left(w)
                        w = x.parent.left
                    w.color = x.parent.color
                    x.parent.color = BLACK
                    w.left.color = BLACK
                    self._rotate_right(x.parent)
                    x = self._root
        x.color = BLACK

    def _minimum(self, node):
        while node.left is not self._nil:
            node = node.left
        return node

    def _maximum(self, node):
        while node.right is not self._nil:
            node = node.right
        return node

    def _inorder(self, node):
        if node is not self._nil:
            yield from self._inorder(node.left)
            yield node
            yield from self._inorder(node.right)
