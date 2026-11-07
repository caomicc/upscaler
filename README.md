# upscaler

Rescales pixel art while keeping its palette, built for sizes that aren't a
whole-number multiple apart, such as **24×24 → 32×32** (a factor of 4/3).

## How it works

```
24×24 ──MMPX 2×──▶ 48×48 ──MMPX 2×──▶ 96×96 ──3×3 majority vote──▶ 32×32
```

1. **MMPX** (McGuire & Gagiu, 2021) is a 2× scaler made for pixel art. It
   smooths diagonals and keeps outlines one pixel wide. Every output pixel is
   *copied* from the input, never blended, so no new colours can appear.
2. **Mode downsample on an adaptive grid**: each output pixel takes the most
   common colour in its block of the 96×96 image. Blocks average 3×3, but each
   boundary may shift ±1 line (⅓ of an output pixel). A local search picks
   the shifts so thin features keep their thickness. With a rigid 3×3 grid,
   one 1px line in every three would come out 2px thick, the same doubling
   plain nearest-neighbour causes. The cost compares each run's output
   thickness to its real thickness *relative to the run's size*, so leftover
   rounding goes into large flat areas instead of outlines. `--method fixed`
   gives the rigid grid for comparison.

Neither step blends colours, so the output only uses colours from the input.
The CLI checks this and warns if it ever fails.

Expect a clean **draft**, not finished art. A hand touch-up pass in Aseprite
is still the step that adds real detail at 32px.

## Usage

```sh
uv sync
uv run upscaler sprite.png                     # -> out/sprite.png (32x32)
uv run upscaler sprites/ -o out --compare      # batch + side-by-side previews
uv run upscaler sheet.png --tile 24 --size 32  # sprite sheet, frame by frame
uv run pytest
```

`--compare` writes `*_compare.png`, three panels zoomed to the same size:
**original | plain nearest-neighbour to 32 | this pipeline**.

`examples/make_sample.py` writes a 24×24 test sprite.
