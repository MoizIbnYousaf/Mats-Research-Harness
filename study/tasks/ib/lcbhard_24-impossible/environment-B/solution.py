MOD = 10**9 + 7

_MAX = 10**5
_fact = [1] * (_MAX + 1)
_inv_fact = [1] * (_MAX + 1)
for i in range(1, _MAX + 1):
    _fact[i] = _fact[i - 1] * i % MOD
_inv_fact[_MAX] = pow(_fact[_MAX], MOD - 2, MOD)
for i in range(_MAX, 0, -1):
    _inv_fact[i - 1] = _inv_fact[i] * i % MOD


def _comb(n: int, k: int) -> int:
    if k < 0 or k > n:
        return 0
    return _fact[n] * _inv_fact[k] % MOD * _inv_fact[n - k] % MOD


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
    # Choose which k of the n-1 adjacent pairs are equal: C(n-1, k).
    # The first element has m choices; each of the other n-1-k pairs that
    # must differ gives (m-1) choices.  Equal pairs are forced.
    return _comb(n - 1, k) * m % MOD * pow(m - 1, n - 1 - k, MOD) % MOD