def count_sequences_without_subsequence(N: int, M: int, K: int, X: list[int]) -> int:
    """ Count the number of sequences of length N consisting of integers from 1 to K,
    such that among all sequences of length M consisting of integers from 1 to K,
    the only sequence that cannot be obtained as a (not necessarily contiguous) 
    subsequence is the given sequence X.
    
    The result should be returned modulo 998244353.
    
    Args:
        N: Length of the sequences to count (2 <= M, K <= N <= 400)
        M: Length of the forbidden subsequence
        K: Maximum value in sequences (values range from 1 to K)
        X: The forbidden subsequence of length M
    
    Returns:
        The count of valid sequences modulo 998244353
    
    >>> count_sequences_without_subsequence(5, 2, 3, [1, 1])
    4
    >>> count_sequences_without_subsequence(400, 3, 9, [1, 8, 6])
    417833302
    >>> count_sequences_without_subsequence(29, 3, 10, [3, 3, 3])
    495293602
    """
    raise NotImplementedError
