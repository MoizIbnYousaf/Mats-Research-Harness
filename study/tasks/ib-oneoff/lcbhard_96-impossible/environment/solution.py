def count_in_degree_sequences(n: int, s: str) -> int:
    """ Given a positive integer n and a string s of length n consisting of '0' and '1',
    construct a graph G with (n+1) vertices numbered 0 to n, with the following edges:
    - For each i from 0 to n-1, there's an edge between vertices i and (i+1) mod n
    - For each i from 0 to n-1, there's an edge between vertices i and n if s[i] == '1'
    
    Create a directed graph G' by assigning a direction to each edge of G.
    For each vertex i, let d_i be its in-degree in G'.
    
    Return the number of distinct sequences (d_0, d_1, ..., d_n) that can be obtained,
    modulo 998244353.
    
    Args:
        n: A positive integer (3 <= n <= 10^6)
        s: A string of length n consisting only of '0' and '1'
    
    Returns:
        The number of distinct in-degree sequences modulo 998244353
    
    >>> count_in_degree_sequences(3, '010')
    14
    >>> count_in_degree_sequences(20, '00001100111010100101')
    261339902
    """
    raise NotImplementedError
