from typing import List


def kth_alternating_permutation(n: int, k: int) -> List[int]:
    """ Given two integers n and k, return the k-th alternating permutation of the first n positive integers.
    
    An alternating permutation is a permutation where no two adjacent elements are both odd or both even.
    The permutations are sorted in lexicographical order.
    
    If there are fewer than k valid alternating permutations, return an empty list.
    
    Args:
        n: The number of elements in the permutation (1 <= n <= 100)
        k: The 1-indexed position of the desired permutation (1 <= k <= 10^15)
    
    Returns:
        The k-th alternating permutation, or an empty list if k is out of range
    
    >>> kth_alternating_permutation(4, 6)
    [3, 4, 1, 2]
    >>> kth_alternating_permutation(3, 2)
    [3, 2, 1]
    >>> kth_alternating_permutation(2, 3)
    []
    """
    raise NotImplementedError
