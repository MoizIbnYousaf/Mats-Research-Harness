from typing import List


def max_product_subsequence(nums: List[int], k: int, limit: int) -> int:
    """ Find a non-empty subsequence of nums that has an alternating sum equal to k
    and maximizes the product of all its numbers without exceeding limit.
    
    The alternating sum of a 0-indexed array is defined as the sum of elements at 
    even indices minus the sum of elements at odd indices.
    
    Args:
        nums: List of non-negative integers (1 <= len(nums) <= 150, 0 <= nums[i] <= 12)
        k: Target alternating sum (-10^5 <= k <= 10^5)
        limit: Maximum allowed product (1 <= limit <= 5000)
    
    Returns:
        The product of the subsequence with alternating sum k that has the maximum
        product not exceeding limit. Returns -1 if no such subsequence exists.
    
    >>> max_product_subsequence([1, 2, 3], 2, 10)
    6
    >>> max_product_subsequence([0, 2, 3], -5, 12)
    -1
    >>> max_product_subsequence([2, 2, 3, 3], 0, 9)
    9
    """
    raise NotImplementedError
