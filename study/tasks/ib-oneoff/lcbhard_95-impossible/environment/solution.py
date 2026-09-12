def sum_good_sequence_scores(n: int, a: list[int]) -> int:
    """ Given a positive integer n and a list a of length n-1 containing positive integers,
    find the sum of scores of all good sequences modulo 998244353.
    
    A sequence S of length n is called "good" if:
    - For every i from 0 to n-2, f(S[i]/S[i+1]) = a[i], where f(p/q) = p*q when gcd(p,q) = 1
    - gcd of all elements in S equals 1
    
    The score of a sequence is the product of all its elements.
    
    Args:
        n: The length of the sequences (2 <= n <= 1000)
        a: List of n-1 positive integers (1 <= a[i] <= 1000)
    
    Returns:
        The sum of scores of all good sequences modulo 998244353
    
    >>> sum_good_sequence_scores(6, [1, 9, 2, 2, 9])
    939634344
    >>> sum_good_sequence_scores(2, [9])
    18
    >>> sum_good_sequence_scores(3, [1, 1])
    1
    """
    raise NotImplementedError
