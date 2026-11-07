"""Write examples/slime_24.png, a 24x24 test sprite with an outline, shading, a highlight and eyes."""

from pathlib import Path

from PIL import Image

ROWS = [
    "........................",
    "........................",
    "........................",
    "........................",
    "..........oooo..........",
    "........oo####oo........",
    ".......o##hh####o.......",
    "......o##hhh#####o......",
    ".....o##hh########o.....",
    ".....o#hh#########o.....",
    "....o#############so....",
    "....o###ko####ko##so....",
    "...o####kw####kw###so...",
    "...o####kk####kk###so...",
    "...o###############so...",
    "...o##############sso...",
    "..o#######kkkk####sso...",
    "..o##############ssso...",
    "..o#############sssso...",
    "..osss#######sssssso....",
    "...oossssssssssssoo.....",
    ".....oooooooooooo.......",
    "........................",
    "........................",
]

PAL = {
    ".": (0, 0, 0, 0),
    "o": (24, 20, 37, 255),     # outline
    "#": (62, 137, 72, 255),    # body
    "s": (38, 92, 66, 255),     # shadow
    "h": (99, 199, 77, 255),    # highlight
    "k": (24, 20, 37, 255),     # eyes/mouth
    "w": (255, 255, 255, 255),  # eye glint
}

if __name__ == "__main__":
    assert len(ROWS) == 24 and all(len(r) == 24 for r in ROWS)
    im = Image.new("RGBA", (24, 24))
    im.putdata([PAL[c] for r in ROWS for c in r])
    dest = Path(__file__).with_name("slime_24.png")
    im.save(dest)
    print(dest)
