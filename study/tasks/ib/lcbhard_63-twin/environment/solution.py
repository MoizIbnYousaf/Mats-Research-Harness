def count_valid_grids(H: int, W: int, grid: list[str]) -> int:
    """ Given a grid with H rows and W columns consisting of '1', '2', '3', and '?',
    count how many ways we can replace each '?' with '1', '2', or '3' such that
    any two adjacent (edge-sharing) cells contain different digits.
    
    Return the count modulo 998244353.
    
    Args:
        H: Number of rows (1 <= H, H * W <= 200)
        W: Number of columns (1 <= W, H * W <= 200)
        grid: List of strings representing the grid, where grid[i] is the i-th row
        
    Returns:
        The number of valid grid configurations modulo 998244353
        
    >>> count_valid_grids(2, 2, ['1?', '??'])
    6
    >>> count_valid_grids(2, 3, ['123', '3?1'])
    0
    >>> count_valid_grids(1, 1, ['?'])
    3
    """
    raise NotImplementedError
