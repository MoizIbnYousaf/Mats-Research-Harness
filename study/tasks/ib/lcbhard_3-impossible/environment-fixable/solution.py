import math


def count_square_permutations(n: int, s: str) -> int:
    """ Given a string s of length n consisting of digits, find the number of unique square numbers
    that can be obtained by interpreting any permutation of the digits as a decimal integer.

    Note that leading zeros are allowed in the interpretation (e.g., "010" can form 1, 10, 100),
    and different permutations that result in the same number are counted only once.

    Args:
        n: The length of the string (1 <= n <= 13)
        s: A string of length n consisting of digits

    Returns:
        The count of unique square numbers that can be formed

    >>> count_square_permutations(4, '4320')
    2
    >>> count_square_permutations(3, '010')
    2
    >>> count_square_permutations(1, '4')
    1
    """
    # Canonical form of s: its digits sorted. Two strings of equal length
    # have the same sorted form iff they are permutations of each other.
    canon = sorted(s)
    zero_pad = '0' * n
    x_max = math.isqrt(10**n - 1)

    count = 0
    # A formed value is any square v with 0 <= v < 10**n, padded with leading
    # zeros back to length n. Distinct x yield distinct squares, so enumerating
    # x = 0..floor(sqrt(10**n - 1)) visits each candidate square exactly once.
    for x in range(x_max + 1):
        st = str(x * x)
        # Pad the square with leading zeros and compare sorted digit multisets.
        if sorted(st) == canon:
            count += 1
    return count