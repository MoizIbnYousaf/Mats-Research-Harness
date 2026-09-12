def sum_manhattan_distances(m: int, n: int, k: int) -> int:
    """ Given a rectangular grid of size m × n, calculate the sum of Manhattan distances 
    between every pair of k identical pieces over all valid arrangements.
    
    A valid arrangement is a placement of all k pieces on the grid with at most one piece per cell.
    The Manhattan Distance between two cells (x_i, y_i) and (x_j, y_j) is |x_i - x_j| + |y_i - y_j|.
    
    Return the sum modulo 10^9 + 7.
    
    Args:
        m: Number of rows in the grid (1 <= m <= 10^5)
        n: Number of columns in the grid (1 <= n <= 10^5, 2 <= m * n <= 10^5)
        k: Number of identical pieces to place (2 <= k <= m * n)
    
    Returns:
        The sum of Manhattan distances between every pair of pieces over all valid arrangements,
        modulo 10^9 + 7.
    
    >>> sum_manhattan_distances(2, 2, 2)
    8
    >>> sum_manhattan_distances(1, 4, 3)
    20
    >>> sum_manhattan_distances(1, 3, 3)
    4
    """
    MOD = 10**9 + 7
    N = m * n

    # Sum of Manhattan distances over all unordered pairs of cells in an m x n grid.
    # Separates into independent row and column components:
    #   row part    = n^2 * sum_{i<j} (j-i) = n^2 * (m^3 - m) / 6
    #   column part = m^2 * sum_{i<j} (j-i) = m^2 * (n^3 - n) / 6
    pair_sum = (n * n * (m * m * m - m) + m * m * (n * n * n - n)) // 6

    # Each unordered pair of cells is occupied in C(N-2, k-2) arrangements.
    k -= 2
    if k > 0:
        fact = [1] * (N - 1)
        for i in range(1, N - 1):
            fact[i] = fact[i - 1] * i % MOD
        inv_fact = [1] * (N - 1)
        inv_fact[N - 2] = pow(fact[N - 2], MOD - 2, MOD)
        for i in range(N - 2, 0, -1):
            inv_fact[i - 1] = inv_fact[i] * i % MOD
        factor = fact[N - 2] * inv_fact[k] % MOD * inv_fact[N - 2 - k] % MOD
    else:
        factor = 1

    return pair_sum % MOD * factor % MOD
