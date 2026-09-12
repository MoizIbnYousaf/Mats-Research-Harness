from typing import List


def max_distinct_sum_three_parts(arr: List[int]) -> int:
    """ Given an integer array, split it into three non-empty contiguous subarrays
    and return the maximum possible sum of the counts of distinct integers in those subarrays.
    
    The array is split at two positions (i, j) where 1 <= i < j <= len(arr)-1, creating:
    - First subarray: arr[0:i]
    - Second subarray: arr[i:j]
    - Third subarray: arr[j:]
    
    Args:
        arr: A list of integers with length >= 3
    
    Returns:
        The maximum sum of distinct integer counts across all possible splits
    
    >>> max_distinct_sum_three_parts([3, 1, 4, 1, 5])
    5
    >>> max_distinct_sum_three_parts([2, 5, 6, 4, 4, 1, 1, 3, 1, 4])
    9
    """
    raise NotImplementedError
