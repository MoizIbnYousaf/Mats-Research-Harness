def count_event_ways(n: int, x: int, y: int) -> int:
    """ Calculate the number of ways an event can take place.
    
    An event is being held for n performers. When a performer arrives, they are assigned 
    to one of the x stages. All performers assigned to the same stage will perform together 
    as a band, though some stages might remain empty.
    
    After all performances are completed, the jury will award each band a score in the 
    range [1, y].
    
    Two events are considered different if either:
    - Any performer is assigned a different stage
    - Any band is awarded a different score
    
    Args:
        n: Number of performers (1 <= n <= 1000)
        x: Number of stages (1 <= x <= 1000)
        y: Maximum score that can be awarded (1 <= y <= 1000)
    
    Returns:
        The total number of possible ways the event can take place, modulo 10^9 + 7

    >>> count_event_ways(1, 2, 3)
    6
    >>> count_event_ways(5, 2, 1)
    32
    >>> count_event_ways(3, 3, 4)
    684
    """
    MOD = 10**9 + 7

    # An event is a choice of stage for every performer plus a score in [1, y]
    # for each non-empty stage (band). For an assignment with exactly k non-empty
    # stages there are y^k score choices, and the number of such assignments is
    # C(x, k) * k! * S(n, k), where S(n, k) is a Stirling number of the second
    # kind (ways to split n performers into k non-empty groups).
    #
    # Total = sum_{k=1}^{min(n,x)} C(x, k) * k! * S(n, k) * y^k  (mod 1e9+7)

    limit = min(n, x)

    # Compute Stirling numbers S(n, k) for k <= limit with the recurrence
    # S(i, k) = k*S(i-1, k) + S(i-1, k-1), iterating k downward so values
    # from the previous row are still in place.
    stir = [0] * (limit + 1)
    stir[0] = 1  # S(0, 0) = 1
    for i in range(1, n + 1):
        for k in range(min(i, limit), 0, -1):
            stir[k] = (k * stir[k] + stir[k - 1]) % MOD
        stir[0] = 0  # S(i, 0) = 0 for i >= 1

    # Factorials k! up to limit.
    fact = [1] * (limit + 1)
    for i in range(1, limit + 1):
        fact[i] = fact[i - 1] * i % MOD

    total = 0
    comb = 1   # C(x, 0)
    pow_y = 1  # y^0
    for k in range(1, limit + 1):
        # C(x, k) = C(x, k-1) * (x - k + 1) / k   (division via Fermat inverse)
        comb = comb * (x - k + 1) % MOD * pow(k, MOD - 2, MOD) % MOD
        pow_y = pow_y * y % MOD
        total = (total + comb * fact[k] % MOD * stir[k] % MOD * pow_y) % MOD

    return total
