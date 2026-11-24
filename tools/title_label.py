"""Project URL and build version in the title screen's bottom-right corner (AGENTS.md).

The title picture is a raw 320x240 16-bit image in GRAPHIC/LOGO.E3 at offset 0x13000
(the game keeps it in VRAM (320,256) and copies it to the screen every frame). Two
right-aligned lines are drawn into it, light grey with a 1-pixel dark outline so they read
over the boards and the arrow tip: 'v<version>' just below the right end of the copyright
line, and 'github.com/retro-trans' under it. Small hand-made pixel font (3-5 px wide,
x-height 4, ascenders / descenders 2).

    python tools/title_label.py preview <out.png> [version]    the patched picture, 3x
Used by tools/build.py (patch(VERSION)).
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'source', 'disc', 'GRAPHIC', 'LOGO.E3')
PIC, W, H = 0x13000, 320, 240
URL = 'github.com/retro-trans'
RIGHT = 312                     # last text column (outline one further right)
LINES_Y = (214, 224)            # top row of the 8-row glyph cells: version, URL
INK = (232, 232, 224)
EDGE = (24, 14, 6)

# rows 0-7: ascender 0-1, x-height 2-5, descender 6-7
FONT = {
    'g': '....|....|.###|#..#|#..#|.###|...#|###.',
    'i': '#|.|#|#|#|#|.|.',
    't': '.#.|.#.|###|.#.|.#.|..#|...|...',
    'h': '#...|#...|###.|#..#|#..#|#..#|....|....',
    'u': '....|....|#..#|#..#|#..#|.###|....|....',
    'b': '#...|#...|###.|#..#|#..#|###.|....|....',
    'c': '...|...|.##|#..|#..|.##|...|...',
    'o': '....|....|.##.|#..#|#..#|.##.|....|....',
    'm': '.....|.....|####.|#.#.#|#.#.#|#.#.#|.....|.....',
    'r': '...|...|#.#|##.|#..|#..|...|...',
    'e': '....|....|.##.|####|#...|.##.|....|....',
    'a': '....|....|.###|#..#|#..#|.###|....|....',
    'n': '....|....|###.|#..#|#..#|#..#|....|....',
    's': '...|...|.##|#..|..#|##.|...|...',
    'v': '...|...|#.#|#.#|#.#|.#.|...|...',
    '.': '.|.|.|.|.|#|.|.',
    '/': '..#|..#|.#.|.#.|#..|#..|...|...',
    '-': '...|...|...|###|...|...|...|...',
    '0': '.#.|#.#|#.#|#.#|#.#|.#.|...|...',
    '1': '.#.|##.|.#.|.#.|.#.|###|...|...',
    '2': '##.|..#|..#|.#.|#..|###|...|...',
    '3': '##.|..#|.#.|..#|..#|##.|...|...',
    '4': '#.#|#.#|###|..#|..#|..#|...|...',
    '5': '###|#..|##.|..#|..#|##.|...|...',
    '6': '.##|#..|##.|#.#|#.#|.#.|...|...',
    '7': '###|..#|..#|.#.|.#.|.#.|...|...',
    '8': '.#.|#.#|.#.|#.#|#.#|.#.|...|...',
    '9': '.#.|#.#|#.#|.##|..#|##.|...|...',
}


def rgb15(c):
    r, g, b = (v >> 3 for v in c)
    return r | (g << 5) | (b << 10)


def pixels(text, x_right, y):
    """{(x, y)} of the ink of text, right-aligned to x_right"""
    glyphs = [[r for r in FONT[c].split('|')] for c in text]
    width = sum(len(g[0]) for g in glyphs) + len(glyphs) - 1
    x = x_right - width + 1
    out = set()
    for g in glyphs:
        for j, r in enumerate(g):
            out |= {(x + a, y + j) for a, ch in enumerate(r) if ch == '#'}
        x += len(g[0]) + 1
    return out


def patch(version, data=None):
    d = bytearray(open(SRC, 'rb').read() if data is None else data)
    ink = pixels('v' + version, RIGHT, LINES_Y[0]) | pixels(URL, RIGHT, LINES_Y[1])
    edge = {(x + i, y + j) for x, y in ink for i in (-1, 0, 1) for j in (-1, 0, 1)} - ink
    for pts, col in ((edge, rgb15(EDGE)), (ink, rgb15(INK))):
        for x, y in pts:
            assert 0 <= x < W and 0 <= y < H, (x, y)
            struct.pack_into('<H', d, PIC + (y * W + x) * 2, col)
    return bytes(d)


def preview(out, version):
    from PIL import Image
    d = patch(version)
    im = Image.new('RGB', (W, H))
    p = im.load()
    for y in range(H):
        for x in range(W):
            v = struct.unpack_from('<H', d, PIC + (y * W + x) * 2)[0]
            p[x, y] = ((v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3)
    im.resize((W * 3, H * 3), Image.NEAREST).save(out)


if __name__ == '__main__':
    if sys.argv[1:2] == ['preview']:
        preview(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else '0.0.0')
