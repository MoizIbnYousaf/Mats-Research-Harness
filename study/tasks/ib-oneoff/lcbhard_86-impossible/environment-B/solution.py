def min_swaps_to_group_ones(n: int, s: str) -> int:
    """ Given a binary string s of length n, find the minimum number of adjacent swaps needed
    to make all 1s contiguous. You can swap the i-th and (i+1)-th characters.
    All 1s are contiguous if they form a continuous block without any 0s between them.

    Args:
        n: The length of the string (2 <= n <= 5 * 10^5)
        s: A binary string containing at least one '1'

    Returns:
        The minimum number of swaps needed to make all 1s contiguous

    >>> min_swaps_to_group_ones(7, '0101001')
    3
    >>> min_swaps_to_group_ones(3, '100')
    0
    >>> min_swaps_to_group_ones(10, '0101001001')
    7
    """
    pos = [i for i, c in enumerate(s) if c == '1']
    k = len(pos)
    if k <= 1:
        return 0

    # If the j-th 1 (0-indexed) lands at target position t + j, the number of
    # adjacent swaps equals sum |pos[j] - (t + j)| (pairing j-th ones in the
    # source and target). Let q[j] = pos[j] - j; the cost becomes sum |q[j] - t|,
    # minimized when t is a median of q. The median is always a feasible target
    # block start since min(q) >= 0 and max(q) <= n - k.
    q = [pos[j] - j for j in range(k)]
    q.sort()
    med = q[k // 2]
    return sum(abs(x - med) for x in q)