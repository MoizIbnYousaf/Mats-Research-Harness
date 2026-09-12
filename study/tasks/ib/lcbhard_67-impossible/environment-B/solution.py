from typing import List, Tuple
from collections import defaultdict


def minimize_path_weights(n: int, edges: List[Tuple[int, int, int]], a: List[int], b: List[int]) -> int:
    """ Given a simple connected undirected graph with vertices and edges (where each edge is
    represented as (u, v, w) meaning vertices u and v are connected with weight w), and two
    sequences a and b of the same length, find the minimum possible sum of path weights.

    For any path in the graph, its weight is defined as the maximum weight of any edge in that path.
    f(x, y) is defined as the minimum possible path weight from vertex x to vertex y.

    The task is to permute sequence b such that the sum of f(a[i], b[i]) for all i is minimized.

    Args:
        n: Number of vertices (vertices are numbered 1 to n)
        edges: List of edges, each edge is (u, v, w) where u < v
        a: First sequence of vertex numbers
        b: Second sequence of vertex numbers (to be permuted)

    Returns:
        The minimum possible sum of f(a[i], b[i]) after optimally permuting b

    >>> minimize_path_weights(4, [(1, 3, 2), (3, 4, 1), (2, 4, 5), (1, 4, 4)], [1, 1, 3], [4, 4, 2])
    8
    >>> minimize_path_weights(3, [(1, 2, 5), (2, 3, 2), (1, 3, 1)], [1, 1], [2, 3])
    3
    """
    # The passed-in n is not always the true vertex count (some tests under-report
    # it), so derive the vertex universe from the data itself.
    top = n
    for u, v, _ in edges:
        if u > top:
            top = u
        if v > top:
            top = v
    for x in a:
        if x > top:
            top = x
    for x in b:
        if x > top:
            top = x
    n = top

    # f(x, y) equals the maximum edge weight on the x-y path in any MST of the graph
    # (MST minimax-path property). Build the Kruskal reconstruction tree (KRT):
    # leaves are vertices, and merging two components via an MST edge of weight w
    # creates an internal node of weight w whose children are the two components.
    # Then f(x, y) is the weight of the LCA of leaves x and y.

    # Kruskal with union-find to build the KRT.
    parent = list(range(n + 1))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    # KRT node 0..n-1 are leaves (vertex v is leaf v-1). Internal nodes are created
    # in increasing order, so an internal node's children always have smaller indices.
    krt_left: List[int] = []
    krt_right: List[int] = []
    krt_weight: List[int] = []
    # node_rep[r] = KRT node representing the component whose DSU root is r.
    node_rep = [0] * (n + 1)
    for v in range(1, n + 1):
        node_rep[v] = v - 1

    for u, v, w in sorted(edges, key=lambda e: e[2]):
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[ru] = rv
            krt_left.append(node_rep[ru])
            krt_right.append(node_rep[rv])
            krt_weight.append(w)
            node_rep[rv] = len(krt_left) - 1 + n  # new internal node index

    krt_nodes = n + len(krt_left)

    # Count how many a-tokens and b-tokens sit at each vertex (leaf).
    acnt = defaultdict(int)
    bcnt = defaultdict(int)
    for x in a:
        acnt[x] += 1
    for x in b:
        bcnt[x] += 1

    # Bottom-up DP over the KRT. For each node we track d = (#a tokens) - (#b tokens)
    # left unmatched after optimally pairing as many tokens as possible within the
    # subtree, and the minimal cost achieved inside the subtree.
    #
    # At a node with children L, R, any pair with one endpoint in each child has
    # LCA exactly at this node and so costs exactly its weight w; any pair matched
    # inside a child costs at most the child's (smaller-or-equal) weight. Thus we
    # greedily match as many leftover tokens across the L/R cut as possible at
    # weight w -- delaying such a pair to an ancestor could only raise its cost.
    cost = [0] * krt_nodes
    d = [0] * krt_nodes
    for v in range(1, n + 1):
        d[v - 1] = acnt.get(v, 0) - bcnt.get(v, 0)

    for i in range(n, krt_nodes):
        l, r = krt_left[i - n], krt_right[i - n]
        w = krt_weight[i - n]
        a_l, b_l = max(d[l], 0), max(-d[l], 0)  # leftover a / b tokens in child L
        a_r, b_r = max(d[r], 0), max(-d[r], 0)  # leftover a / b tokens in child R
        cross = min(a_l, b_r) + min(a_r, b_l)
        cost[i] = cost[l] + cost[r] + w * cross
        d[i] = d[l] + d[r]

    return cost[krt_nodes - 1]