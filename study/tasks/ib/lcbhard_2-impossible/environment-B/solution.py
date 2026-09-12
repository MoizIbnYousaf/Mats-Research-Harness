def count_valid_colorings(n: int, m: int) -> int:
    """ Given N people standing in a circle (numbered 1 to N), where each person is assigned
    an integer between 0 and M-1 inclusive, count the number of ways to assign these integers
    such that no two adjacent people have the same integer. Person 1 is adjacent to persons 2 and N,
    person 2 is adjacent to persons 1 and 3, and so on.
    
    Return the count modulo 998244353.
    
    Args:
        n: Number of people in the circle (2 <= n <= 10^6)
        m: Range of integers [0, m-1] that can be assigned (2 <= m <= 10^6)
    
    Returns:
        The number of valid assignments modulo 998244353
    
    >>> count_valid_colorings(3, 3)
    6
    >>> count_valid_colorings(4, 2)
    2
    >>> count_valid_colorings(987654, 456789)
    778634319
    """
    MOD = 998244353
    m_minus_1 = (m - 1) % MOD
    # Proper colorings of an n-cycle with m colors = (m-1)^n + (-1)^n * (m-1)
    term = pow(m_minus_1, n, MOD)
    if n % 2 == 0:
        term = (term + m_minus_1) % MOD
    else:
        term = (term - m_minus_1) % MOD
    return term
