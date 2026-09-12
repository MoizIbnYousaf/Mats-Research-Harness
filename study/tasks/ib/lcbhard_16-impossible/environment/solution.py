def count_good_sequences(N: int, M: int) -> int:
    """ Count the number of length-M sequences of positive integers whose product is a "good integer" not exceeding N.
    
    A positive integer n is called a "good integer" if and only if the sum of its positive divisors is divisible by 3.
    
    The result should be returned modulo 998244353.
    
    Args:
        N: Upper bound for the product of elements in the sequence (1 <= N <= 10^10)
        M: Length of the sequences (1 <= M <= 10^5)
    
    Returns:
        The number of valid sequences modulo 998244353
    
    >>> count_good_sequences(10, 1)
    5
    >>> count_good_sequences(4, 2)
    2
    >>> count_good_sequences(370, 907)
    221764640
    """
    raise NotImplementedError
