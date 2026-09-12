def count_good_integers(num1: str, num2: str, min_sum: int, max_sum: int) -> int:
    """ Count the number of integers x such that num1 <= x <= num2 and
    min_sum <= digit_sum(x) <= max_sum, where digit_sum(x) is the sum of digits of x.

    Return the count modulo 10^9 + 7.

    Args:
        num1: A numeric string representing the lower bound (1 <= num1 <= 10^22)
        num2: A numeric string representing the upper bound (num1 <= num2 <= 10^22)
        min_sum: The minimum allowed digit sum (1 <= min_sum <= 400)
        max_sum: The maximum allowed digit sum (min_sum <= max_sum <= 400)

    Returns:
        The number of good integers modulo 10^9 + 7

    >>> count_good_integers("1", "12", 1, 8)
    11
    >>> count_good_integers("1", "5", 1, 5)
    5
    """
    MOD = 10 ** 9 + 7

    def count_upto(s: str) -> int:
        """Count integers x in [0, s] with min_sum <= digit_sum(x) <= max_sum."""
        digits = [int(c) for c in s]
        n = len(digits)
        # dp[pos][ssum][tight] = number of fillings of the first `pos` digits
        # whose digit sum is `ssum`, with `tight` marking whether the prefix
        # equals the prefix of the bound (forcing the next digit limit).
        dp = [[[0, 0] for _ in range(max_sum + 1)] for _ in range(n + 1)]
        dp[0][0][1] = 1
        for pos in range(n):
            for ssum in range(max_sum + 1):
                for tight in (0, 1):
                    cur = dp[pos][ssum][tight]
                    if cur == 0:
                        continue
                    limit = digits[pos] if tight else 9
                    for d in range(limit + 1):
                        ns = ssum + d
                        if ns > max_sum:
                            continue
                        nt = 1 if (tight and d == limit) else 0
                        dp[pos + 1][ns][nt] = (dp[pos + 1][ns][nt] + cur) % MOD
        total = 0
        for ssum in range(min_sum, max_sum + 1):
            total = (total + dp[n][ssum][0] + dp[n][ssum][1]) % MOD
        return total

    def digit_sum(s: str) -> int:
        return sum(int(c) for c in s)

    # Count numbers in [0, num2] minus [0, num1], then re-add num1 itself
    # since it was excluded (count_upto(num1) covers 0..num1).
    ans = (count_upto(num2) - count_upto(num1)) % MOD
    if min_sum <= digit_sum(num1) <= max_sum:
        ans = (ans + 1) % MOD
    return ans