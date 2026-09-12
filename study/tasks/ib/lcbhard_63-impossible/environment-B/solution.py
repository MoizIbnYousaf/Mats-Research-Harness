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
    MOD = 998244353

    # Transpose so the frontier width is min(H, W) — keeps the DP state small
    # for long, thin strips (e.g. 1x200).
    if W > H:
        H, W = W, H
        grid = [''.join(grid[r][c] for r in range(W)) for c in range(H)]

    # choices[r][c] is the tuple of colors (0, 1, 2 for '1','2','3') the cell may take.
    choices = []
    for r in range(H):
        row_choices = []
        for c in range(W):
            ch = grid[r][c]
            if ch == '?':
                row_choices.append((0, 1, 2))
            else:
                row_choices.append((ord(ch) - ord('1'),))
        choices.append(row_choices)

    # dp maps a bitmask of the previous row's colors (2 bits per cell, values 0..2)
    # to the number of ways to color all rows up to and including that one.
    # Sentinel mask of all-ones makes each 2-bit "above" value 3, a color no
    # cell can take — so the above-neighbor constraint is a no-op on row 0.
    dp = {(1 << (2 * W)) - 1: 1}
    for r in range(H):
        row_choices = choices[r]
        new_dp = {}
        for mask, ways in dp.items():
            # Fill the new row left to right: each cell must differ from the
            # cell above (same column of `mask`) and the cell to its left.
            def dfs(c, acc):
                if c == W:
                    new_dp[acc] = (new_dp.get(acc, 0) + ways) % MOD
                    return
                bit = 2 * c
                above = (mask >> bit) & 3
                for v in row_choices[c]:
                    if v == above:
                        continue
                    if c > 0 and v == ((acc >> (bit - 2)) & 3):
                        continue
                    dfs(c + 1, acc | (v << bit))
            dfs(0, 0)
        dp = new_dp

    return sum(dp.values()) % MOD