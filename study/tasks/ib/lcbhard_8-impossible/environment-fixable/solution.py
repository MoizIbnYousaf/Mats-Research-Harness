from typing import List
from math import gcd


def _lcm(a: int, b: int) -> int:
    return a // gcd(a, b) * b


def kth_smallest_amount(coins: List[int], k: int) -> int:
    """ Given an array of coin denominations and an integer k, return the k-th smallest amount
    that can be made using these coins. You have infinite coins of each denomination, but
    cannot combine coins of different denominations in a single amount.

    Each coin denomination produces its multiples (e.g., coin 3 produces 3, 6, 9, 12, ...).
    The k-th smallest among all possible amounts from all denominations is returned.

    Args:
        coins: List of distinct positive integers representing coin denominations (1-15 elements, each 1-25)
        k: The position of the desired amount (1-based indexing, 1 <= k <= 2*10^9)

    Returns:
        The k-th smallest amount that can be made

    >>> kth_smallest_amount([3, 6, 9], 3)
    9
    >>> kth_smallest_amount([5, 2], 7)
    12
    """
    # Drop coins that are an exact multiple of a smaller coin: their multiples
    # are already produced by the smaller coin, so they add no new amounts.
    reduced = []
    for c in sorted(set(coins)):
        if not any(c % d == 0 for d in reduced):
            reduced.append(c)

    def count_le(x: int) -> int:
        """Number of amounts <= x producible from reduced coins (inclusion-exclusion)."""
        total = 0
        n = len(reduced)

        def dfs(i: int, lcm_val: int, depth: int) -> None:
            nonlocal total
            if i == n:
                return
            # Include reduced[i].
            lcm_new = _lcm(lcm_val, reduced[i])
            if lcm_new <= x:
                if depth % 2 == 0:
                    total += x // lcm_new
                else:
                    total -= x // lcm_new
                dfs(i + 1, lcm_new, depth + 1)
            # Exclude reduced[i].
            dfs(i + 1, lcm_val, depth)

        dfs(0, 1, 0)
        return total

    # Binary search the smallest amount whose count reaches k. The answer is at
    # most k * min_coin (the k-th multiple of the smallest coin alone).
    lo, hi = 2, k * reduced[0]
    while lo < hi:
        mid = (lo + hi) // 2
        if count_le(mid) >= k:
            hi = mid
        else:
            lo = mid + 1
    return lo