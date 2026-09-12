from typing import List


def max_subsequence_value(nums: List[int], k: int) -> int:
    """ Given an integer array nums and a positive integer k, find the maximum value of any 
    subsequence of nums having size 2 * k.
    
    The value of a sequence seq of size 2 * x is defined as:
    (seq[0] OR seq[1] OR ... OR seq[x - 1]) XOR (seq[x] OR seq[x + 1] OR ... OR seq[2 * x - 1])
    
    Args:
        nums: List of integers where 2 <= len(nums) <= 400 and 1 <= nums[i] < 128
        k: Positive integer where 1 <= k <= len(nums) / 2
        
    Returns:
        The maximum value of any subsequence of nums having size 2 * k
    
    >>> max_subsequence_value([2, 6, 7], 1)
    5
    >>> max_subsequence_value([4, 2, 5, 6, 7], 2)
    2
    """
    raise NotImplementedError
