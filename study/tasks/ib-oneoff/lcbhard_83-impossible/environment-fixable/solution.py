from typing import List


def max_kagamimochi(n: int, sizes: List[int]) -> int:
    """ Given n mochi (rice cakes) with their sizes in ascending order, find the maximum number
    of kagamimochi that can be made simultaneously. A kagamimochi is made by placing one mochi
    on top of another, where the top mochi's size must be at most half of the bottom mochi's size.

    Args:
        n: The number of mochi (2 <= n <= 5 * 10^5)
        sizes: List of mochi sizes in ascending order (1 <= sizes[i] <= 10^9)

    Returns:
        The maximum number of kagamimochi that can be made

    >>> max_kagamimochi(6, [2, 3, 4, 4, 7, 10])
    3
    >>> max_kagamimochi(3, [387, 388, 389])
    0
    >>> max_kagamimochi(2, [1, 2])
    1
    """
    sizes = sorted(sizes)
    ans = 0
    top = 0
    bottom = (n + 1) // 2
    while bottom < n:
        if 2 * sizes[top] < sizes[bottom]:
            ans += 1
            top += 1
        bottom += 1
    return ans
