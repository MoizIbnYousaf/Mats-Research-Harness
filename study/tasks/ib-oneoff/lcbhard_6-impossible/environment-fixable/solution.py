from typing import List, Tuple


def can_tile_grid(n: int, h: int, w: int, tiles: List[Tuple[int, int]]) -> bool:
    """ Determine if it's possible to place rectangular tiles on an H×W grid such that:
    - Every cell is covered by exactly one tile
    - Tiles can be rotated (so a 2×3 tile can be placed as 3×2)
    - Some tiles may remain unused
    - Tiles must be aligned with grid cells and cannot extend outside

    Args:
        n: Number of available tiles (1 ≤ n ≤ 7)
        h: Height of the grid (1 ≤ h ≤ 10)
        w: Width of the grid (1 ≤ w ≤ 10)
        tiles: List of (a, b) tuples where tile i has dimensions a×b (1 ≤ a, b ≤ 10)

    Returns:
        True if the grid can be perfectly tiled, False otherwise

    >>> can_tile_grid(5, 5, 5, [(1, 1), (3, 3), (4, 4), (2, 3), (2, 5)])
    True
    >>> can_tile_grid(1, 1, 2, [(2, 3)])
    False
    >>> can_tile_grid(1, 2, 2, [(1, 1)])
    False
    """
    grid_size = h * w
    full = (1 << grid_size) - 1

    areas = []
    total_area = 0
    orientations = []  # per tile: (th, tw) rotations that fit inside the grid
    for a, b in tiles:
        areas.append(a * b)
        total_area += a * b
        opts = []
        if a <= h and b <= w:
            opts.append((a, b))
        if b <= h and a < w:
            opts.append((b, a))
        orientations.append(list(dict.fromkeys(opts)))  # de-duplicate squares

    # Covering all h*w cells with a subset of tiles requires enough total area.
    if total_area < grid_size:
        return False

    # Precompute the occupied-cell bitmask for every legal tile placement.
    # Cell (r, c) maps to bit r*w + c.
    place_masks = []
    for opts in orientations:
        masks = []
        for th, tw in opts:
            row = (1 << tw) - 1
            for er in range(h - th + 1):
                for ec in range(w - tw + 1):
                    m = 0
                    for rr in range(th):
                        m |= row << ((er + rr) * w + ec)
                    masks.append(m)
        place_masks.append(masks)

    m = len(tiles)

    def rec(mask: int, used: int, remaining: int, unused_area: int) -> bool:
        if remaining == 0:
            return True
        # Prune: the unused tiles cannot supply enough cells.
        if unused_area < remaining:
            return False
        # The first empty cell must be covered by the next tile.
        empty = (~mask) & full
        first = (empty & -empty).bit_length() - 1

        for i in range(m):
            if (used >> i) & 1:
                continue
            ti = areas[i]
            for pm in place_masks[i]:
                if not ((pm >> first) & 1):
                    continue
                if pm & mask:
                    continue
                if rec(mask | pm, used | (1 << i), remaining - ti, unused_area - ti):
                    return True
        return False

    return rec(0, 0, grid_size, total_area)