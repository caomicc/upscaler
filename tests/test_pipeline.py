import random

from PIL import Image

from upscaler import rescale, rescale_sheet
from upscaler.downsample import mode_downsample
from upscaler.grid import Grid, pack
from upscaler.mmpx import mmpx2x

BLACK = (0, 0, 0, 255)
RED = (200, 40, 40, 255)
CLEAR = (0, 0, 0, 0)


def img_from(rows, palette):
    h, w = len(rows), len(rows[0])
    im = Image.new("RGBA", (w, h))
    im.putdata([palette[ch] for row in rows for ch in row])
    return im


def colors(im):
    im = im.convert("RGBA")
    return set(getattr(im, "get_flattened_data", im.getdata)())


def test_flat_image_stays_flat():
    im = Image.new("RGBA", (24, 24), RED)
    out = rescale(im, 32, 32)
    assert out.size == (32, 32)
    assert colors(out) == {RED}


def test_mmpx_doubles_and_preserves_palette():
    rnd = random.Random(1)
    pal = [pack(10, 20, 30, 255), pack(200, 100, 0, 255), 0, pack(255, 255, 255, 255)]
    g = Grid(24, 24, [rnd.choice(pal) for _ in range(24 * 24)])
    out = mmpx2x(g)
    assert (out.width, out.height) == (48, 48)
    assert out.colors() <= g.colors()


def test_isolated_pixel_maps_to_2x2_block():
    g = Grid(5, 5, [0] * 25)
    g.pixels[12] = pack(255, 0, 0, 255)
    out = mmpx2x(g)
    lit = [i for i, c in enumerate(out.pixels) if c]
    assert len(lit) == 4


def test_random_sprite_24_to_32_never_adds_colours():
    rnd = random.Random(7)
    palette = [BLACK, RED, CLEAR, (240, 200, 120, 255), (60, 120, 200, 255)]
    im = Image.new("RGBA", (24, 24))
    im.putdata([rnd.choice(palette) for _ in range(24 * 24)])
    out = rescale(im, 32, 32)
    assert out.size == (32, 32)
    assert colors(out) <= colors(im)


def test_mode_downsample_majority_and_tie_break_to_centre():
    a, b = pack(1, 1, 1, 255), pack(250, 250, 250, 255)
    # A 3x3 block where b has 5 of 9 pixels, so b wins the vote.
    g = Grid(3, 3, [a, b, a,
                    b, b, b,
                    a, b, a])
    assert mode_downsample(g, 1, 1).pixels == [b]


def test_one_px_outline_survives():
    rows = ["........................"] * 4 + \
           ["....####################"] + \
           ["....#..................."] * 19
    im = img_from(rows, {".": CLEAR, "#": BLACK})
    out = rescale(im, 32, 32)
    px = out.load()
    # The outline's horizontal run should still be there, and still 1px thick in most columns.
    row_hits = [y for y in range(32) if px[20, y] == BLACK]
    assert len(row_hits) == 1


def test_1px_horizontal_line_stays_1px_at_every_offset():
    # A fixed grid thickens the line at one of every three y offsets; the adaptive one must not.
    for y in range(2, 22):
        rows = ["." * 24] * 24
        rows = rows[:y] + ["...." + "#" * 16 + "...."] + rows[y + 1:]
        out = rescale(img_from(rows, {".": CLEAR, "#": BLACK}), 32, 32)
        px = out.load()
        thick = sum(1 for yy in range(32) if px[16, yy] == BLACK)
        assert thick == 1, f"line at y={y} came out {thick}px thick"


def test_fixed_method_still_available():
    im = Image.new("RGBA", (24, 24), RED)
    assert colors(rescale(im, 32, 32, method="fixed")) == {RED}


def test_sheet_tiles_processed_independently():
    a = Image.new("RGBA", (24, 24), RED)
    b = Image.new("RGBA", (24, 24), BLACK)
    sheet = Image.new("RGBA", (48, 24))
    sheet.paste(a, (0, 0))
    sheet.paste(b, (24, 0))
    out = rescale_sheet(sheet, 24, 24, 32, 32)
    assert out.size == (64, 32)
    assert colors(out.crop((0, 0, 32, 32))) == {RED}
    assert colors(out.crop((32, 0, 64, 32))) == {BLACK}
