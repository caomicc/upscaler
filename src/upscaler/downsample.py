"""Shrink an image by majority vote over blocks of pixels, never by averaging.

Each output pixel covers a rectangle of the input and takes the most common
colour in it. Where the rectangles go is decided by one of two methods:

* ``fixed``: an even grid. For 96 -> 32 every block is 3x3. Simple, but a 1px
  line (4 rows after a 4x upscale) straddles two blocks in one of every three
  positions and comes out 2px thick.
* ``adaptive`` (the default): block heights and widths may vary (2/3/4 for a
  ratio of 3). A dynamic program picks boundaries that line up with colour
  edges, so the extra size goes into flat areas instead of thickening lines.
"""

from __future__ import annotations

from collections import Counter

from .grid import Grid, luma

Span = tuple[int, int]


def fixed_spans(src: int, dst: int) -> list[Span]:
    return [((i * src) // dst, max(((i + 1) * src) // dst, (i * src) // dst + 1)) for i in range(dst)]


def adaptive_spans(
    lines: list[list[int]], dst: int, max_drift: int = 1, drift_penalty: float = 0.01, max_passes: int = 8
) -> list[Span]:
    """Split ``len(lines)`` input lines into ``dst`` consecutive blocks.

    ``lines[i]`` is input line i (a row or a column); ``lines[i][x]`` is the
    colour at position x along it. Each output pixel stands for
    ``ratio = n / dst`` input lines.

    Cost is measured per position x, over *runs*: consecutive blocks that
    vote the same colour c. A run of m blocks covering input lines [s, e) has
    real thickness L = count(c in [s, e)) / ratio output pixels, and costs
    |m - L| / L (thickness error *relative* to the run's size) plus the pixels
    that lost the vote, also in output-pixel units. Using relative error
    means a 1.33px outline drawn 2px (50% too thick) costs far more than a
    25.3px background run drawn 26px (3% off). Area is conserved, so the
    leftover rounding has to go somewhere, and this puts it in large flat
    areas where it can't be seen. Errors also cancel within a single run, so
    uneven blocks in empty space cost nothing.

    Boundary k may sit at most ``max_drift`` lines from its even-grid
    position. With a 4x upscale that's 1/3 of an output pixel, enough to stop
    1px lines from doubling without warping the shape. The search starts from
    the even grid and tries single and adjacent-pair boundary moves of +/-1,
    keeping any move that lowers the total cost.
    """
    n = len(lines)
    ratio = n / dst
    width = len(lines[0])
    ideal = [round(k * ratio) for k in range(dst + 1)]
    bounds = ideal[:]

    # prefix[x][c][i] = number of c pixels among lines [0, i) at position x.
    prefix: list[dict[int, list[int]]] = []
    for x in range(width):
        cols: dict[int, list[int]] = {}
        for i in range(n):
            c = lines[i][x]
            if c not in cols:
                cols[c] = [0] * (n + 1)
        for c, arr in cols.items():
            run = 0
            for i in range(n):
                run += lines[i][x] == c
                arr[i + 1] = run
        prefix.append(cols)

    def block_winner(x: int, a: int, b: int) -> int:
        counts = Counter(lines[y][x] for y in range(a, b))
        best = max(counts.values())
        tied = [c for c, k in counts.items() if k == best]
        if len(tied) == 1:
            return tied[0]
        center = lines[(a + b - 1) // 2][x]
        return center if center in tied else min(tied, key=lambda c: ((c >> 24) == 0, luma(c), c))

    def column_cost(x: int, winners: list[int], bd: list[int]) -> float:
        pre = prefix[x]
        cost = 0.0
        k = 0
        while k < dst:
            c = winners[k]
            j = k
            while j + 1 < dst and winners[j + 1] == c:
                j += 1
            s, e = bd[k], bd[j + 1]
            have = pre[c][e] - pre[c][s]
            true_px = max(have / ratio, 0.5)  # the run's real thickness in output pixels
            cost += abs((j - k + 1) - have / ratio) / true_px + ((e - s) - have) / ratio
            k = j + 1
        return cost

    def drift_cost(bd: list[int]) -> float:
        return drift_penalty * sum(abs(b - i) for b, i in zip(bd, ideal))

    winners = [[block_winner(x, bounds[k], bounds[k + 1]) for k in range(dst)] for x in range(width)]
    col_costs = [column_cost(x, winners[x], bounds) for x in range(width)]
    total = sum(col_costs) + drift_cost(bounds)

    def valid(bd: list[int], ks: tuple[int, ...]) -> bool:
        for k in ks:
            if abs(bd[k] - ideal[k]) > max_drift:
                return False
        return all(bd[k] < bd[k + 1] for k in range(min(ks) - 1, max(ks) + 1))

    # Candidate moves: shift a window of 1-4 consecutive boundaries the same way
    # (this moves a block without changing its length), or push two adjacent
    # boundaries apart or together.
    moves: list[tuple[tuple[int, ...], tuple[int, ...]]] = []
    for k in range(1, dst):
        for span in range(1, 5):
            if k + span - 1 < dst:
                ks = tuple(range(k, k + span))
                moves += [(ks, (d,) * span) for d in (-1, 1)]
        if k + 1 < dst:
            moves += [((k, k + 1), (-1, 1)), ((k, k + 1), (1, -1))]

    for _ in range(max_passes):
        improved = False
        for ks, ds in moves:
            bd = bounds[:]
            for k, d in zip(ks, ds):
                bd[k] += d
            if not valid(bd, ks):
                continue
            touched = range(min(ks) - 1, max(ks) + 1)  # blocks whose span changed
            lo_line, hi_line = bd[min(ks) - 1], bd[max(ks) + 1]  # these outer edges don't move
            new_winners, new_costs = [], []
            for x in range(width):
                # If one colour fills the whole affected range at this x, the
                # winners and run boundaries are the same as before, so the cost is too.
                c0 = lines[lo_line][x]
                if prefix[x][c0][hi_line] - prefix[x][c0][lo_line] == hi_line - lo_line:
                    new_winners.append(winners[x])
                    new_costs.append(col_costs[x])
                    continue
                w = winners[x][:]
                for b in touched:
                    w[b] = block_winner(x, bd[b], bd[b + 1])
                new_winners.append(w)
                new_costs.append(column_cost(x, w, bd))
            new_total = sum(new_costs) + drift_cost(bd)
            if new_total < total - 1e-9:
                bounds, winners, col_costs, total = bd, new_winners, new_costs, new_total
                improved = True
        if not improved:
            break

    return [(bounds[k], bounds[k + 1]) for k in range(dst)]


def mode_downsample(src: Grid, width: int, height: int, method: str = "adaptive") -> Grid:
    if method == "fixed":
        xs, ys = fixed_spans(src.width, width), fixed_spans(src.height, height)
    elif method == "adaptive":
        rows = [src.pixels[y * src.width:(y + 1) * src.width] for y in range(src.height)]
        cols = [[src.pixels[y * src.width + x] for y in range(src.height)] for x in range(src.width)]
        ys = adaptive_spans(rows, height)
        xs = adaptive_spans(cols, width)
    else:
        raise ValueError(f"unknown downsample method {method!r}")

    out: list[int] = []
    for y0, y1 in ys:
        for x0, x1 in xs:
            block = [src.pixels[y * src.width + x] for y in range(y0, y1) for x in range(x0, x1)]
            cx, cy = (x0 + x1 - 1) // 2, (y0 + y1 - 1) // 2
            out.append(_vote(block, src.pixels[cy * src.width + cx]))
    return Grid(width, height, out)


def _vote(block: list[int], center: int) -> int:
    counts = Counter(block)
    best = max(counts.values())
    tied = [c for c, n in counts.items() if n == best]
    if len(tied) == 1:
        return tied[0]
    # Tie-breaks in order: the centre pixel's colour, then any opaque colour
    # over transparent, then the darker colour (outlines are usually the
    # darkest and the first thing lost when shrinking).
    if center in tied:
        return center
    return min(tied, key=lambda c: ((c >> 24) == 0, luma(c), c))
