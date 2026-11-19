
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
        self.k = math.floor((math.log(len(graph.nodes)) ** (1/3)))
        self.t = math.floor((math.log(len(graph.nodes)) ** (2/3)))

def bmssp(level_l, bound_B, closed_S, bmssp_ws: bmssp_workspace):
    # Base case:
    if level_l == 0:
        return base_case(bound_B, closed_S, bmssp_ws)




def find_pivots(bound_B, closed_S, bmssp_ws: bmssp_workspace):
    explored = set(closed_S)
    init_relax_frontier = set(closed_S)









def base_case(bound_B, closed_S, bmssp_ws: bmssp_workspace) -> tuple[float, set]:
    # solve the bmssp using dijkstra for the base case

    # closed_S should be singleton, raise an error if not
    if len(closed_S) != 1:
        raise ValueError("closed_S should be a singleton set")

    graph = bmssp_ws.graph
    g_cost = bmssp_ws.g_cost
    k = bmssp_ws.k

    # works whether closed_S is a list or a set
    start_node = next(iter(closed_S))

    # start from the node's existing (already final) cost, not 0
    settled = set()
    bin_heap = [(g_cost[start_node], start_node)]

    # Dijkstra from start_node, stopping once k + 1 nodes have been settled
    while bin_heap and len(settled) < k + 1:
        current_cost, current_node = heapq.heappop(bin_heap)
        # skip nodes already settled, and stale heap entries superseded by a cheaper push
        if current_node in settled or current_cost > g_cost[current_node]:
            continue
        settled.add(current_node)

        for neighbor in graph.neighbors(current_node):
            new_cost = current_cost + graph[current_node][neighbor].get('weight', 1)
            # relax only if it doesn't worsen the known cost and stays strictly below the bound.
            # '<=' (as in the paper) lets a node whose cost was already set to this value
            # by another path still be included in the result set
            if new_cost <= g_cost[neighbor] and new_cost < bound_B:
                g_cost[neighbor] = new_cost
                heapq.heappush(bin_heap, (new_cost, neighbor))

    if len(settled) <= k:
        return bound_B, settled

    # found more than k nodes: shrink the bound to the largest settled cost,
    # and return only the nodes strictly below it
    new_bound = max(g_cost[node] for node in settled)
    return new_bound, {node for node in settled if g_cost[node] < new_bound}

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
    # B' = largest settled cost = 3; returned set is nodes with cost < 3
    ws = _workspace(_path_graph(), 0, k=2)
    bound, found = base_case(100, [0], ws)
    assert bound == 3
    assert found == {0, 1}
    assert ws.g_cost[1] == 1 and ws.g_cost[2] == 3


def test_base_case_exactly_k_nodes_returns_original_bound():
    # only 3 nodes reachable below B and k = 3 -> no truncation
    ws = _workspace(_path_graph(), 0, k=3)
    bound, found = base_case(5, [0], ws)
    assert bound == 5
    assert found == {0, 1, 2}


def test_base_case_ties_at_new_bound_are_excluded():
    # star: 1, 2, 3 all at cost 1 from 0. k = 2 settles 0 and two leaves,
    # B' = 1, and only nodes with cost strictly < 1 are returned
    G = nx.Graph()
    for leaf in (1, 2, 3):
        G.add_edge(0, leaf, weight=1)
    ws = _workspace(G, 0, k=2)
    bound, found = base_case(100, [0], ws)
    assert bound == 1
    assert found == {0}


def test_base_case_rejects_non_singleton():
    ws = _workspace(_path_graph(), 0, k=10)
    try:
        base_case(10, [0, 1], ws)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for non-singleton closed_S")


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
    test_base_case_ties_at_new_bound_are_excluded()
    test_base_case_rejects_non_singleton()











    print("All tests passed")