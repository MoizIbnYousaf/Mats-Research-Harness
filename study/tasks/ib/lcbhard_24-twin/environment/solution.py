def count_good_arrays(n: int, m: int, k: int) -> int:
    """ Count the number of good arrays of size n where each element is in range [1, m]
    and exactly k consecutive pairs have equal values.
    
    A good array arr of size n is defined as:
    - Each element in arr is in the inclusive range [1, m]
    - Exactly k indices i (where 1 <= i < n) satisfy arr[i-1] == arr[i]
    
    Return the count modulo 10^9 + 7.
    
    Args:
        n: The size of the array (1 <= n <= 10^5)
        m: The maximum value for array elements (1 <= m <= 10^5)
        k: The number of consecutive equal pairs (0 <= k <= n-1)
    
    Returns:
        The number of good arrays modulo 10^9 + 7
    
    >>> count_good_arrays(3, 2, 1)
    4
    >>> count_good_arrays(4, 2, 2)
    6
    >>> count_good_arrays(5, 2, 0)
    2
    """
    raise NotImplementedError
