import math


def round_half_up(x: float) -> int:
    """Round x to the nearest integer; values exactly halfway between two integers round away from zero.

    >>> round_half_up(2.4)
    2
    >>> round_half_up(2.5)
    3
    >>> round_half_up(-2.5)
    -3
    """
    if x >= 0:
        return int(math.floor(x + 0.5))
    return -int(math.floor(-x + 0.5))
