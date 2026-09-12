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
    raise NotImplementedError
