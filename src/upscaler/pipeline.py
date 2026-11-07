"""Overall pipeline: MMPX-upscale, mode-downsample to the target size, then thin doubled lines."""

from __future__ import annotations

from PIL import Image

from .downsample import mode_downsample_spans
from .grid import Grid
from .mmpx import mmpx2x
from .thin import thin_lines


def rescale(
    img: Image.Image, width: int, height: int, min_factor: int = 4,
    method: str = "adaptive", thin: bool = True, upscaler: str = "nearest",
) -> Image.Image:
    """Rescale one sprite while keeping its palette.

    Upscales 2x at a time until the image is at least ``min_factor`` times
    larger and at least as large as the target, then shrinks it by majority
    vote. A 24 -> 32 rescale goes 24 -> 48 -> 96 -> 32. ``upscaler`` is
    "mmpx" (smooths diagonals) or "nearest" (plain pixel doubling, so all
    the work is left to the grid and thin pass). If ``thin`` is set, 1px
    source lines that came out 2px are then trimmed back to 1px.
    """
    grid = Grid.from_image(img)
    factor = 1
    while factor < min_factor or grid.width < width or grid.height < height:
        grid = mmpx2x(grid) if upscaler == "mmpx" else _double(grid)
        factor *= 2
    out, xs, ys = mode_downsample_spans(grid, width, height, method)
    if thin:
        out = thin_lines(out, grid, xs, ys, factor)
    return out.to_image()


def _double(g: Grid) -> Grid:
    out: list[int] = []
    for y in range(g.height):
        row = [p for p in g.pixels[y * g.width:(y + 1) * g.width] for _ in (0, 1)]
        out += row + row
    return Grid(g.width * 2, g.height * 2, out)


def rescale_sheet(
    img: Image.Image, tile_w: int, tile_h: int, out_w: int, out_h: int,
    min_factor: int = 4, method: str = "adaptive", thin: bool = True, upscaler: str = "nearest",
) -> Image.Image:
    """Rescale each tile of a sprite sheet on its own.

    Tiles are processed separately so one frame's pixels can't influence the
    edges of its neighbour.
    """
    sw, sh = img.size
    if sw % tile_w or sh % tile_h:
        raise ValueError(f"sheet {sw}x{sh} is not a whole number of {tile_w}x{tile_h} tiles")
    cols, rows = sw // tile_w, sh // tile_h
    out = Image.new("RGBA", (cols * out_w, rows * out_h), (0, 0, 0, 0))
    for r in range(rows):
        for c in range(cols):
            tile = img.crop((c * tile_w, r * tile_h, (c + 1) * tile_w, (r + 1) * tile_h))
            out.paste(rescale(tile, out_w, out_h, min_factor, method, thin, upscaler), (c * out_w, r * out_h))
    return out
