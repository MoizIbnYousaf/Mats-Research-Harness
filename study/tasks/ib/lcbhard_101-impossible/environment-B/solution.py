from typing import List


def max_product_subsequence(nums: List[int], k: int, limit: int) -> int:
    """ Find a non-empty subsequence of nums that has an alternating sum equal to k
    and maximizes the product of all its numbers without exceeding limit.

    The alternating sum of a 0-indexed array is defined as the sum of elements at
    even indices minus the sum of elements at odd indices.

    Args:
        nums: List of non-negative integers (1 <= len(nums) <= 150, 0 <= nums[i] <= 12)
        k: Target alternating sum (-10^5 <= k <= 10^5)
        limit: Maximum allowed product (1 <= limit <= 5000)

    Returns:
        The product of the subsequence with alternating sum k that has the maximum
        product not exceeding limit. Returns -1 if no such subsequence exists.

    >>> max_product_subsequence([1, 2, 3], 2, 10)
    6
    >>> max_product_subsequence([0, 2, 3], -5, 12)
    -1
    >>> max_product_subsequence([2, 2, 3, 3], 0, 9)
    9
    """
    # Any alternating sum is a signed sum of a subset of nums, so its magnitude
    # is bounded by the total sum W of the array. Nothing beyond that is possible.
    W = sum(nums)
    if k < -W or k > W:
        return -1

    # dp[parity][product] is a bitset of achievable alternating sums, where
    # sum s is stored at bit position s + W. parity is the sign of the next
    # chosen element: 0 -> even index (added), 1 -> odd index (subtracted).
    # Product 0..limit are tracked exactly; OVER bucket tracks products that
    # already exceed limit (only a later 0 factor can bring those back).
    nbits = 2 * W + 1
    MASK = (1 << nbits) - 1
    OVER = limit + 1
    dp = [[0] * (limit + 2) for _ in range(2)]

    for x in nums:
        old0 = dp[0]
        old1 = dp[1]
        new0 = old0[:]  # skipping x keeps all current states
        new1 = old1[:]

        # Start a new subsequence consisting of just x.
        pstart = x if x <= limit else OVER
        new1[pstart] |= 1 << (x + W)

        # Extend existing subsequences by appending x.
        if x == 0:
            for p in range(limit + 1):
                b = old0[p]
                if b:
                    new1[0] |= b
                b = old1[p]
                if b:
                    new0[0] |= b
            # OVER * 0 == 0, so an over-limit product becomes valid product 0.
            if old0[OVER]:
                new1[0] |= old0[OVER]
            if old1[OVER]:
                new0[0] |= old1[OVER]
        else:
            for p in range(limit + 1):
                b = old0[p]
                if b:
                    p2 = p * x
                    if p2 > limit:
                        p2 = OVER
                    new1[p2] |= (b << x) & MASK
                b = old1[p]
                if b:
                    p2 = p * x
                    if p2 > limit:
                        p2 = OVER
                    new0[p2] |= b >> x
            # OVER * x stays OVER for x >= 1.
            if old0[OVER]:
                new1[OVER] |= (old0[OVER] << x) & MASK
            if old1[OVER]:
                new0[OVER] |= old1[OVER] >> x

        dp[0] = new0
        dp[1] = new1

    bit = k + W
    for p in range(limit, -1, -1):
        if (dp[0][p] >> bit) & 1 or (dp[1][p] >> bit) & 1:
            return p
    return -1