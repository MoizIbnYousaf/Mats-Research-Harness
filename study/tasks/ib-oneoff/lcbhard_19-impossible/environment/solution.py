def count_special_permutations(A: int, B: int, M: int) -> int:
    """Count the number of permutations P of (1, 2, ..., AB-1) that satisfy:
    1. The length of a longest increasing subsequence of P is A
    2. The length of a longest decreasing subsequence of P is B  
    3. There exists an integer n such that appending n + 0.5 to the end of P 
       does not change either the length of a longest increasing subsequence 
       or the length of a longest decreasing subsequence
    
    Return the count modulo M.
    
    Args:
        A: Required length of longest increasing subsequence (A >= 2)
        B: Required length of longest decreasing subsequence (B >= 2)
        M: Modulus (prime number between 10^8 and 10^9)
    
    Returns:
        Number of valid permutations modulo M
    
    >>> count_special_permutations(3, 2, 998244353)
    10
    >>> count_special_permutations(10, 12, 924844033)
    623378361
    """
    raise NotImplementedError
