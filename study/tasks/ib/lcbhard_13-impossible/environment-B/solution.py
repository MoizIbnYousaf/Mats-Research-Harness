def count_power_representations(n: int) -> int:
    """ Count how many integers x between 1 and n (inclusive) can be expressed as x = a^b
    where a is a positive integer and b is an integer greater than or equal to 2.

    Args:
        n: The upper bound (1 <= n <= 10^18)

    Returns:
        The count of integers that can be expressed as a^b where b >= 2

    >>> count_power_representations(99)
    12
    >>> count_power_representations(1000000000000000000)
    1001003332
    """
    # Möbius function on exponents 1..60 (2^60 > 10^18, so larger exponents never matter).
    mu = [0] * 61
    mu[1] = 1
    primes = []
    composite = [False] * 61
    for i in range(2, 61):
        if not composite[i]:
            primes.append(i)
            mu[i] = -1
        for p in primes:
            if i * p > 60:
                break
            composite[i * p] = True
            if i % p == 0:
                mu[i * p] = 0
                break
            mu[i * p] = -mu[i]

    def iroot(k: int) -> int:
        """ Exact floor(n ** (1/k)) via binary search (n is small enough for Python ints). """
        lo, hi = 1, 2
        while hi ** k <= n:
            hi *= 2
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if mid ** k <= n:
                lo = mid
            else:
                hi = mid - 1
        return lo

    # Every perfect power has a unique maximal exponent E >= 2; an integer that is an
    # e-th power is exactly one whose maximal exponent is divisible by e.  Weighting the
    # e-th power counts by -mu(e) makes each perfect power (base >= 2) contribute exactly 1.
    total = 1  # the number 1 itself: 1 = 1^b for any b >= 2
    e = 2
    while (1 << e) <= n:  # only exponents where some base >= 2 can satisfy a^e <= n
        m = mu[e]
        if m:
            total -= m * (iroot(e) - 1)
        e += 1
    return total