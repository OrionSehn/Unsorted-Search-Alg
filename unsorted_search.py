
import heapq

import math

import networkx as nx

from block_data_struct import BlockHeap, Block



class bmssp_workspace:
    def __init__(self, graph, source):
        self.graph = graph
        self.g_cost = dict()
        for node in graph.nodes:
            self.g_cost[node] = float('inf')
        self.g_cost[source] = 0
        self.source = source
        # k = floor(log^(1/3) n), t = floor(log^(2/3) n), log base 2.
        # max(1, ...) so tiny graphs (n <= 2) still get a usable k and t
        # (the small epsilon stops float error flooring exact powers down, e.g.
        # 8 ** (2/3) evaluates to 3.9999999999999996, which would give t = 3, not 4)
        log_n = math.log2(len(graph.nodes))
        self.k = max(1, math.floor(log_n ** (1/3) + 1e-9))
        self.t = max(1, math.floor(log_n ** (2/3) + 1e-9))
        self.predecessors = dict()
        # number of edges on each node's current best path (for tie-breaking)
        self.hops = {source: 0}

    # ------------------------------------------------------------------
    # Tie-breaking (Assumption 2.1 in Duan et al.)
    # Paths are totally ordered by <length, number of vertices, last vertex,
    # second-to-last vertex, ...>, so no two paths have the "same" distance.
    # A node's key is (cost, hops, node): this orders different nodes, and
    # bounds compare against keys. Node ids must be comparable (e.g. ints).
    # ------------------------------------------------------------------

    def key(self, node):
        return (self.g_cost[node], self.hops.get(node, 0), node)

    def candidate_key(self, u, v, new_cost):
        # key v would have if reached via u
        return (new_cost, self.hops.get(u, 0) + 1, v)

    def is_valid_relaxation(self, u, v, new_cost):
        '''
        True if the path to v through u is <= v's current path in the total order
        (the paper's "d[u] + w <= d[v]"). Equal only when it IS v's current path.
        '''
        current_cost = self.g_cost[v]
        if new_cost != current_cost:
            return new_cost < current_cost
        new_hops = self.hops.get(u, 0) + 1
        current_hops = self.hops.get(v, 0)
        if new_hops != current_hops:
            return new_hops < current_hops
        # same length and hop count: both paths end at v, so compare the next
        # vertex back (the predecessor)
        current_pred = self.predecessors.get(v)
        if current_pred is None:
            return False  # v's cost was given directly (e.g. a source); keep it
        return u <= current_pred

    def relax(self, u, v, new_cost):
        self.g_cost[v] = new_cost
        self.hops[v] = self.hops.get(u, 0) + 1
        self.predecessors[v] = u


def as_bound(bound_B):
    '''
    Bounds are compared against node keys (cost, hops, node). A plain number B
    becomes (B,), and (c, h, v) < (B,) exactly when c < B.
    '''
    return bound_B if isinstance(bound_B, tuple) else (bound_B,)

def bmssp(level_l, bound_B, closed_S, bmssp_ws: bmssp_workspace):
    # Base case:
    if level_l == 0:
        return base_case(bound_B, closed_S, bmssp_ws)




def find_pivots(bound_B, closed_S, bmssp_ws: bmssp_workspace) -> tuple[set, set]:
    '''
    FindPivots from Duan et al.
    Runs k rounds of Bellman-Ford style relaxation outward from closed_S, then
    returns (pivots P, encountered nodes W).
      - if W grows larger than k * |S|, every node of S is a pivot: P = S
      - otherwise P = the nodes of S that are roots of a tree with >= k vertices
        in the shortest-path forest F over W
    '''
    graph = bmssp_ws.graph
    g_cost = bmssp_ws.g_cost
    k = bmssp_ws.k
    bound = as_bound(bound_B)

    encountered_nodes_in_pivots = set(closed_S)   # W
    prev_relax_frontier = set(closed_S)           # W_{i-1}
    for i in range(1, k + 1):
        current_relax_frontier = set()            # W_i
        for node in prev_relax_frontier:
            for neighbor in graph.neighbors(node):
                new_cost = g_cost[node] + graph[node][neighbor].get('weight', 1)
                # relax the edge if the new path is <= the current one in the
                # tie-broken order ('<=' as in the paper: equal means it is the
                # same path, which keeps nodes already reached this way)
                if bmssp_ws.is_valid_relaxation(node, neighbor, new_cost):
                    bmssp_ws.relax(node, neighbor, new_cost)
                    # only nodes strictly below the bound join W
                    if bmssp_ws.key(neighbor) < bound:
                        current_relax_frontier.add(neighbor)
        encountered_nodes_in_pivots.update(current_relax_frontier)
        prev_relax_frontier = current_relax_frontier

        if len(encountered_nodes_in_pivots) > k * len(closed_S):
            return set(closed_S), encountered_nodes_in_pivots

    # F: shortest-path forest over W (tight edges only)
    forest_F = build_shortest_path_forest(encountered_nodes_in_pivots, bmssp_ws)

    # pivots are the roots (in S) of trees in F with >= k vertices
    pivot_set = find_large_tree_roots(forest_F, closed_S, k)
    return pivot_set, encountered_nodes_in_pivots


def build_shortest_path_forest(nodes_W, bmssp_ws: bmssp_workspace) -> dict:
    '''
    Builds F = {(u, v) : u, v in W, d[v] = d[u] + w(u, v)}: the edges that
    lie on each node's current best path.

    With the tie-broken order, "d[v] = d[u] + w(u, v)" means v's current path
    is exactly u's path plus the edge: same cost, one more hop, and u is v's
    predecessor. Each node then has at most one such edge, so F is a forest
    (as the paper states under Assumption 2.1).

    Returned as a {child: parent} dict. Nodes with no parent are roots.
    Assumes positive edge weights.
    '''
    graph = bmssp_ws.graph
    g_cost = bmssp_ws.g_cost
    hops = bmssp_ws.hops
    parent = {}
    for v in nodes_W:
        u = bmssp_ws.predecessors.get(v)
        if u is None or u not in nodes_W or g_cost[u] == float('inf'):
            continue  # inf + w == inf would look "tight"
        if (g_cost[v] == g_cost[u] + graph[u][v].get('weight', 1)
                and hops.get(v, 0) == hops.get(u, 0) + 1):
            parent[v] = u
    return parent


def find_large_tree_roots(forest_parent: dict, candidate_roots, k) -> set:
    '''
    Returns the candidates that are roots (have no parent) of a tree in the
    forest containing >= k vertices (the root counts).
    forest_parent: {child: parent} dict, as returned by build_shortest_path_forest
    '''
    children = {}
    for child, parent in forest_parent.items():
        children.setdefault(parent, []).append(child)

    large_roots = set()
    for root in candidate_roots:
        if root in forest_parent:
            continue  # has a parent, so it is not a root
        # count the tree's vertices with an iterative DFS
        tree_size = 0
        stack = [root]
        while stack:
            node = stack.pop()
            tree_size += 1
            stack.extend(children.get(node, []))
        if tree_size >= k:
            large_roots.add(root)
    return large_roots








def base_case(bound_B, closed_S, bmssp_ws: bmssp_workspace) -> tuple[float, set]:
    # solve the bmssp using dijkstra for the base case

    # closed_S should be singleton, raise an error if not
    if len(closed_S) != 1:
        raise ValueError("closed_S should be a singleton set")

    graph = bmssp_ws.graph
    g_cost = bmssp_ws.g_cost
    k = bmssp_ws.k
    bound = as_bound(bound_B)

    # works whether closed_S is a list or a set
    start_node = next(iter(closed_S))

    # start from the node's existing (already final) cost, not 0.
    # heap entries are node keys (cost, hops, node), so ties pop in a fixed order
    settled = set()
    bin_heap = [bmssp_ws.key(start_node)]

    # Dijkstra from start_node, stopping once k + 1 nodes have been settled
    while bin_heap and len(settled) < k + 1:
        entry = heapq.heappop(bin_heap)
        current_node = entry[2]
        # skip nodes already settled, and stale entries superseded by a better path
        if current_node in settled or entry != bmssp_ws.key(current_node):
            continue
        settled.add(current_node)

        for neighbor in graph.neighbors(current_node):
            new_cost = g_cost[current_node] + graph[current_node][neighbor].get('weight', 1)
            # relax only if the new path is <= the current one in the tie-broken
            # order ('<=' as in the paper) and its key is strictly below the bound
            if (bmssp_ws.is_valid_relaxation(current_node, neighbor, new_cost)
                    and bmssp_ws.candidate_key(current_node, neighbor, new_cost) < bound):
                bmssp_ws.relax(current_node, neighbor, new_cost)
                heapq.heappush(bin_heap, bmssp_ws.key(neighbor))

    if len(settled) <= k:
        return bound_B, settled

    # found more than k nodes: the new bound B' is the largest settled key,
    # and only nodes strictly below it are returned. Keys are unique, so
    # exactly one settled node (the largest) is left out.
    new_bound = max(bmssp_ws.key(node) for node in settled)
    return new_bound, {node for node in settled if bmssp_ws.key(node) < new_bound}

# ---------------------------------------------------------------------------
# base_case tests
# Expected behaviour (BaseCase from Duan et al.):
#   - closed_S = [x], where g_cost[x] is already final
#   - run Dijkstra from x, starting at g_cost[x]; only set a node's cost if it
#     improves on g_cost and is strictly below bound_B
#   - stop once k + 1 nodes have been settled (x counts)
#   - if <= k nodes found: return (bound_B, found)
#     else: B' = largest cost found, return (B', {found nodes with cost < B'})
# k is set explicitly in each test so results don't depend on log(n).
# ---------------------------------------------------------------------------

def _path_graph():
    # 0 --1-- 1 --2-- 2 --3-- 3      true costs from 0: 0, 1, 3, 6
    G = nx.Graph()
    G.add_edge(0, 1, weight=1)
    G.add_edge(1, 2, weight=2)
    G.add_edge(2, 3, weight=3)
    return G


def _workspace(G, source, k):
    ws = bmssp_workspace(G, source)
    ws.k = k
    return ws


def _settle(ws, node, cost, hops, pred=None):
    # record a path found by an earlier search: its cost, hop count and predecessor
    ws.g_cost[node] = cost
    ws.hops[node] = hops
    if pred is not None:
        ws.predecessors[node] = pred


def _settle_path_graph(ws, nodes=(0, 1, 2, 3)):
    # true shortest-path state on _path_graph() from source 0
    state = {0: (0, 0, None), 1: (1, 1, 0), 2: (3, 2, 1), 3: (6, 3, 2)}
    for node in nodes:
        _settle(ws, node, *state[node])


def test_base_case_finds_all_costs_within_bound():
    ws = _workspace(_path_graph(), 0, k=10)
    bound, found = base_case(10, [0], ws)
    assert bound == 10
    assert found == {0, 1, 2, 3}
    assert ws.g_cost == {0: 0, 1: 1, 2: 3, 3: 6}


def test_base_case_bound_is_strict():
    # node 3 costs exactly 6, so with B = 6 it must not be included or updated
    ws = _workspace(_path_graph(), 0, k=10)
    bound, found = base_case(6, [0], ws)
    assert bound == 6
    assert found == {0, 1, 2}
    assert ws.g_cost[3] == float('inf')


def test_base_case_unreachable_nodes_untouched():
    G = _path_graph()
    G.add_node(99)  # isolated
    ws = _workspace(G, 0, k=10)
    bound, found = base_case(10, [0], ws)
    assert 99 not in found
    assert ws.g_cost[99] == float('inf')


def test_base_case_picks_cheaper_route():
    # 0->2 directly costs 5, but 0->1->3->2 costs 1+1+1 = 3
    G = nx.Graph()
    G.add_edge(0, 1, weight=1)
    G.add_edge(1, 3, weight=1)
    G.add_edge(3, 2, weight=1)
    G.add_edge(0, 2, weight=5)
    ws = _workspace(G, 0, k=10)
    bound, found = base_case(10, [0], ws)
    assert found == {0, 1, 2, 3}
    assert ws.g_cost == {0: 0, 1: 1, 2: 3, 3: 2}


def test_base_case_starts_from_existing_cost():
    # x = 1 was already settled at cost 1 by an earlier search; costs must
    # build on g_cost[1], not restart from 0
    ws = _workspace(_path_graph(), 0, k=10)
    ws.g_cost[0] = 0
    ws.g_cost[1] = 1
    bound, found = base_case(10, [1], ws)
    assert ws.g_cost[2] == 3
    assert ws.g_cost[3] == 6
    # node 0 is reachable from 1 (cost 2) but already has a better cost (0),
    # so it is not re-explored or returned
    assert ws.g_cost[0] == 0
    assert found == {1, 2, 3}


def test_base_case_does_not_overwrite_better_costs():
    # an earlier search already found node 2 at cost 2 (better than 3 via node 1)
    ws = _workspace(_path_graph(), 0, k=10)
    ws.g_cost[1] = 1
    ws.g_cost[2] = 2
    bound, found = base_case(10, [1], ws)
    assert ws.g_cost[2] == 2
    assert 2 not in found


def test_base_case_directed_edges():
    # in a DiGraph, edges are only followed forwards
    G = nx.DiGraph()
    G.add_edge(0, 1, weight=1)
    G.add_edge(2, 1, weight=1)  # 2 is not reachable from 0
    ws = _workspace(G, 0, k=10)
    bound, found = base_case(10, [0], ws)
    assert found == {0, 1}
    assert ws.g_cost[2] == float('inf')


def test_base_case_stops_after_k_plus_one_nodes():
    # k = 2: settles 0, 1, 2 (k + 1 nodes) then stops.
    # B' = largest settled key = node 2's (cost 3, 2 hops, node 2);
    # returned set is nodes with key < B'
    ws = _workspace(_path_graph(), 0, k=2)
    bound, found = base_case(100, [0], ws)
    assert bound == (3, 2, 2)
    assert found == {0, 1}
    assert ws.g_cost[1] == 1 and ws.g_cost[2] == 3


def test_base_case_exactly_k_nodes_returns_original_bound():
    # only 3 nodes reachable below B and k = 3 -> no truncation
    ws = _workspace(_path_graph(), 0, k=3)
    bound, found = base_case(5, [0], ws)
    assert bound == 5
    assert found == {0, 1, 2}


def test_base_case_ties_broken_by_node_id():
    # star: 1, 2, 3 all at cost 1 (1 hop) from 0, so they differ only by node id.
    # k = 2 settles 0, 1, 2 (smallest keys first); B' = node 2's key (1, 1, 2),
    # and only node 2 is left out. Without tie-breaking, B' would be just 1
    # and nodes 1 and 2 would both be dropped
    G = nx.Graph()
    for leaf in (1, 2, 3):
        G.add_edge(0, leaf, weight=1)
    ws = _workspace(G, 0, k=2)
    bound, found = base_case(100, [0], ws)
    assert bound == (1, 1, 2)
    assert found == {0, 1}


def test_base_case_numeric_bound_vs_tuple_bound():
    # a tuple bound from an earlier call cuts between nodes that tie on cost:
    # B = (1, 1, 2) admits node 1 (key (1, 1, 1)) but not nodes 2 or 3
    G = nx.Graph()
    for leaf in (1, 2, 3):
        G.add_edge(0, leaf, weight=1)
    ws = _workspace(G, 0, k=10)
    bound, found = base_case((1, 1, 2), [0], ws)
    assert bound == (1, 1, 2)
    assert found == {0, 1}
    assert ws.g_cost[2] == float('inf') and ws.g_cost[3] == float('inf')


def test_base_case_equal_paths_pick_smaller_predecessor():
    # diamond: 0-1-3 and 0-2-3 both cost 2 with 2 hops; the tie goes to the
    # path through the smaller predecessor, node 1
    G = nx.Graph()
    for u, v in [(0, 1), (0, 2), (1, 3), (2, 3)]:
        G.add_edge(u, v, weight=1)
    ws = _workspace(G, 0, k=10)
    base_case(10, [0], ws)
    assert ws.g_cost[3] == 2
    assert ws.predecessors[3] == 1
    assert ws.hops[3] == 2


def test_base_case_rejects_non_singleton():
    ws = _workspace(_path_graph(), 0, k=10)
    try:
        base_case(10, [0, 1], ws)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for non-singleton closed_S")


# ---------------------------------------------------------------------------
# find_large_tree_roots tests (hand-built forests, {child: parent})
# ---------------------------------------------------------------------------

def test_large_roots_tree_of_exactly_k_is_included():
    # 0 -> 1 -> 2 : 3 vertices, k = 3
    forest = {1: 0, 2: 1}
    assert find_large_tree_roots(forest, [0], 3) == {0}


def test_large_roots_tree_smaller_than_k_is_excluded():
    forest = {1: 0, 2: 1}
    assert find_large_tree_roots(forest, [0], 4) == set()


def test_large_roots_counts_branching_trees():
    #      0
    #    /   \
    #   1     2
    #  / \
    # 3   4      -> 5 vertices
    forest = {1: 0, 2: 0, 3: 1, 4: 1}
    assert find_large_tree_roots(forest, [0], 5) == {0}
    assert find_large_tree_roots(forest, [0], 6) == set()


def test_large_roots_only_large_trees_returned():
    # tree at 0 has 3 vertices, tree at 10 has 1, tree at 20 has 2
    forest = {1: 0, 2: 0, 21: 20}
    assert find_large_tree_roots(forest, [0, 10, 20], 2) == {0, 20}
    assert find_large_tree_roots(forest, [0, 10, 20], 3) == {0}


def test_large_roots_non_root_candidate_excluded():
    # 1 is a candidate but has a parent, so it is not a root
    forest = {1: 0, 2: 1, 3: 2}
    assert find_large_tree_roots(forest, [0, 1], 2) == {0}


def test_large_roots_single_vertex_tree():
    assert find_large_tree_roots({}, [7], 1) == {7}
    assert find_large_tree_roots({}, [7], 2) == set()


# ---------------------------------------------------------------------------
# build_shortest_path_forest tests
# ---------------------------------------------------------------------------

def test_forest_path_graph():
    ws = _workspace(_path_graph(), 0, k=10)
    _settle_path_graph(ws)
    assert build_shortest_path_forest({0, 1, 2, 3}, ws) == {1: 0, 2: 1, 3: 2}


def test_forest_excludes_non_tight_edges():
    # 0-1 (1), 1-2 (1), 0-2 (5): edge 0-2 is not on a shortest path
    G = nx.Graph()
    G.add_edge(0, 1, weight=1)
    G.add_edge(1, 2, weight=1)
    G.add_edge(0, 2, weight=5)
    ws = _workspace(G, 0, k=10)
    _settle(ws, 1, 1, 1, pred=0)
    _settle(ws, 2, 2, 2, pred=1)
    assert build_shortest_path_forest({0, 1, 2}, ws) == {1: 0, 2: 1}


def test_forest_excludes_stale_predecessor():
    # 2's predecessor is 1, but 1's cost has since improved, so 0->...->1->2
    # is no longer 2's current path through 1: the edge is not tight
    ws = _workspace(_path_graph(), 0, k=10)
    _settle_path_graph(ws, nodes=(0, 1, 2))
    ws.g_cost[1] = 0.5  # (this also makes edge 0->1 non-tight, but we only check 1->2)
    assert 2 not in build_shortest_path_forest({0, 1, 2}, ws)


def test_forest_excludes_nodes_outside_W():
    ws = _workspace(_path_graph(), 0, k=10)
    _settle_path_graph(ws)
    assert build_shortest_path_forest({0, 1, 2}, ws) == {1: 0, 2: 1}


def test_forest_one_parent_per_node_on_ties():
    # two equal-length shortest paths into 3: 0-1-3 and 0-2-3 (both cost 2,
    # 2 hops). The tie-break picked predecessor 1, so only edge 1->3 is in F
    G = nx.Graph()
    for u, v in [(0, 1), (0, 2), (1, 3), (2, 3)]:
        G.add_edge(u, v, weight=1)
    ws = _workspace(G, 0, k=10)
    _settle(ws, 1, 1, 1, pred=0)
    _settle(ws, 2, 1, 1, pred=0)
    _settle(ws, 3, 2, 2, pred=1)
    assert build_shortest_path_forest({0, 1, 2, 3}, ws) == {1: 0, 2: 0, 3: 1}


# ---------------------------------------------------------------------------
# find_pivots tests
# ---------------------------------------------------------------------------

def test_find_pivots_early_exit_when_W_too_large():
    # S = {0}, k = 2: after 2 rounds W = {0, 1, 2}, and 3 > k * |S| = 2
    ws = _workspace(_path_graph(), 0, k=2)
    pivots, W = find_pivots(100, [0], ws)
    assert pivots == {0}
    assert W == {0, 1, 2}
    assert ws.g_cost[1] == 1 and ws.g_cost[2] == 3


def test_find_pivots_only_large_trees_are_pivots():
    # S = {0, 10}; 0 reaches 1, 2 (tree of 3), 10 is isolated (tree of 1).
    # k = 2: W = {0, 1, 2, 10}, 4 <= k * |S| = 4, so no early exit
    G = nx.Graph()
    G.add_edge(0, 1, weight=1)
    G.add_edge(1, 2, weight=1)
    G.add_node(10)
    ws = _workspace(G, 0, k=2)
    ws.g_cost[10] = 5  # 10 already settled by an earlier search
    pivots, W = find_pivots(100, [0, 10], ws)
    assert W == {0, 1, 2, 10}
    assert pivots == {0}


def test_find_pivots_bound_limits_W():
    # same graph, B = 2: node 2 costs exactly 2, so it gets a cost but not a place in W
    G = nx.Graph()
    G.add_edge(0, 1, weight=1)
    G.add_edge(1, 2, weight=1)
    G.add_node(10)
    ws = _workspace(G, 0, k=2)
    ws.g_cost[10] = 5
    pivots, W = find_pivots(2, [0, 10], ws)
    assert W == {0, 1, 10}
    assert ws.g_cost[2] == 2
    assert pivots == {0}  # tree 0 -> 1 has 2 vertices >= k


def test_find_pivots_source_node_inside_another_tree_is_not_pivot():
    # S = {0, 1} on the path graph; 1 lies on 0's shortest-path tree, so only 0 is a root.
    # k = 3: W = {0, 1, 2, 3}, 4 <= 3 * 2, tree at 0 has 4 vertices
    ws = _workspace(_path_graph(), 0, k=3)
    _settle(ws, 1, 1, 1, pred=0)  # 1 was reached from 0 by an earlier search
    pivots, W = find_pivots(100, [0, 1], ws)
    assert W == {0, 1, 2, 3}
    assert pivots == {0}


def test_find_pivots_equal_paths_pick_smaller_predecessor():
    # diamond: 3 is reached in round 2 from both 1 and 2 at cost 2, 2 hops.
    # Whichever order the frontier is visited in, the predecessor must be 1
    G = nx.Graph()
    for u, v in [(0, 1), (0, 2), (1, 3), (2, 3)]:
        G.add_edge(u, v, weight=1)
    ws = _workspace(G, 0, k=4)
    pivots, W = find_pivots(100, [0], ws)
    assert W == {0, 1, 2, 3}
    assert ws.predecessors[3] == 1
    forest = build_shortest_path_forest(W, ws)
    assert forest == {1: 0, 2: 0, 3: 1}
    assert pivots == {0}  # tree has 4 vertices >= k


def test_workspace_k_t_use_log2():
    # n = 256: log2 = 8 -> k = floor(8^(1/3)) = 2, t = floor(8^(2/3)) = 4
    # (natural log would give log = 5.55 -> k = 1, t = 3)
    G = nx.path_graph(256)
    ws = bmssp_workspace(G, 0)
    assert ws.k == 2
    assert ws.t == 4


def test_workspace_k_t_at_least_1_on_tiny_graphs():
    G = nx.Graph()
    G.add_node(0)
    ws = bmssp_workspace(G, 0)
    assert ws.k == 1 and ws.t == 1


def test_find_pivots_improves_costs():
    # round 1 reaches 2 via the direct edge (cost 5); round 2 must improve it
    # to 2 via node 1. k = 3 so |W| = 3 <= k * |S| and there is no early exit
    # after round 1 (with k = 2 it would exit early, leaving g_cost[2] = 5)
    G = nx.Graph()
    G.add_edge(0, 1, weight=1)
    G.add_edge(1, 2, weight=1)
    G.add_edge(0, 2, weight=5)
    ws = _workspace(G, 0, k=3)
    pivots, W = find_pivots(100, [0], ws)
    assert ws.g_cost == {0: 0, 1: 1, 2: 2}
    assert W == {0, 1, 2}
    assert pivots == {0}  # tree 0 -> 1 -> 2 has 3 vertices >= k


if __name__ == "__main__":

    # Base case tests
    test_base_case_finds_all_costs_within_bound()
    test_base_case_bound_is_strict()
    test_base_case_unreachable_nodes_untouched()
    test_base_case_picks_cheaper_route()
    test_base_case_starts_from_existing_cost()
    test_base_case_does_not_overwrite_better_costs()
    test_base_case_directed_edges()
    test_base_case_stops_after_k_plus_one_nodes()
    test_base_case_exactly_k_nodes_returns_original_bound()
    test_base_case_ties_broken_by_node_id()
    test_base_case_numeric_bound_vs_tuple_bound()
    test_base_case_equal_paths_pick_smaller_predecessor()
    test_base_case_rejects_non_singleton()

    # find_large_tree_roots
    test_large_roots_tree_of_exactly_k_is_included()
    test_large_roots_tree_smaller_than_k_is_excluded()
    test_large_roots_counts_branching_trees()
    test_large_roots_only_large_trees_returned()
    test_large_roots_non_root_candidate_excluded()
    test_large_roots_single_vertex_tree()

    # build_shortest_path_forest
    test_forest_path_graph()
    test_forest_excludes_non_tight_edges()
    test_forest_excludes_stale_predecessor()
    test_forest_excludes_nodes_outside_W()
    test_forest_one_parent_per_node_on_ties()

    # find_pivots
    test_find_pivots_early_exit_when_W_too_large()
    test_find_pivots_only_large_trees_are_pivots()
    test_find_pivots_bound_limits_W()
    test_find_pivots_source_node_inside_another_tree_is_not_pivot()
    test_find_pivots_improves_costs()
    test_find_pivots_equal_paths_pick_smaller_predecessor()

    # workspace
    test_workspace_k_t_use_log2()
    test_workspace_k_t_at_least_1_on_tiny_graphs()











    print("All tests passed")