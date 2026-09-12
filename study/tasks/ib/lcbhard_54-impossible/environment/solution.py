def count_paths(N: int, M: int, K: int, extra_edges: list) -> int:
    """ Count the number of ways to move exactly K times in a directed graph.
    
    The graph has N vertices numbered 1 to N with N+M edges:
    - Edges 1 to N form a cycle: vertex i connects to vertex i+1 (vertex N connects to vertex 1)
    - M additional edges are given in extra_edges as (source, destination) pairs
    
    Starting from vertex 1, count the number of distinct paths of exactly K moves.
    Return the count modulo 998244353.
    
    Args:
        N: Number of vertices (2 <= N <= 200000)
        M: Number of extra edges (0 <= M <= 50)
        K: Number of moves to make (1 <= K <= 200000)
        extra_edges: List of M tuples (X_i, Y_i) representing directed edges from X_i to Y_i
    
    Returns:
        The number of K-length paths starting from vertex 1, modulo 998244353
    
    >>> count_paths(6, 2, 5, [(1, 4), (2, 5)])
    5
    >>> count_paths(10, 0, 200000, [])
    1
    """
    raise NotImplementedError
