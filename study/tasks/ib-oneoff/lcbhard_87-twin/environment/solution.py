from typing import List, Tuple


def max_alkane_vertices(n: int, edges: List[Tuple[int, int]]) -> int:
    """ Given an undirected tree with n vertices (numbered 1 to n) and edges connecting them,
    find the maximum number of vertices in a subgraph that forms an alkane.
    
    An alkane is defined as:
    - An undirected tree
    - Every vertex has degree 1 or 4
    - There is at least one vertex of degree 4
    
    If no such subgraph exists, return -1.
    
    Args:
        n: Number of vertices (1 <= n <= 2*10^5)
        edges: List of edges, where each edge is a tuple (a, b) representing an undirected edge
               between vertices a and b (1 <= a, b <= n)
    
    Returns:
        Maximum number of vertices in an alkane subgraph, or -1 if none exists
    
    >>> max_alkane_vertices(9, [(1, 2), (2, 3), (3, 4), (4, 5), (2, 6), (2, 7), (3, 8), (3, 9)])
    8
    >>> max_alkane_vertices(7, [(1, 2), (1, 3), (2, 4), (2, 5), (3, 6), (3, 7)])
    -1
    """
    raise NotImplementedError
