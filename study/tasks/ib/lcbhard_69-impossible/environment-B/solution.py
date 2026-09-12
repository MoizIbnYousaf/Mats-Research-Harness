from typing import List, Tuple


def min_deletions_to_snowflake(n: int, edges: List[Tuple[int, int]]) -> int:
    """ Given a tree with n vertices numbered 1 to n, find the minimum number of vertices
    that must be deleted (along with their adjacent edges) so that the remaining graph
    becomes a Snowflake Tree.

    A Snowflake Tree is defined as a tree with:
    - One central vertex
    - x vertices connected to the central vertex (x > 0)
    - y leaves connected to each of those x vertices (y > 0)

    Args:
        n: Number of vertices in the tree (3 <= n <= 3 * 10^5)
        edges: List of edges, where each edge is a tuple (u, v) with 1 <= u < v <= n

    Returns:
        The minimum number of vertices that must be deleted

    >>> min_deletions_to_snowflake(8, [(1, 3), (2, 3), (3, 4), (4, 5), (5, 6), (5, 7), (4, 8)])
    1
    >>> min_deletions_to_snowflake(3, [(1, 2), (2, 3)])
    0
    >>> min_deletions_to_snowflake(10, [(1, 3), (1, 2), (5, 7), (6, 10), (2, 8), (1, 6), (8, 9), (2, 7), (1, 4)])
    3
    """
    # Build adjacency lists.
    adj = [[] for _ in range(n + 1)]
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)

    best = 0
    for c in range(1, n + 1):
        # For each potential middle vertex m (a neighbor of center c):
        # s_m = number of neighbors of m besides c = deg(m) - 1 (these can be its leaves).
        s_vals = []
        for m in adj[c]:
            s_vals.append(len(adj[m]) - 1)
        s_vals.sort(reverse=True)

        # Choose x middles with the largest s values; the best y for that x is s_vals[x-1].
        # Snowflake size = 1 + x + x*y (center + middles + leaves).
        for x, s in enumerate(s_vals, 1):
            if s < 1:  # y must be at least 1
                break
            size = 1 + x + x * s
            if size > best:
                best = size

    # Delete every vertex not part of the largest snowflake.
    return n - best
