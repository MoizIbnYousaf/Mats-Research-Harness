from typing import List, Tuple, Optional


def min_weight_hamiltonian_walk(n: int, m: int, edges: List[Tuple[int, int, int]]) -> Optional[int]:
    """ Given a weighted directed graph with n vertices (numbered 1 to n) and m edges,
    determine if there exists a walk that visits each vertex at least once.
    If such a walk exists, return the minimum total weight of edges traversed.
    If no such walk exists, return None.
    
    The graph is guaranteed not to contain negative cycles.
    Edges can be traversed multiple times, with their weight counted each time.
    
    Args:
        n: Number of vertices (2 <= n <= 20)
        m: Number of edges (1 <= m <= n*(n-1))
        edges: List of tuples (u, v, w) representing directed edges from u to v with weight w
               where 1 <= u, v <= n, u != v, and -10^6 <= w <= 10^6
    
    Returns:
        The minimum total weight if a valid walk exists, None otherwise.
    
    >>> min_weight_hamiltonian_walk(3, 4, [(1, 2, 5), (2, 1, -3), (2, 3, -4), (3, 1, 100)])
    -2
    >>> min_weight_hamiltonian_walk(3, 2, [(1, 2, 0), (2, 1, 0)])
    None
    >>> min_weight_hamiltonian_walk(2, 1, [(2, 1, 0)])
    0
    """
    raise NotImplementedError
