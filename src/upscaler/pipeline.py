"""Overall pipeline: MMPX-upscale to at least the target size, then mode-downsample to it."""

from __future__ import annotations

from PIL import Image

from .downsample import mode_downsample
from .grid import Grid
from .mmpx import mmpx2x


def rescale(
    img: Image.Image, width: int, height: int, min_factor: int = 4, method: str = "adaptive"
) -> Image.Image:
    """Rescale one sprite while keeping its palette.

    Runs MMPX 2x until the image is at least ``min_factor`` times larger and at
    least as large as the target, then shrinks it by majority vote. A 24 -> 32
    rescale goes 24 -> 48 -> 96 -> 32, so every output pixel is a vote over an
    exact 3x3 block.
    """
    grid = Grid.from_image(img)
    factor = 1
    while factor < min_factor or grid.width < width or grid.height < height:
        grid = mmpx2x(grid)
        factor *= 2
    return mode_downsample(grid, width, height, method).to_image()


def rescale_sheet(
    img: Image.Image, tile_w: int, tile_h: int, out_w: int, out_h: int,
    min_factor: int = 4, method: str = "adaptive",
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
            out.paste(rescale(tile, out_w, out_h, min_factor, method), (c * out_w, r * out_h))
    return out
