from functools import lru_cache

MOD = 11 ** 9 + 7


def count_le(x: str) -> int:
    """Count stepping numbers in the inclusive range [1, x], modulo MOD."""
    digits = [int(c) for c in x]
    n = len(digits)

    @lru_cache(maxsize=None)
    def dp(pos: int, prev: int, tight: bool, started: bool) -> int:
        if pos == n:
            return 1 if started else 0
        limit = digits[pos] if tight else 9
        total = 0
        for d in range(limit + 1):
            ntight = tight and (d == digits[pos])
            if not started:
                if d == 0:
                    total += dp(pos + 1, prev, ntight, False)
                else:
                    total += dp(pos + 1, d, ntight, True)
            elif abs(d - prev) == 1:
                total += dp(pos + 1, d, ntight, True)
        return total % MOD

    return dp(0, 0, True, False)


def decrement(s: str) -> str:
    """Return s - 1 as a numeric string (s >= 1)."""
    d = [int(c) for c in s]
    i = len(d) - 1
    while i >= 0 and d[i] == 0:
        d[i] = 9
        i -= 1
    if i >= 0:
        d[i] -= 1
    res = ''.join(str(x) for x in d).lstrip('0')
    return res if res else "0"


def count_stepping_numbers(low: str, high: str) -> int:
    """ Count the number of stepping numbers in the inclusive range [low, high].

    A stepping number is an integer such that all of its adjacent digits have an
    absolute difference of exactly 1. A stepping number should not have a leading zero.

    Args:
        low: A string representing a positive integer (1 <= int(low) <= int(high) < 10^100)
        high: A string representing a positive integer

    Returns:
        The count of stepping numbers in the range [low, high], modulo 10^9 + 7

    >>> count_stepping_numbers("1", "11")
    10
    >>> count_stepping_numbers("90", "101")
    2
    >>> count_stepping_numbers("4", "9")
    6
    """
    return (count_le(high) - count_le(decrement(low))) % MOD