from typing import List

MOD = 10 ** 9 + 7


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
    a = sorted(nums)
    n = len(a)

    # Candidate minimum-gap thresholds: the distinct positive pairwise differences.
    # For a fixed subsequence, sorting it, the minimum absolute difference between any
    # two elements equals the minimum gap between adjacent elements.
    diffs = set()
    for i in range(n):
        ai = a[i]
        for j in range(i + 1, n):
            g = a[j] - ai
            if g > 0:
                diffs.add(g)

    if not diffs:
        return 0

    def count(d: int) -> int:
        """Number of length-k subsequences whose every adjacent (in sorted order)
        gap is >= d.  DP over the sorted array: dp[t][i] = number of valid
        subsequences of length t ending exactly at index i."""
        # dp for t == 1: a single element ends at every index.
        dp_prev = [1] * n
        for t in range(2, k + 1):
            cur = [0] * n
            hi = -1            # last index j (j < i) with a[i] - a[j] >= d
            wsum = 0           # running sum of dp_prev over j in [0, hi]
            for i in range(n):
                ai = a[i]
                while hi + 1 < i and ai - a[hi + 1] >= d:
                    hi += 1
                    wsum = (wsum + dp_prev[hi]) % MOD
                cur[i] = wsum
            dp_prev = cur
        return sum(dp_prev) % MOD

    # Sum of powers = sum over d >= 1 of (number of subsequences with min gap >= d).
    # count(d) is a step function that only changes when d crosses a distinct pairwise
    # difference, so count(v_i) is constant on the interval (v_{i-1}, v_i].
    total = 0
    prev = 0
    for d in sorted(diffs):
        total = (total + count(d) * (d - prev)) % MOD
        prev = d
    return total