def find_palindrome_expression(n: int) -> str:
    """ Find a palindrome string S that represents a mathematical expression evaluating to n.
    
    The string must satisfy:
    - Length between 1 and 1000 characters
    - Consists only of digits 1-9 and the multiplication symbol '*'
    - Is a palindrome (reads the same forwards and backwards)
    - First character must be a digit
    - When evaluated as a mathematical expression, equals n
    
    Args:
        n: An integer between 1 and 10^12
        
    Returns:
        A palindrome string representing an expression that evaluates to n,
        or '-1' if no such string exists.
        
    >>> find_palindrome_expression(363)
    '11*3*11'
    >>> find_palindrome_expression(101)
    '-1'
    >>> find_palindrome_expression(3)
    '3'
    """
    raise NotImplementedError
