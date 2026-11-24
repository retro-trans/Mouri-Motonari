"""1x proportional font for the canvas VWF (12 px lines).

Source: Skies of Arcadia's Latin font (work/source/skies_font.png, 96 glyphs of
12x24 with coverage levels; decoded by tools/skies_font.py from the user's own
disc, never committed), reduced 2x2 -> 1 px (mean coverage) and thresholded.
Characters Skies lacks come from EXTRA_SRC drawings below.

Glyph table (MIPS side, tools/vwf.py):
  codes 0x20-0x7F, 12 rows each, row = u16 (bit 15 = left pixel), so 24 bytes/glyph
  widths: u8 advance per code
Digits are tabular (same advance) so game-made numbers keep their columns.

    python tools/vwf_font.py --preview work/ui/font/vwf_preview.png ["Sample text"]
"""
import argparse
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'source', 'skies_font.png')
H = 12
THRESH = int(os.environ.get('MM_FONT_THRESH', '128'))
PHASE_Y = os.environ.get('MM_FONT_PHASEY', '0') == '1'
SPACE_ADV = 4
DIGIT_ADV = 6
GAP = 1            # px between glyphs

# 1x drawings for codes Skies lacks (0x7F is used for the e-acute / unused)
EXTRA_SRC = {
    0x5B: ['..##', '..#.', '..#.', '..#.', '..#.', '..#.', '..#.', '..#.', '..##'],   # [
    0x5D: ['##..', '.#..', '.#..', '.#..', '.#..', '.#..', '.#..', '.#..', '##..'],   # ]
    0x5C: ['#...', '#...', '.#..', '.#..', '..#.', '..#.', '...#', '...#', '....'],  # backslash
}
EXTRA_TOP = 1


def reduce(cell, dx, dy):
    """2x2 mean of the 12x24 coverage cell shifted by (dx, dy) 2x px -> 1x rows."""
    px = cell.load()

    def at(x, y):
        x -= dx
        y -= dy
        return px[x, y] if 0 <= x < 12 and 0 <= y < 24 else 0
    rows = []
    for y in range(H):
        rows.append([1 if (at(2 * x, 2 * y) + at(2 * x + 1, 2 * y) + at(2 * x, 2 * y + 1) +
                           at(2 * x + 1, 2 * y + 1)) / 4 >= THRESH else 0 for x in range(7)])
    return rows


def error(cell, rows, dx, dy):
    px = cell.load()
    e = 0
    for y in range(24):
        for x in range(12):
            ys, xs = (y + dy) // 2, (x + dx) // 2
            v = rows[ys][xs] * 255 if ys < H and xs < 7 else 0
            e += abs(v - px[x, y])
    return e


def load():
    im = Image.open(SRC).convert('L')
    glyphs = {}
    for i in range(96):
        code = 32 + i
        cell = im.crop((i * 12, 0, i * 12 + 12, 24))
        best = None
        for dy in (0, 1) if PHASE_Y else (0,):
            for dx in (0, 1):
                rows = reduce(cell, dx, dy)
                e = error(cell, rows, dx, dy)
                if best is None or e < best[0]:
                    best = (e, rows)
        glyphs[code] = best[1]
    for code, art in EXTRA_SRC.items():
        rows = [[0] * 7 for _ in range(H)]
        for y, line in enumerate(art):
            for x, c in enumerate(line):
                if c == '#':
                    rows[EXTRA_TOP + y][x] = 1
        glyphs[code] = rows
    return glyphs


def build():
    """-> (bitmaps {code: [u16 rows]}, adv {code: int})"""
    g = load()
    bm, adv = {}, {}
    for code in range(0x20, 0x80):
        rows = g.get(code, [[0] * 7 for _ in range(H)])
        cols = [x for x in range(7) if any(r[x] for r in rows)]
        if code == 0x20 or not cols:
            bm[code] = [0] * H
            adv[code] = SPACE_ADV
            continue
        x0, x1 = cols[0], cols[-1]
        w = x1 - x0 + 1
        words = []
        for r in rows:
            v = 0
            for x in range(x0, x1 + 1):
                if r[x]:
                    v |= 0x8000 >> (x - x0)
            words.append(v)
        if 0x30 <= code <= 0x39:
            pad = (DIGIT_ADV - GAP - w) // 2
            words = [v >> max(pad, 0) for v in words]
            adv[code] = DIGIT_ADV
        else:
            adv[code] = w + GAP
        bm[code] = words
    return bm, adv


def text_width(s, adv=None):
    if adv is None:
        adv = build()[1]
    return sum(adv.get(ord(c), 6) for c in s)


def render(text, scale=3):
    bm, adv = build()
    lines = text.split('\n')
    W = max(text_width(l, adv) for l in lines) + 4
    im = Image.new('L', (W, H * len(lines) + 4), 255)
    for li, line in enumerate(lines):
        x = 2
        for c in line:
            code = ord(c)
            for y, v in enumerate(bm.get(code, [0] * H)):
                for k in range(16):
                    if v & (0x8000 >> k):
                        im.putpixel((x + k, 2 + li * H + y), 0)
            x += adv.get(code, 6)
    return im.resize((im.width * scale, im.height * scale), Image.NEAREST)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview')
    ap.add_argument('text', nargs='?', default=''.join(chr(c) for c in range(0x20, 0x50)) + '\n' +
                    ''.join(chr(c) for c in range(0x50, 0x7F)) +
                    '\nMouri Motonari: "Brother, rest now.\nI swear on three arrows we\'ll hold Aki!"')
    a = ap.parse_args()
    if a.preview:
        os.makedirs(os.path.dirname(os.path.abspath(a.preview)), exist_ok=True)
        render(a.text.replace('\\n', '\n')).save(a.preview)
        print(a.preview)
