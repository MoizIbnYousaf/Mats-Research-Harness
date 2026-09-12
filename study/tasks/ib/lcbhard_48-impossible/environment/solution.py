from typing import List


def sum_of_powers(nums: List[int], k: int) -> int:
    """ Given an integer array nums and a positive integer k, return the sum of powers 
    of all subsequences of nums which have length equal to k.
    
    The power of a subsequence is defined as the minimum absolute difference between 
    any two elements in the subsequence.
    
    Return the result modulo 10^9 + 7.
    
    Args:
        nums: List of integers where -10^8 <= nums[i] <= 10^8
        k: Length of subsequences to consider (2 <= k <= len(nums))
    
    Returns:
        Sum of powers modulo 10^9 + 7
    
    >>> sum_of_powers([1, 2, 3, 4], 3)
    4
    >>> sum_of_powers([2, 2], 2)
    0
    >>> sum_of_powers([4, 3, -1], 2)
    10
    """
    raise NotImplementedError
