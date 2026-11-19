
import heapq

import math

import networkx as nx

from block_data_struct import BlockHeap, Block

from bmssp_recorder import BMSSPRecorder, format_bound, format_nodes



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
        # optional BMSSPRecorder (see bmssp_recorder.py); None = no visualization
        self.recorder = None

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
        if self.recorder:
            self.recorder.on_relax(u, v)


def as_bound(bound_B):
    '''
    Bounds are compared against node keys (cost, hops, node). A plain number B
    becomes (B,), and (c, h, v) < (B,) exactly when c < B.
    '''
    return bound_B if isinstance(bound_B, tuple) else (bound_B,)

def bmssp(level_l, bound_B, closed_S, bmssp_ws: bmssp_workspace):
    '''
    BMSSP(l, B, S) from Duan et al. (Algorithm 3).
    Returns (B', U): a new bound B' <= B, and the set U of nodes whose shortest
    path costs are now final and below B'.
    Bounds are node keys (cost, hops, node) or (B,); see as_bound.
    '''
    # line 6: base case
    if level_l == 0:
        return base_case(bound_B, closed_S, bmssp_ws)

    ws = bmssp_ws
    bound = as_bound(bound_B)
    if ws.recorder:
        ws.recorder.enter_call(level_l, bound_B, closed_S)

    # line 8: find the pivot nodes P and the encountered nodes W
    pivot_set_P, encountered_nodes_W = find_pivots(bound_B, closed_S, ws)

    # line 9-10: block data structure D with M = 2^((l-1)t), holding the pivots' keys
    block_data_struct_D = BlockHeap(
        m_limit=2 ** ((level_l - 1) * ws.t),
        bound_B=bound,
    )
    # node -> the key D currently holds for it (added by Insert or BatchPrepend,
    # forgotten once pulled out). A node can be relaxed to a different path with
    # the same (cost, hops, node) key (equal cost and hops, smaller predecessor);
    # adding that key again would put a duplicate in D, which the block heap
    # does not allow. The paper's Insert just keeps the existing entry then.
    key_in_D = {}
    for node in pivot_set_P:
        block_data_struct_D.insert(ws.key(node))
        key_in_D[node] = ws.key(node)
    if ws.recorder:
        ws.recorder.attach_structure(block_data_struct_D)
        ws.recorder.frame(f"FindPivots: P = {format_nodes(pivot_set_P)}, |W| = {len(encountered_nodes_W)}; "
                          f"insert P into D", active=pivot_set_P)

    # line 11: B'_0 = smallest pivot key, or B if there are no pivots
    last_bound_B_prime = min((ws.key(node) for node in pivot_set_P), default=bound)
    resolved_below_bound_U = set()
    max_resolved = ws.k * 2 ** (level_l * ws.t)

    # line 12
    while len(resolved_below_bound_U) < max_resolved and not block_data_struct_D.is_empty():
        # line 14: pull the smallest M keys and the bound B_i separating them from the rest.
        # D can still hold an outdated key for a node whose cost improved after it
        # was inserted (the paper's Insert replaces it; the block heap does not), so
        # keep only keys that are still the node's current key
        bound_B_i, pulled_keys = block_data_struct_D.pull()
        for key in pulled_keys:
            if key_in_D.get(key[2]) == key:
                del key_in_D[key[2]]
        pulled_nodes_S_i = {key[2] for key in pulled_keys if key == ws.key(key[2])}
        if ws.recorder:
            ws.recorder.frame(f"Pull: S_i = {format_nodes(pulled_nodes_S_i)}, B_i = {format_bound(bound_B_i)}",
                              active=pulled_nodes_S_i)

        # line 15-16: recurse on the pulled nodes
        if pulled_nodes_S_i:
            bound_B_prime_i, resolved_U_i = bmssp(level_l - 1, bound_B_i, pulled_nodes_S_i, ws)
        else:
            bound_B_prime_i, resolved_U_i = bound_B_i, set()
        resolved_below_bound_U |= resolved_U_i
        last_bound_B_prime = bound_B_prime_i

        # line 17-24: relax edges out of the newly resolved nodes
        relaxation_group_K = set()
        for node in resolved_U_i:
            for neighbor in ws.graph.neighbors(node):
                new_cost = ws.g_cost[node] + ws.graph[node][neighbor].get('weight', 1)
                if ws.is_valid_relaxation(node, neighbor, new_cost):   # '<=' with tie-break
                    ws.relax(node, neighbor, new_cost)
                    neighbor_key = ws.key(neighbor)
                    if bound_B_i <= neighbor_key < bound:                # [B_i, B) -> Insert
                        if key_in_D.get(neighbor) != neighbor_key:
                            block_data_struct_D.insert(neighbor_key)
                            key_in_D[neighbor] = neighbor_key
                    elif bound_B_prime_i <= neighbor_key < bound_B_i:    # [B'_i, B_i) -> K
                        relaxation_group_K.add(neighbor)

        # line 25: batch prepend K, plus the pulled nodes that were not resolved.
        # keys are rebuilt here because a node may be relaxed several times in one
        # iteration, and only its latest key is valid
        nodes_to_prepend = relaxation_group_K | pulled_nodes_S_i
        keys_to_prepend = {
            ws.key(node) for node in nodes_to_prepend
            if bound_B_prime_i <= ws.key(node) < bound_B_i
        }
        block_data_struct_D.batch_prepend(keys_to_prepend)
        for key in keys_to_prepend:
            key_in_D[key[2]] = key
        if ws.recorder:
            ws.recorder.frame(f"Relax edges out of U_i; batch prepend: {format_nodes(k[2] for k in keys_to_prepend)}",
                              active=resolved_U_i)

    # after the loop: B' = min(last B'_i, B); add the nodes of W below B'
    bound_B_prime = min(last_bound_B_prime, bound)
    resolved_below_bound_U |= {node for node in encountered_nodes_W if ws.key(node) < bound_B_prime}
    if ws.recorder:
        ws.recorder.exit_call(level_l, closed_S, bound_B_prime, resolved_below_bound_U)
    return bound_B_prime, resolved_below_bound_U


def bmssp_shortest_paths(graph, source, visualization_path=None):
    '''
    Single-source shortest paths with BMSSP, using the paper's top-level call:
    l = ceil(log2(n) / t), S = {source}, B = infinity.
    Returns (g_cost, predecessors): {node: cost} (inf if unreachable) and
    {node: predecessor on its shortest path} (the source has none).

    The paper's setting is a directed graph with non-negative edge weights.
    An undirected graph also works (each edge counts in both directions).
    Missing weights default to 1, as elsewhere in this file.

    visualization_path: if given, the run is recorded and written to this JSON
    file for the Manim scene in visualization/bmssp_scene.py (format in
    visualization/schema.py). Recording doesn't change the result. Meant for
    small graphs (around 10-20 nodes); nodes may have a 'pos' attribute (x, y)
    to control the layout, otherwise one is computed.
    '''
    for u, v, weight in graph.edges(data='weight', default=1):
        if weight < 0:
            raise ValueError(f"edge ({u}, {v}) has negative weight {weight}; BMSSP needs non-negative weights")
    ws = bmssp_workspace(graph, source)
    n = len(graph.nodes)
    top_level = math.ceil(math.log2(n) / ws.t) if n > 1 else 0

    if visualization_path is not None:
        ws.recorder = BMSSPRecorder(ws)
        ws.recorder.frame(f"Start: source {source}, k = {ws.k}, t = {ws.t}, top level l = {top_level}",
                          active={source})

    bmssp(top_level, float('inf'), {source}, ws)

    if ws.recorder:
        ws.recorder.frame("Done: every reachable node is complete")
        ws.recorder.write(visualization_path)
        ws.recorder = None
    return ws.g_cost, ws.predecessors


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
    Works with non-negative edge weights, including 0: each parent has one
    hop fewer than its child, so following parents can never loop.
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
    if bmssp_ws.recorder:
        bmssp_ws.recorder.enter_call(0, bound_B, closed_S)

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
        result = (bound_B, settled)
    else:
        # found more than k nodes: the new bound B' is the largest settled key,
        # and only nodes strictly below it are returned. Keys are unique, so
        # exactly one settled node (the largest) is left out.
        new_bound = max(bmssp_ws.key(node) for node in settled)
        result = (new_bound, {node for node in settled if bmssp_ws.key(node) < new_bound})

    if bmssp_ws.recorder:
        bmssp_ws.recorder.exit_call(0, closed_S, *result)
    return result

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


# ---------------------------------------------------------------------------
# bmssp tests, checked against networkx's Dijkstra
# ---------------------------------------------------------------------------

def _random_weighted_graph(rng, n, p, directed, max_weight):
    G = nx.gnp_random_graph(n, p, seed=rng.randint(0, 10**9), directed=directed)
    for u, v in G.edges:
        G[u][v]['weight'] = rng.randint(1, max_weight)
    return G


def _assert_matches_networkx(G, source):
    '''
    Runs bmssp_shortest_paths and checks it against networkx:
      - reachable nodes get exactly networkx's shortest-path cost
      - unreachable nodes stay at inf
      - every predecessor edge is tight, and following predecessors from any
        reachable node leads back to the source
    '''
    cost, pred = bmssp_shortest_paths(G, source)
    true = nx.single_source_dijkstra_path_length(G, source)

    for node in G.nodes:
        if node in true:
            assert cost[node] == true[node], (node, cost[node], true[node])
        else:
            assert cost[node] == float('inf'), (node, cost[node])

    for node in true:
        if node == source:
            continue
        parent = pred[node]
        assert cost[node] == cost[parent] + G[parent][node].get('weight', 1), node
        # walk back to the source (at most n steps, so a cycle would be caught)
        current, steps = node, 0
        while current != source:
            current = pred[current]
            steps += 1
            assert steps <= len(G), f"predecessor cycle from {node}"


def test_bmssp_path_graph():
    _assert_matches_networkx(_path_graph(), 0)


def test_bmssp_single_node():
    G = nx.Graph()
    G.add_node(0)
    cost, pred = bmssp_shortest_paths(G, 0)
    assert cost == {0: 0}
    assert pred == {}


def test_bmssp_two_nodes():
    G = nx.Graph()
    G.add_edge(0, 1, weight=4)
    _assert_matches_networkx(G, 0)


def test_bmssp_picks_cheaper_route():
    # 0->2 directly costs 5, but 0->1->3->2 costs 3
    G = nx.Graph()
    G.add_edge(0, 1, weight=1)
    G.add_edge(1, 3, weight=1)
    G.add_edge(3, 2, weight=1)
    G.add_edge(0, 2, weight=5)
    _assert_matches_networkx(G, 0)


def test_bmssp_unreachable_nodes_stay_inf():
    G = _path_graph()
    G.add_edge(50, 51, weight=1)   # separate component
    G.add_node(99)                 # isolated
    _assert_matches_networkx(G, 0)
    cost, _ = bmssp_shortest_paths(G, 0)
    assert cost[50] == cost[51] == cost[99] == float('inf')


def test_bmssp_directed_edges_followed_forwards_only():
    G = nx.DiGraph()
    G.add_edge(0, 1, weight=1)
    G.add_edge(1, 2, weight=1)
    G.add_edge(3, 2, weight=1)     # 3 is not reachable from 0
    _assert_matches_networkx(G, 0)
    cost, _ = bmssp_shortest_paths(G, 0)
    assert cost[3] == float('inf')


def test_bmssp_non_zero_source():
    G = _path_graph()
    _assert_matches_networkx(G, 2)


def test_bmssp_ties_pick_smaller_predecessor():
    # diamond: 0-1-3 and 0-2-3 both cost 2; the tie-break picks predecessor 1
    G = nx.Graph()
    for u, v in [(0, 1), (0, 2), (1, 3), (2, 3)]:
        G.add_edge(u, v, weight=1)
    cost, pred = bmssp_shortest_paths(G, 0)
    assert cost[3] == 2
    assert pred[3] == 1


def test_bmssp_matches_networkx_random_small():
    # many small graphs: undirected and directed, sparse and dense,
    # weights from all-equal (lots of ties) to varied
    import random
    rng = random.Random(0)
    for _ in range(400):
        G = _random_weighted_graph(
            rng,
            n=rng.randint(1, 60),
            p=rng.choice([0.05, 0.1, 0.2, 0.4]),
            directed=rng.random() < 0.5,
            max_weight=rng.choice([1, 3, 20]),
        )
        _assert_matches_networkx(G, 0)


def test_bmssp_matches_networkx_random_large():
    # larger graphs reach recursion level 3 and use batch_prepend heavily
    import random
    rng = random.Random(1)
    for n in (200, 1000, 3000):
        for directed in (False, True):
            G = nx.gnm_random_graph(n, 4 * n, seed=rng.randint(0, 10**9), directed=directed)
            for u, v in G.edges:
                G[u][v]['weight'] = rng.randint(1, 10)
            _assert_matches_networkx(G, 0)


def test_bmssp_matches_networkx_on_grid():
    # a grid has many equal-length shortest paths, which stresses the tie-break
    G = nx.grid_2d_graph(20, 20)
    G = nx.convert_node_labels_to_integers(G)   # node ids must be comparable
    _assert_matches_networkx(G, 0)


def test_bmssp_directed_with_zero_weights():
    # non-negative includes 0: some, half, or all edges weigh 0
    import random
    rng = random.Random(5)
    for trial in range(300):
        G = nx.gnp_random_graph(rng.randint(1, 120), rng.choice([0.03, 0.08, 0.2]),
                                seed=trial, directed=True)
        zero_share = rng.choice([0.1, 0.5, 1.0])
        for u, v in G.edges:
            G[u][v]['weight'] = 0 if rng.random() < zero_share else rng.randint(1, 5)
        _assert_matches_networkx(G, 0)


def test_bmssp_zero_weight_cycle():
    # 1 <-> 2 is a zero-weight cycle; it must not make predecessors loop
    G = nx.DiGraph()
    G.add_edge(0, 1, weight=1)
    G.add_edge(1, 2, weight=0)
    G.add_edge(2, 1, weight=0)
    G.add_edge(2, 3, weight=2)
    _assert_matches_networkx(G, 0)
    cost, pred = bmssp_shortest_paths(G, 0)
    assert cost == {0: 0, 1: 1, 2: 1, 3: 3}
    assert pred[2] == 1 and pred[1] == 0


def test_bmssp_rejects_negative_weights():
    G = nx.DiGraph()
    G.add_edge(0, 1, weight=2)
    G.add_edge(1, 2, weight=-1)
    try:
        bmssp_shortest_paths(G, 0)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for a negative weight")


def test_bmssp_inserts_and_prepends_respect_pull_bound():
    # Algorithm 3 lines 21-25: after a pull returns bound B_i, relaxed values in
    # [B_i, B) go to D.Insert, and values below B_i go to D.BatchPrepend.
    # Sending them the wrong way still gives correct distances (they all end up
    # in D), so comparing with networkx can't catch it; this checks the rule
    # directly by watching every BlockHeap that bmssp creates.
    import random
    original_pull = BlockHeap.pull
    original_insert = BlockHeap.insert
    original_prepend = BlockHeap.batch_prepend
    checked = {'insert': 0, 'prepend': 0}

    def watched_pull(self):
        bound, items = original_pull(self)
        self._last_pull_bound = bound
        return bound, items

    def watched_insert(self, value):
        last_bound = getattr(self, '_last_pull_bound', None)
        if last_bound is not None:   # inserts of the pivots happen before any pull
            assert value >= last_bound, f"inserted {value} below pull bound {last_bound}"
            checked['insert'] += 1
        return original_insert(self, value)

    def watched_prepend(self, values):
        values = list(values)
        last_bound = getattr(self, '_last_pull_bound', None)
        assert last_bound is not None, "batch_prepend called before any pull"
        for value in values:
            assert value < last_bound, f"prepended {value} not below pull bound {last_bound}"
            checked['prepend'] += 1
        return original_prepend(self, values)

    BlockHeap.pull = watched_pull
    BlockHeap.insert = watched_insert
    BlockHeap.batch_prepend = watched_prepend
    try:
        rng = random.Random(6)
        for _ in range(60):
            n = rng.randint(50, 800)
            G = nx.gnm_random_graph(n, 4 * n, seed=rng.randint(0, 10**9), directed=True)
            for u, v in G.edges:
                G[u][v]['weight'] = rng.randint(0, 10)
            _assert_matches_networkx(G, 0)
    finally:
        BlockHeap.pull = original_pull
        BlockHeap.insert = original_insert
        BlockHeap.batch_prepend = original_prepend

    # make sure the rule was actually exercised, not skipped
    assert checked['insert'] > 0 and checked['prepend'] > 0, checked


def test_bmssp_never_puts_duplicate_values_in_D():
    # BlockHeap needs distinct values. A node can be relaxed to a different path
    # with the same (cost, hops, node) key (equal cost and hops, smaller
    # predecessor); if that key is already in D (inserted OR prepended), adding
    # it again would store a duplicate. Checks every BlockHeap after each change.
    import random
    original_insert = BlockHeap.insert
    original_prepend = BlockHeap.batch_prepend

    def all_values(heap):
        snap = heap.snapshot()
        values = [v for _, _, items in snap['heap_blocks'] for v in items]
        values += snap['b_block'][2]
        values += [v for block in snap['prepend_blocks'] for v in block]
        return values

    def checked_insert(self, value):
        original_insert(self, value)
        values = all_values(self)
        assert len(values) == len(set(values)), f"duplicate after insert of {value}"

    def checked_prepend(self, values):
        values = list(values)
        original_prepend(self, values)
        stored = all_values(self)
        assert len(stored) == len(set(stored)), f"duplicate after batch_prepend of {values}"

    BlockHeap.insert = checked_insert
    BlockHeap.batch_prepend = checked_prepend
    try:
        rng = random.Random(7)
        for _ in range(300):
            # small weights -> many equal-cost, equal-hop paths
            G = _random_weighted_graph(rng, n=rng.randint(5, 60), p=rng.choice([0.1, 0.2, 0.3]),
                                       directed=True, max_weight=rng.choice([1, 2]))
            _assert_matches_networkx(G, 0)
        # the case found by the visualization: I is prepended, then relaxed again
        # via E with the same cost and hops but a smaller predecessor than F
        import os, sys
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "visualization"))
        from make_bmssp_replay import sample_graph
        _assert_matches_networkx(sample_graph(), "A")
    finally:
        BlockHeap.insert = original_insert
        BlockHeap.batch_prepend = original_prepend


# ---------------------------------------------------------------------------
# visualization export (bmssp_shortest_paths(..., visualization_path=...))
# ---------------------------------------------------------------------------

def _load_replay(path):
    # visualization/schema.py has no manim dependency, so it can be used here
    import os, sys
    vis_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "visualization")
    if vis_dir not in sys.path:
        sys.path.insert(0, vis_dir)
    from schema import AlgorithmReplay
    return AlgorithmReplay.load(path)


def test_visualization_does_not_change_result():
    import os, random, tempfile
    rng = random.Random(8)
    with tempfile.TemporaryDirectory() as tmp:
        for trial in range(40):
            G = _random_weighted_graph(rng, n=rng.randint(1, 25), p=0.2,
                                       directed=rng.random() < 0.7, max_weight=rng.choice([1, 4]))
            plain_cost, plain_pred = bmssp_shortest_paths(G, 0)
            recorded_cost, recorded_pred = bmssp_shortest_paths(G, 0, visualization_path=os.path.join(tmp, f"{trial}.json"))
            assert recorded_cost == plain_cost and recorded_pred == plain_pred


def test_visualization_replay_matches_schema_and_result():
    import os, random, tempfile
    rng = random.Random(9)
    with tempfile.TemporaryDirectory() as tmp:
        for trial in range(30):
            G = _random_weighted_graph(rng, n=rng.randint(2, 20), p=0.25, directed=True, max_weight=5)
            path = os.path.join(tmp, f"{trial}.json")
            cost, _ = bmssp_shortest_paths(G, 0, visualization_path=path)
            replay = _load_replay(path)

            assert replay.algorithm == "bmssp" and replay.graph.directed
            assert {n.id for n in replay.graph.nodes} == {str(n) for n in G.nodes}
            assert len(replay.graph.edges) == G.number_of_edges()
            assert all(-1 <= n.x <= 1 and -1 <= n.y <= 1 for n in replay.graph.nodes)
            assert len(replay.frames) >= 2

            edge_ids = {(e.source, e.target) for e in replay.graph.edges}
            for frame in replay.frames:
                assert len(frame.graph_state.nodes) == len(G.nodes)
                assert all((e.source, e.target) in edge_ids for e in frame.graph_state.edges)
                if frame.block_state is not None:
                    assert frame.block_state.b_block is not None

            # last frame: every reachable node complete with its final cost
            final = {ns.id: ns for ns in replay.frames[-1].graph_state.nodes}
            for node in G.nodes:
                if cost[node] == float('inf'):
                    assert final[str(node)].state == "unexplored"
                else:
                    assert final[str(node)].state == "closed", (node, final[str(node)].state)
                    assert final[str(node)].label_extra == f"d={cost[node]}"


def test_visualization_records_block_structure_and_calls():
    import os, tempfile, sys
    vis_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "visualization")
    sys.path.insert(0, vis_dir)
    from make_bmssp_replay import sample_graph
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "sample.json")
        bmssp_shortest_paths(sample_graph(), "A", visualization_path=path)
        replay = _load_replay(path)
    stacks = [f.call_stack for f in replay.frames]
    assert max(len(s) for s in stacks) == 3                       # level 2 -> level 1 -> base case
    assert any(s and s[-1].startswith("BaseCase") for s in stacks)
    states = [f.block_state for f in replay.frames if f.block_state]
    assert any(b.prepend_blocks for b in states)                  # BatchPrepend shows up
    assert any(len(blk.items) > 1 for b in states for blk in b.heap_blocks)
    assert any(item.stale for b in states for blk in b.heap_blocks + [b.b_block] for item in blk.items)
    assert any(item.highlight for b in states for blk in b.heap_blocks + [b.b_block] for item in blk.items)


def test_visualization_large_example_has_three_sizes_of_D():
    # the 26-node example runs at level 3, so D comes in three sizes:
    # M = 2^((l-1)t) = 16, 4 and 1; level 3's D0 gets blocks of up to 8
    import os, tempfile, sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "visualization"))
    from make_bmssp_replay import large_sample_graph
    G = large_sample_graph()
    assert len(G) == 26
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "large.json")
        cost, _ = bmssp_shortest_paths(G, "A", visualization_path=path)
        replay = _load_replay(path)
    assert cost == {**{n: float('inf') for n in G}, **nx.single_source_dijkstra_path_length(G, "A")}
    titles = {f.block_state.title.split(",")[0] for f in replay.frames if f.block_state}
    assert titles == {"D at level 3: M = 16", "D at level 2: M = 4", "D at level 1: M = 1"}
    level3 = [f.block_state for f in replay.frames
              if f.block_state and f.block_state.title.startswith("D at level 3")]
    assert max(len(b.items) for s in level3 for b in s.prepend_blocks) == 8


def test_visualization_undirected_graph_lists_each_edge_once():
    import os, tempfile
    G = _path_graph()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "undirected.json")
        bmssp_shortest_paths(G, 0, visualization_path=path)
        replay = _load_replay(path)
    assert replay.graph.directed is False
    assert len(replay.graph.edges) == 3
    # relaxing 1 -> 0 direction of an undirected edge still highlights the listed edge
    edge_ids = {(e.source, e.target) for e in replay.graph.edges}
    assert all((e.source, e.target) in edge_ids for f in replay.frames for e in f.graph_state.edges)


def test_no_visualization_file_without_path():
    import os, tempfile
    with tempfile.TemporaryDirectory() as tmp:
        before = set(os.listdir(tmp))
        bmssp_shortest_paths(_path_graph(), 0)
        assert set(os.listdir(tmp)) == before


def test_bmssp_one_level_returns_consistent_bound_and_set():
    # a single level-1 call with a small k and t can stop early (|U| limit), so it
    # may return B' < B. Whatever it returns, U must be exactly the nodes whose key
    # is below B', and their costs must already be final
    import random
    rng = random.Random(2)
    for _ in range(200):
        G = _random_weighted_graph(rng, n=rng.randint(2, 80), p=0.1,
                                   directed=rng.random() < 0.5, max_weight=5)
        true = nx.single_source_dijkstra_path_length(G, 0)
        ws = bmssp_workspace(G, 0)
        bound = rng.choice([float('inf'), rng.randint(1, 30)])
        bound_B_prime, resolved_U = bmssp(1, bound, {0}, ws)

        assert bound_B_prime <= as_bound(bound)
        for node in resolved_U:
            assert ws.g_cost[node] == true[node], node
        assert resolved_U == {node for node in true if ws.key(node) < bound_B_prime}


def test_bmssp_one_level_stops_early_on_long_path():
    # path of 100 nodes: at level 1 the loop stops once |U| reaches k * 2^t,
    # so the returned bound is below B and U is a prefix of the path
    G = nx.path_graph(100)
    ws = bmssp_workspace(G, 0)
    bound_B_prime, resolved_U = bmssp(1, float('inf'), {0}, ws)
    assert bound_B_prime < as_bound(float('inf'))
    assert 0 < len(resolved_U) < 100
    assert resolved_U == set(range(len(resolved_U)))
    assert all(ws.g_cost[node] == node for node in resolved_U)


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












    # bmssp
    test_bmssp_path_graph()
    test_bmssp_single_node()
    test_bmssp_two_nodes()
    test_bmssp_picks_cheaper_route()
    test_bmssp_unreachable_nodes_stay_inf()
    test_bmssp_directed_edges_followed_forwards_only()
    test_bmssp_non_zero_source()
    test_bmssp_ties_pick_smaller_predecessor()
    test_bmssp_matches_networkx_random_small()
    test_bmssp_matches_networkx_random_large()
    test_bmssp_matches_networkx_on_grid()
    test_bmssp_directed_with_zero_weights()
    test_bmssp_zero_weight_cycle()
    test_bmssp_rejects_negative_weights()
    test_bmssp_inserts_and_prepends_respect_pull_bound()
    test_bmssp_never_puts_duplicate_values_in_D()
    test_bmssp_one_level_returns_consistent_bound_and_set()
    test_bmssp_one_level_stops_early_on_long_path()

    # visualization export
    test_visualization_does_not_change_result()
    test_visualization_replay_matches_schema_and_result()
    test_visualization_records_block_structure_and_calls()
    test_visualization_large_example_has_three_sizes_of_D()
    test_visualization_undirected_graph_lists_each_edge_once()
    test_no_visualization_file_without_path()

    print("All tests passed")