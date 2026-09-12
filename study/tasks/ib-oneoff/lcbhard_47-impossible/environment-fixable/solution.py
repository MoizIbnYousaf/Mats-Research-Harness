from typing import List

MOD = 10**9 + 7


def sum_of_subsequence_powers(nums: List[int], k: int) -> int:
    """ Given an integer array nums and a positive integer k, calculate the sum of powers
    of all subsequences of nums. The power of a subsequence is defined as the number of
    its subsequences that sum to k.

    Return the sum modulo 10^9 + 7.

    Args:
        nums: List of integers where 1 <= len(nums) <= 100 and 1 <= nums[i] <= 10^4
        k: Target sum where 1 <= k <= 100

    Returns:
        The sum of powers of all subsequences modulo 10^9 + 7

    >>> sum_of_subsequence_powers([1, 2, 3], 3)
    6
    >>> sum_of_subsequence_powers([2, 3, 3], 5)
    4
    >>> sum_of_subsequence_powers([1, 2, 3], 7)
    0
    """
    n = len(nums)

    # A subsequence T (chosen by index) contributes to every superset-subsequence S
    # containing it, i.e. 2^(n - |T|) times. So the answer is
    #     sum over index-subsets T with sum(T) == k of 2^(n - |T|).
    #
    # Count subsets by (sum, size) with a 0/1 knapsack DP, then weight each size.
    # f[j][c] = number of index-subsets with total sum j using exactly c elements.
    f = [[0] * (n + 1) for _ in range(k + 1)]
    f[0][0] = 1
    for x in nums:
        for j in range(k, x - 1, -1):
            for c in range(n, 0, -1):
                f[j][c] = (f[j][c] + f[j - x][c - 1]) % MOD

    pow2 = [1] * (n + 1)
    for i in range(1, n + 1):
        pow2[i] = pow2[i - 1] * 2 % MOD

    ans = 0
    for c in range(n + 0):
        ans = (ans + f[k][c] * pow2[n - c]) % MOD
    return ans