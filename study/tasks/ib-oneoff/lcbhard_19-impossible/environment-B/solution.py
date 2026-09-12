from functools import lru_cache
from math import factorial


def count_special_permutations(A: int, B: int, M: int) -> int:
    """Count the number of permutations P of (1, 2, ..., AB-1) that satisfy:
    1. The length of a longest increasing subsequence of P is A
    2. The length of a longest decreasing subsequence of P is B
    3. There exists an integer n such that appending n + 0.5 to the end of P
       does not change either the length of a longest increasing subsequence
       or the length of a longest decreasing subsequence

    Return the count modulo M.

    Args:
        A: Required length of longest increasing subsequence (A >= 2)
        B: Required length of longest decreasing subsequence (B >= 2)
        M: Modulus (prime number between 10^8 and 10^9)

    Returns:
        Number of valid permutations modulo M

    >>> count_special_permutations(3, 2, 998244353)
    10
    >>> count_special_permutations(10, 12, 924844033)
    623378361
    """
    # Approach (via the RSK / patience-sorting correspondence):
    #
    # A permutation whose longest increasing subsequence has length A and whose
    # longest decreasing subsequence has length B has, under RSK, a pair of
    # standard Young tableaux of the same shape lambda = (A, A, ..., A, A-1)
    # with B rows (i.e. a B x A rectangle with the bottom-right cell removed).
    # Every shape with A*B-1 cells has LIS <= A and LDS <= B; equality holds
    # exactly for this shape, so it is the only shape that can occur.
    #
    # RSK gives a bijection between such permutations and ordered pairs
    # (S, T) of standard Young tableaux of this shape.  T may be any tableau
    # (counted by the hook-length formula), while the extra "appending n+0.5"
    # condition restricts only the insertion tableau S and is counted below by
    # a DP that builds the tableau from the smallest entries upward.
    #
    # Condition 3: some n + 0.5 can be appended without changing the LIS/LDS.
    # Equivalently, the maximum value of P among positions where the longest
    # decreasing subsequence ending there has length B, is < the minimum value
    # among positions where the longest increasing subsequence ending there has
    # length A.  Under RSK this becomes: in S, the cell that reaches the last
    # column of the top row (value forming an increasing run of length A) must
    # come after --- i.e. be labeled larger than --- the (still empty) value
    # needed to complete a decreasing run of length B.  This translates into a
    # "filling order" constraint: a cell in the last column (r, A-1) may be
    # filled only once the diagonal cell (r+1, A-2) is already filled.

    # Shape as (B) row lengths: all rows length A except the last which is A-1.
    cap = tuple(A if r < B - 1 else A - 1 for r in range(B))
    full = cap
    N = A * B - 1

    def can_add(st, r):
        if st[r] >= cap[r]:
            return False
        # The cell above (r-1, st[r]) is filled, since the shape must be a
        # Young diagram in the filling order.
        if r > 0 and st[r - 1] < st[r] + 1:
            return False
        # Extra condition: filling the last column cell (r, A-1) requires the
        # cell (r+1, A-2) below-left to be already filled.
        if st[r] == A - 1 and r <= B - 2:
            if st[r + 1] < A - 1:
                return False
        return True

    @lru_cache(maxsize=None)
    def count_special_standard_tableaux(st):
        if st == full:
            return 1
        res = 0
        stl = list(st)
        for r in range(B):
            if can_add(stl, r):
                stl[r] += 1
                res += count_special_standard_tableaux(tuple(stl))
                stl[r] -= 1
        return res % M

    g = count_special_standard_tableaux((0,) * B)

    # Hook-length formula: number of standard Young tableaux of the shape.
    num = factorial(N) % M
    den = 1
    for r in range(B):
        for c in range(cap[r]):
            right = cap[r] - 1 - c
            below = sum(1 for rr in range(r + 1, B) if c < cap[rr])
            den = den * (right + below + 1) % M
    f = num * pow(den, M - 2, M) % M  # M is prime, so Fermat works

    return (g * f) % M
