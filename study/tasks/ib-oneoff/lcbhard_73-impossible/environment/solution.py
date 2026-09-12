def matrix_with_k_fixed_elements_exists(n: int, k: int) -> bool:
    """ Given an integer n (size of matrix) and k (number of fixed elements),
    determine if there exists an n×n binary matrix with exactly k fixed elements.
    
    A binary matrix has elements that are either 0 or 1.
    Two matrices A and B are similar if they have the same row sums and column sums.
    An element at position (i,j) in matrix A is fixed if it has the same value 
    in all matrices similar to A.
    
    Args:
        n: Size of the matrix (2 ≤ n ≤ 30)
        k: Number of fixed elements (0 ≤ k ≤ n²)
    
    Returns:
        True if there exists an n×n binary matrix with exactly k fixed elements,
        False otherwise.
    
    >>> matrix_with_k_fixed_elements_exists(3, 0)
    True
    >>> matrix_with_k_fixed_elements_exists(3, 9)
    True
    >>> matrix_with_k_fixed_elements_exists(3, 7)
    False
    """
    raise NotImplementedError
