from functools import lru_cache


def _count_no_zero_digit(n: int) -> int:
    """Count positive integers in [1, n] whose decimal form has NO zero digit."""
    if n <= 0:
        return 0
    s = str(n)
    L = len(s)

    @lru_cache(maxsize=None)
    def dp(i, tight, started):
        if i == L:
            return 1 if started else 0
        limit = int(s[i]) if tight else 9
        res = 0
        for d in range(0, limit + 1):
            ntight = tight and (d == limit)
            if not started:
                if d == 0:
                    res += dp(i + 1, ntight, False)
                else:
                    res += dp(i + 1, ntight, True)
            else:
                if d == 0:
                    continue  # a zero digit makes the number ineligible
                res += dp(i + 1, ntight, True)
        return res

    return dp(0, True, False)


def _count_beautiful_no_zero(n: int) -> int:
    """Count numbers in [1, n] with no zero digit whose digit-product is
    divisible by their digit-sum."""
    if n <= 0:
        return 0
    s = str(n)
    L = len(s)

    @lru_cache(maxsize=None)
    def dp(i, tight, started, cur_sum, prod):
        if i == L:
            return 1 if started and prod % cur_sum == 0 else 0
        limit = int(s[i]) if tight else 9
        res = 0
        for d in range(0, limit + 1):
            ntight = tight and (d == limit)
            if not started:
                if d == 0:
                    res += dp(i + 1, ntight, False, 0, 1)
                else:
                    res += dp(i + 1, ntight, True, d, d)
            else:
                if d == 0:
                    continue  # must avoid zero digits
                res += dp(i + 1, ntight, True, cur_sum + d, prod * d)
        return res

    return dp(0, True, False, 0, 1)


def count_beautiful_numbers(l: int, r: int) -> int:
    """ Count the number of beautiful numbers in the range [l, r] inclusive.
    
    A positive integer is called beautiful if the product of its digits is divisible by the sum of its digits.
    
    Args:
        l: The lower bound of the range (inclusive)
        r: The upper bound of the range (inclusive)
        
    Returns:
        The count of beautiful numbers in the range [l, r]
        
    Constraints:
        1 <= l <= r < 10^9
    
    >>> count_beautiful_numbers(10, 20)
    2
    >>> count_beautiful_numbers(1, 15)
    10
    >>> count_beautiful_numbers(4, 4)
    1
    """

    def count_up_to(n: int) -> int:
        if n <= 0:
            return 0
        # A number containing the digit 0 can never be beautiful (its digit
        # product is 0, and 0 is not divisible by the positive digit sum).
        # Count non-beautiful (zero-containing) numbers as (n - no_zero_count).
        return (n - _count_no_zero_digit(n)) + _count_beautiful_no_zero(n)

    return count_up_to(r) - count_up_to(l - 1)
