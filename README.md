# upscaler

Rescales pixel art while keeping its palette, built for sizes that aren't a
whole-number multiple apart, such as **24×24 → 32×32** (a factor of 4/3).

## How it works

```
24×24 ──4× upscale──▶ 96×96 ──majority vote (adaptive grid)──▶ 32×32 ──thin pass──▶ out
```

1. **4× upscale**, plain pixel doubling by default. `--upscaler mmpx` uses
   MMPX (McGuire & Gagiu, 2021) instead, which smooths big curves a little
   but consistently thickens dark outlines (+9% to +26% on the test set) and
   eats double outlines. On sprites with dense detail and 1px outlines,
   plain doubling plus the steps below looked better every time. Neither
   option blends colours.
2. **Mode downsample on an adaptive grid**: each output pixel takes the most
   common colour in its block of the 96×96 image. Blocks average 3×3, but each
   boundary may shift ±1 line (⅓ of an output pixel). A local search picks
   the shifts so thin features keep their thickness. With a rigid 3×3 grid,
   one 1px line in every three would come out 2px thick, the same doubling
   plain nearest-neighbour causes. The cost compares each run's output
   thickness to its real thickness *relative to the run's size*, so leftover
   rounding goes into large flat areas instead of outlines. `--method fixed`
   gives the rigid grid for comparison.
3. **Thin pass**: the grid is one set of boundaries for the whole sprite, so
   on dense sprites some 1px bands still double. This pass finds 2px runs
   where the source was about 1px thick and gives the extra pixel back to the
   colour that lost the vote there, or failing that to the neighbouring
   colour. This brings back a 1px rim swallowed by an outline. It only
   trims dark lines into *lighter, opaque* colours, so the outline never eats
   small details and the silhouette's edge never moves. A pixel that holds
   an outline together is never removed. `--no-thin` turns this off.

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
