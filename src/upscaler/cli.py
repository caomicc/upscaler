"""Command line: upscaler INPUT... [-o OUTDIR] [--size 32] [--tile 24] [--compare]."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from .grid import Grid
from .pipeline import rescale, rescale_sheet


def _size(s: str) -> tuple[int, int]:
    w, _, h = s.lower().partition("x")
    return int(w), int(h or w)


def _compare(src: Image.Image, out: Image.Image, zoom: int) -> Image.Image:
    """Make a side-by-side image: original | plain nearest-neighbour | pipeline result.

    All three panels are zoomed to the same on-screen size so they can be
    compared directly.
    """
    ow, oh = out.size
    nn = src.resize((ow, oh), Image.NEAREST)
    panels = [src.resize((ow * zoom, oh * zoom), Image.NEAREST),
              nn.resize((ow * zoom, oh * zoom), Image.NEAREST),
              out.resize((ow * zoom, oh * zoom), Image.NEAREST)]
    gap = zoom * 2
    sheet = Image.new("RGBA", (ow * zoom * 3 + gap * 2, oh * zoom), (40, 40, 48, 255))
    for i, p in enumerate(panels):
        bg = Image.new("RGBA", p.size, (40, 40, 48, 255))
        bg.alpha_composite(p)
        sheet.paste(bg, (i * (ow * zoom + gap), 0))
    return sheet


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="upscaler", description="Palette-preserving pixel-art rescale (MMPX + mode downsample).")
    ap.add_argument("inputs", nargs="+", type=Path, help="PNG files or directories of PNGs")
    ap.add_argument("-o", "--outdir", type=Path, default=Path("out"), help="output directory (default: out)")
    ap.add_argument("--size", type=_size, default=(32, 32), help="target sprite size, e.g. 32 or 32x32 (default 32)")
    ap.add_argument("--tile", type=_size, default=None, help="treat input as a sheet of TILE-sized frames, e.g. 24 or 24x24")
    ap.add_argument("--method", choices=["adaptive", "fixed"], default="adaptive",
                    help="downsample grid: adaptive aligns blocks to edges (default); fixed is an even grid")
    ap.add_argument("--upscaler", choices=["nearest", "mmpx"], default="nearest",
                    help="2x step before the downsample: nearest doubles pixels (default, keeps 1px lines crisp); mmpx smooths diagonals but thickens dark outlines")
    ap.add_argument("--no-thin", dest="thin", action="store_false",
                    help="skip the pass that trims 2px runs back to 1px where the source line was 1px")
    ap.add_argument("--compare", action="store_true", help="also write a zoomed side-by-side *_compare.png")
    ap.add_argument("--zoom", type=int, default=8, help="zoom for --compare (default 8)")
    args = ap.parse_args(argv)

    files: list[Path] = []
    for p in args.inputs:
        files.extend(sorted(p.glob("*.png")) if p.is_dir() else [p])
    if not files:
        print("no input PNGs found", file=sys.stderr)
        return 1

    args.outdir.mkdir(parents=True, exist_ok=True)
    tw, th = args.size
    failed = 0
    for f in files:
        try:
            src = Image.open(f).convert("RGBA")
            if args.tile:
                out = rescale_sheet(src, *args.tile, tw, th, method=args.method, thin=args.thin,
                                    upscaler=args.upscaler)
            else:
                out = rescale(src, tw, th, method=args.method, thin=args.thin, upscaler=args.upscaler)
        except Exception as e:  # keep going so one bad file doesn't stop a batch
            print(f"FAIL {f}: {e}", file=sys.stderr)
            failed += 1
            continue

        dest = args.outdir / f.name
        out.save(dest)
        new = Grid.from_image(out).colors() - Grid.from_image(src).colors()
        note = f"  ({len(new)} NEW COLOURS)" if new else ""
        print(f"ok   {f} {src.size[0]}x{src.size[1]} -> {dest} {out.size[0]}x{out.size[1]}{note}")

        if args.compare:
            if args.tile:
                # For a sheet, compare the first frame only.
                src_c = src.crop((0, 0, *args.tile))
                out_c = out.crop((0, 0, tw, th))
            else:
                src_c, out_c = src, out
            _compare(src_c, out_c, args.zoom).save(args.outdir / f"{f.stem}_compare.png")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
