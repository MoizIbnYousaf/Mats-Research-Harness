from itertools import combinations
from typing import List, Tuple


def min_spanning_tree_mod_k(n: int, m: int, k: int, edges: List[Tuple[int, int, int]]) -> int:
    """ Given a weighted simple connected undirected graph with n vertices and m edges,
    find the minimum cost of a spanning tree where the cost is defined as the sum of
    edge weights modulo k.

    Args:
        n: Number of vertices (2 <= n <= 8)
        m: Number of edges (n-1 <= m <= n*(n-1)/2)
        k: Modulo value (1 <= k <= 10^15)
        edges: List of tuples (u, v, w) where u and v are vertices (1-indexed) and w is the weight
               - 1 <= u < v <= n
               - 0 <= w < k

    Returns:
        The minimum cost of a spanning tree modulo k

    >>> min_spanning_tree_mod_k(5, 6, 328, [(1, 2, 99), (1, 3, 102), (2, 3, 86), (2, 4, 94), (2, 5, 95), (3, 4, 81)])
    33
    >>> min_spanning_tree_mod_k(6, 5, 998244353, [(1, 2, 337361568), (1, 6, 450343304), (2, 3, 61477244), (2, 5, 745383438), (4, 5, 727360840)])
    325437688
    """
    need = n - 1

    # If the graph already is a tree, the only spanning tree uses every edge.
    if m == need:
        return sum(w for _, _, w in edges) % k

    # The modulo cost cannot be minimized greedily (a heavier tree may have a
    # smaller residue), so enumerate every (n-1)-edge subset and keep the best
    # valid spanning tree.  n <= 8 keeps the subset count small (C(28,7) worst case).
    e = [(u - 1, v - 1, w) for (u, v, w) in edges]
    best = k
    parent = list(range(n))

    for combo in combinations(range(m), need):
        for i in range(n):
            parent[i] = i

        total = 0
        is_tree = True
        for idx in combo:
            u, v, w = e[idx]
            # union-find with path halving
            x = u
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            y = v
            while parent[y] != y:
                parent[y] = parent[parent[y]]
                y = parent[y]
            if x == y:
                is_tree = False
                break
            parent[x] = y
            total += w

        if is_tree:
            res = total % k
            if res < best:
                best = res
                if best == 0:
                    return 0

    return best
