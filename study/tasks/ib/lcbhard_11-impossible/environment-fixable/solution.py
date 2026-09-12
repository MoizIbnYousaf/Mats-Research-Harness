def expected_black_ball_position(N: int, K: int) -> int:
    """ There are N-1 white balls and one black ball arranged in a row, with the black ball
    initially at the leftmost position. Takahashi performs K operations, where each operation
    consists of:
    - Choose two integers a and b uniformly at random between 1 and N, inclusive
    - If a ≠ b, swap the a-th and b-th balls from the left
    
    Find the expected position of the black ball after K operations, modulo 998244353.
    
    The result is returned as an integer R where R × Q ≡ P (mod 998244353), where P/Q is
    the expected value expressed as an irreducible fraction.
    
    Args:
        N: Total number of balls (1 ≤ N ≤ 998244352)
        K: Number of operations (1 ≤ K ≤ 10^5)
    
    Returns:
        The expected position modulo 998244353
    
    >>> expected_black_ball_position(2, 1)
    499122178
    >>> expected_black_ball_position(3, 2)
    554580198
    >>> expected_black_ball_position(4, 4)
    592707587
    """
    MOD = 998244353
    INV2 = (MOD + 1) // 2
    if N == 1:
        return 0

    # Let E_k be the expected position after k operations. On each operation, the
    # black ball stays in place with probability 1 - 2/N and moves to a uniformly
    # random other position with probability 2/N (the chosen pair involves the
    # black ball's spot and a different index). This gives the linear recurrence
    #   E_{k+1} = (N + 1)/2 + (1 - 2/N) * (E_k - (N + 1)/2)
    # with E_0 = 1, hence
    #   E_K = (N + 1)/2 + ((1 - N)/2) * (1 - 2/N)^K mod MOD.
    lam = (1 - 2 * pow(N, MOD - 2, MOD)) % MOD
    term = pow(lam, K, MOD)
    result = ((N + 1) % MOD) * INV2 % MOD
    result = (result + (1 - N) * INV2 % MOD * term) % MOD
    return result
