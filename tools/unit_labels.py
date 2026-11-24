"""English label on the 'ship' unit of the battle animations, GRAPHIC/BA_UNIT.BIN.

BA_UNIT.BIN is 49 chunks of 0x8000 bytes, one per unit graphic (read 32032 bytes at a time
into 0x801A8000): 800 rows of 40 bytes (80 px, 4bpp) + 32 bytes. Chunks 30-32 are the same
mounted general as chunk 33 with a big 船 ('ship') stamped over him in ink 1 in each of the
10 frames: the game's stand-in for a unit on a boat. It shows in battle and skill
animations. Here the rider is restored from chunk 33 where the kanji was, and 'SHIP' is
drawn in ink 1, 2-px strokes, centred on the old kanji.

    python tools/unit_labels.py preview <out.png>    original and English frames, 3x
Used by tools/build.py (patch()).
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'source', 'disc', 'GRAPHIC', 'BA_UNIT.BIN')
CHUNK, ROWS, ROWB = 0x8000, 800, 40
STAMPED, PLAIN = (30, 31, 32), 33
INK = 1

GLYPHS = {                                  # 11 rows, 2-px strokes
    'S': ['.######', '#######', '##.....', '##.....', '######.', '.######', '.....##', '.....##',
          '.....##', '#######', '######.'],
    'H': ['##...##'] * 4 + ['#######'] * 2 + ['##...##'] * 5,
    'I': ['######', '######'] + ['..##..'] * 7 + ['######', '######'],
    'P': ['######.', '#######', '##...##', '##...##', '#######', '######.'] + ['##.....'] * 5,
}
TEXT = 'SHIP'


def pixels(d, c):
    a = np.frombuffer(bytes(d[c * CHUNK:c * CHUNK + ROWS * ROWB]), np.uint8).reshape(ROWS, ROWB)
    return np.stack([a & 15, a >> 4], -1).reshape(ROWS, ROWB * 2)


def store(d, c, px):
    p = px.reshape(ROWS, ROWB, 2).astype(np.uint8)
    d[c * CHUNK:c * CHUNK + ROWS * ROWB] = (p[..., 0] | (p[..., 1] << 4)).tobytes()


def text_mask():
    cols = []
    for i, ch in enumerate(TEXT):
        g = np.array([[c == '#' for c in r] for r in GLYPHS[ch]])
        cols += [g] + ([np.zeros((11, 2), bool)] if i < len(TEXT) - 1 else [])
    return np.hstack(cols)


def frames(mask):
    """(y0, y1, x0, x1) of each stamped kanji: runs of rows that hold kanji pixels"""
    rows, out, y = mask.any(1), [], 0
    while y < len(rows):
        if rows[y]:
            y0 = y
            while y < len(rows) and rows[y]:
                y += 1
            xs = np.nonzero(mask[y0:y].any(0))[0]
            out.append((y0, y, xs[0], xs[-1] + 1))
        y += 1
    return out


def patch(data=None):
    d = bytearray(open(SRC, 'rb').read() if data is None else data)
    plain = pixels(d, PLAIN)
    t = text_mask()
    th, tw = t.shape
    for c in STAMPED:
        px = pixels(d, c)
        kanji = (px != plain) & (px == INK)
        assert ((px != plain) == kanji).all(), 'chunk %d differs from %d beyond the kanji' % (c, PLAIN)
        boxes = frames(kanji)
        assert len(boxes) == 10, boxes
        px[kanji] = plain[kanji]
        for y0, y1, x0, x1 in boxes:
            oy, ox = (y0 + y1 - th) // 2, (x0 + x1 - tw) // 2
            px[oy:oy + th, ox:ox + tw][t] = INK
        store(d, c, px)
    return bytes(d)


def preview(out):
    from PIL import Image
    a, b = open(SRC, 'rb').read(), patch()
    grey = (np.arange(16) * 17).astype(np.uint8)
    grey[INK] = 255
    im = np.hstack([grey[pixels(a, 30)[:240]], np.full((240, 2), 128, np.uint8), grey[pixels(b, 30)[:240]]])
    im = Image.fromarray(im)
    im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(out)


if __name__ == '__main__':
    if sys.argv[1:2] == ['preview']:
        preview(sys.argv[2])
