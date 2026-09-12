from typing import List, Tuple

def minimize_path_weights(n: int, edges: List[Tuple[int, int, int]], a: List[int], b: List[int]) -> int:
    """ Given a simple connected undirected graph with n vertices and edges (where each edge is 
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
    raise NotImplementedError
