"""A tiny pixel grid of packed RGBA ints, so colour equality is a single int compare."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image


def pack(r: int, g: int, b: int, a: int) -> int:
    return (a << 24) | (r << 16) | (g << 8) | b


def unpack(c: int) -> tuple[int, int, int, int]:
    return (c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF, (c >> 24) & 0xFF


def luma(c: int) -> int:
    """MMPX's luma: brightness weighted so transparency counts as very bright.

    Transparent pixels get a large value, which makes the rules treat them as
    background and keep darker (outline) pixels in the foreground.
    """
    r, g, b, a = unpack(c)
    return (r + g + b + 1) * (256 - a)


@dataclass
class Grid:
    width: int
    height: int
    pixels: list[int]

    @classmethod
    def from_image(cls, img: Image.Image) -> "Grid":
        rgba = img.convert("RGBA")
        w, h = rgba.size
        data = getattr(rgba, "get_flattened_data", rgba.getdata)()
        return cls(w, h, [_normalize(pack(*p)) for p in data])

    def to_image(self) -> Image.Image:
        img = Image.new("RGBA", (self.width, self.height))
        img.putdata([unpack(c) for c in self.pixels])
        return img

    def get(self, x: int, y: int) -> int:
        """Read with edge clamping, as MMPX's reference implementation does."""
        x = 0 if x < 0 else (self.width - 1 if x >= self.width else x)
        y = 0 if y < 0 else (self.height - 1 if y >= self.height else y)
        return self.pixels[y * self.width + x]

    def colors(self) -> set[int]:
        return set(self.pixels)


def _normalize(c: int) -> int:
    """Collapse every fully transparent pixel to one value.

    Otherwise (255,0,0,0) and (0,0,0,0) would count as different colours and
    break the equality tests the scaler relies on.
    """
    return 0 if (c >> 24) == 0 else c
