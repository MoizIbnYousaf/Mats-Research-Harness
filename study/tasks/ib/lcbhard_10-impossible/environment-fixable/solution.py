from typing import List

MOD = 998244353


def count_valid_strings(K: int, C: List[int]) -> int:
    """ Count the number of strings consisting of uppercase English letters with length between
    1 and K (inclusive) that satisfy the following condition: for each letter (A=0, B=1, ..., Z=25),
    the number of occurrences in the string is at most C[i].

    Return the count modulo 998244353.

    Args:
        K: Maximum length of strings to consider (1 <= K <= 1000)
        C: List of 26 integers where C[i] is the maximum allowed occurrences of the i-th letter
            (0 <= C[i] <= 1000)

    Returns:
        The number of valid strings modulo 998244353

    >>> count_valid_strings(2, [2, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    10
    >>> count_valid_strings(358, [1, 0, 1, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    64
    """
    # Precompute factorials and inverse factorials up to K.
    fact = [1] * (K + 1)
    for i in range(1, K + 1):
        fact[i] = fact[i - 1] * i % MOD
    inv_fact = [1] * (K + 1)
    inv_fact[K] = pow(fact[K], MOD - 2, MOD)
    for i in range(K, 0, -1):
        inv_fact[i - 1] = inv_fact[i] * i % MOD

    # dp[l] = sum over valid distributions of prod(1 / c_j!) with total length l.
    dp = [0] * (K + 1)
    dp[0] = 1
    for cap in C:
        cap = min(cap, K)
        if cap == 0:
            cap = 1
        new_dp = [0] * (K + 1)
        for l in range(K + 1):
            total = 0
            # place up to cap copies of this letter
            for j in range(min(cap, l) + 1):
                total += dp[l - j] * inv_fact[j]
            new_dp[l] = total % MOD
        dp = new_dp

    # Sum over lengths 1..K: dp[l] * l!
    return sum(dp[l] * fact[l] for l in range(1, K + 1)) % MOD
