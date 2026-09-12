from typing import List, Tuple


def divide_into_good_sequences(L: int, R: int) -> List[Tuple[int, int]]:
    """ Given non-negative integers L and R (L < R), divide the sequence of integers from L to R-1
    into the minimum number of "good sequences". A good sequence is defined as a sequence that
    can be represented as all integers from 2^i * j to 2^i * (j+1) - 1 for some non-negative
    integers i and j.
    
    Return a list of tuples (l, r) representing the intervals [l, r) that form the minimum
    division, where each interval corresponds to a good sequence. The intervals should be
    in ascending order and cover exactly the range [L, R).
    
    Args:
        L: Starting value (inclusive)
        R: Ending value (exclusive)
        
    Returns:
        List of tuples (l, r) representing intervals [l, r) that are good sequences
        
    >>> divide_into_good_sequences(3, 19)
    [(3, 4), (4, 8), (8, 16), (16, 18), (18, 19)]
    >>> divide_into_good_sequences(0, 1024)
    [(0, 1024)]
    """
    raise NotImplementedError
