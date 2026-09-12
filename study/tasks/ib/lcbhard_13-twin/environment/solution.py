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
    raise NotImplementedError
