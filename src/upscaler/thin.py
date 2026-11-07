"""After the downsample: turn 2px runs back into 1px where the source line was 1px.

The adaptive grid picks one set of row (and column) boundaries for the whole
sprite. A dense sprite has 1px bands at many different offsets, so some still
come out 2px thick. This pass fixes them locally.

For each run of exactly 2 same-coloured output pixels (vertical runs, then
horizontal runs), it measures how thick that colour is at the same spot in
the upscaled image. If it's about 1 source pixel thick, the run is trimmed to
1px. The trimmed pixel is the one whose block holds less of the colour, and
it is recoloured to its neighbour beyond the run, so the palette is still
preserved. A pixel is only trimmed when that neighbour is lighter and opaque,
so the outside edge of the silhouette never gets notched. The scaler
and the vote both lean toward dark colours, so dark lines are the ones that
spread, and letting a light colour be trimmed would let outlines eat small
details. A pixel is never removed if doing so would break its colour's
8-connectivity (the standard "simple point" test from thinning algorithms),
so diagonal outlines stay unbroken.
"""

from __future__ import annotations

from .grid import Grid, luma

Span = tuple[int, int]

# A 1-source-pixel line is up_factor (4) lines thick in the upscaled image.
# Allow one extra line, because MMPX sometimes widens a line where it smooths a diagonal.
_THIN_SLACK = 1


def _is_simple(px: list[int], w: int, h: int, x: int, y: int) -> bool:
    """True if removing (x, y) keeps the remaining same-colour pixels around it connected.

    It counts groups of same-coloured pixels among the 8 neighbours, joined 8-way
    but with diagonals only through a shared edge neighbour, which is how
    pixel-art outlines connect. Exactly one group means the pixel can go
    without splitting anything.
    """
    c = px[y * w + x]
    ring = [(-1, -1), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0)]
    on = []
    for dx, dy in ring:
        nx, ny = x + dx, y + dy
        on.append(0 <= nx < w and 0 <= ny < h and px[ny * w + nx] == c)
    if not any(on):
        return False  # an isolated pixel is a deliberate detail; leave it
    # Count separate groups around the ring. A corner neighbour joins its
    # neighbours in the ring because they touch it.
    seen = [False] * 8
    groups = 0
    for i in range(8):
        if not on[i] or seen[i]:
            continue
        groups += 1
        stack = [i]
        seen[i] = True
        while stack:
            j = stack.pop()
            for k in ((j - 1) % 8, (j + 1) % 8):
                if on[k] and not seen[k]:
                    seen[k] = True
                    stack.append(k)
    return groups == 1


def _thick_in_big(big: Grid, c: int, cx: int, y0: int, y1: int, vertical: bool) -> int:
    """Length of the run of colour c along one line of the upscaled image, over [y0, y1).

    It starts from the first c pixel inside [y0, y1) and extends past the range
    in both directions if the run continues. ``vertical`` means the line is
    column cx; otherwise it is row cx.
    """
    def at(i: int) -> int:
        return big.pixels[i * big.width + cx] if vertical else big.pixels[cx * big.width + i]

    n = big.height if vertical else big.width
    start = next((i for i in range(y0, y1) if at(i) == c), None)
    if start is None:
        return 0
    a = start
    while a > 0 and at(a - 1) == c:
        a -= 1
    b = start
    while b + 1 < n and at(b + 1) == c:
        b += 1
    return b - a + 1


def _count_in_big(big: Grid, c: int, xs: Span, ys: Span) -> int:
    return sum(1 for y in range(*ys) for x in range(*xs) if big.pixels[y * big.width + x] == c)


def _runner_up(big: Grid, c: int, xs: Span, ys: Span, min_share: int = 2):
    """Most common colour other than c in this block of the upscaled image, or None."""
    counts: dict[int, int] = {}
    for y in range(*ys):
        for x in range(*xs):
            p = big.pixels[y * big.width + x]
            if p != c:
                counts[p] = counts.get(p, 0) + 1
    if not counts:
        return None
    best = max(counts, key=lambda p: (counts[p], p != 0))
    return best if counts[best] >= min_share else None


def thin_lines(out: Grid, big: Grid, xs: list[Span], ys: list[Span], up_factor: int) -> Grid:
    w, h = out.width, out.height
    px = out.pixels[:]
    limit = up_factor + _THIN_SLACK

    for vertical in (True, False):
        # When vertical is False, walk rows by swapping the roles of x and y.
        outer, inner = (w, h) if vertical else (h, w)
        for o in range(outer):
            i = 0
            while i < inner:
                def get(k: int) -> int:
                    return px[k * w + o] if vertical else px[o * w + k]

                c = get(i)
                j = i
                while j + 1 < inner and get(j + 1) == c:
                    j += 1
                if j - i == 1 and c != 0:
                    _maybe_trim(px, w, h, big, xs, ys, o, i, c, vertical, limit)
                i = j + 1

    return Grid(w, h, px)


def _maybe_trim(px, w, h, big, xs, ys, o, i, c, vertical, limit) -> None:
    """Consider the 2px run of colour c at positions i and i+1 along line o."""
    spans_along, spans_across = (ys, xs) if vertical else (xs, ys)
    a0, _ = spans_along[i]
    _, a1 = spans_along[i + 1]
    lo, hi = spans_across[o]
    centre = (lo + hi - 1) // 2
    if _thick_in_big(big, c, centre, a0, a1, vertical) > limit:
        return  # the source really is thick here; 2px is right

    def xy(k: int) -> tuple[int, int]:
        return (o, k) if vertical else (k, o)

    def colour_at(k: int):
        if not 0 <= k < (h if vertical else w):
            return None
        x, y = xy(k)
        return px[y * w + x]

    def allowed(repl) -> bool:
        # Only give dark line pixels back to lighter *opaque* colours.
        # Trimming a light colour lets outlines eat small details (berries,
        # highlights, 1px bands); trimming into transparency puts notches in
        # the silhouette.
        return repl is not None and repl != c and repl != 0 and luma(repl) > luma(c)

    candidates = []
    for k, outside in ((i, i - 1), (i + 1, i + 2)):
        x, y = xy(k)
        # First choice: the colour that lost the vote in this pixel's own
        # block (e.g. a 1px pink rim that the navy outline beat). It's what is
        # really there, and the only way to restore a detail the vote erased.
        # Fallback: the neighbour beyond the run.
        repl = _runner_up(big, c, xs[x], ys[y])
        if not allowed(repl):
            repl = colour_at(outside)
        if not allowed(repl):
            continue
        share = _count_in_big(big, c, xs[x], ys[y])  # try the pixel with less of the colour first
        candidates.append((share, k, repl))
    for _, k, repl in sorted(candidates):
        x, y = xy(k)
        if _is_simple(px, w, h, x, y):
            px[y * w + x] = repl
            return
