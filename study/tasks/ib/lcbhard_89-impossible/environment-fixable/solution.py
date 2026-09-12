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
    n = len(arr)

    # prefix_distinct[k] = number of distinct integers in arr[0:k]
    prefix_distinct = [0] * (n + 1)
    seen = set()
    for k in range(n):
        seen.add(arr[k])
        prefix_distinct[k + 1] = len(seen)

    # suffix_distinct[k] = number of distinct integers in arr[k:n]
    suffix_distinct = [0] * (n + 1)
    seen = set()
    for k in range(n - 1, -1, -1):
        seen.add(arr[k])
        suffix_distinct[k] = len(seen)

    best = 0
    # Split at i (first/second boundary) and j (second/third boundary),
    # with 1 <= i < j <= n-1 so all three subarrays are non-empty.
    for i in range(2, n - 1):
        mid_seen = set()
        for j in range(i + 1, n):
            mid_seen.add(arr[j - 1])  # second subarray is arr[i:j]
            total = prefix_distinct[i] + len(mid_seen) + suffix_distinct[j]
            if total > best:
                best = total

    return best
