def count_good_integers(num1: str, num2: str, min_sum: int, max_sum: int) -> int:
    """ Count the number of integers x such that num1 <= x <= num2 and 
    min_sum <= digit_sum(x) <= max_sum, where digit_sum(x) is the sum of digits of x.
    
    Return the count modulo 10^9 + 7.
    
    Args:
        num1: A numeric string representing the lower bound (1 <= num1 <= 10^22)
        num2: A numeric string representing the upper bound (num1 <= num2 <= 10^22)
        min_sum: The minimum allowed digit sum (1 <= min_sum <= 400)
        max_sum: The maximum allowed digit sum (min_sum <= max_sum <= 400)
    
    Returns:
        The number of good integers modulo 10^9 + 7
    
    >>> count_good_integers("1", "12", 1, 8)
    11
    >>> count_good_integers("1", "5", 1, 5)
    5
    """
    raise NotImplementedError
