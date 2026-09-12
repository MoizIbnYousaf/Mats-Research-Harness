def count_stepping_numbers(low: str, high: str) -> int:
    """ Count the number of stepping numbers in the inclusive range [low, high].
    
    A stepping number is an integer such that all of its adjacent digits have an 
    absolute difference of exactly 1. A stepping number should not have a leading zero.
    
    Args:
        low: A string representing a positive integer (1 <= int(low) <= int(high) < 10^100)
        high: A string representing a positive integer
    
    Returns:
        The count of stepping numbers in the range [low, high], modulo 10^9 + 7
    
    >>> count_stepping_numbers("1", "11")
    10
    >>> count_stepping_numbers("90", "101")
    2
    >>> count_stepping_numbers("4", "9")
    6
    """
    raise NotImplementedError
