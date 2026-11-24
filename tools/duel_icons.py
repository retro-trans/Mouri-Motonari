"""English stat icons of the duel status panel in GRAPHIC/BA_BACK.BIN (image tiles).

BA_BACK.BIN starts with a 4bpp sheet 256 halfwords (1024 px) wide, 96 rows, loaded to VRAM
(640,416) for training duels and battle attacks. Its first row holds four 16x16 icons at
x 896-959 (VRAM 864-879): Lv, 耐 (endurance), 技 (skill points), Ex. Lv and Ex are already
Latin: an orange capital (ink 5, shading c / e to its left and above) plus a small letter,
a blue square (6) behind the upper right, black ground (f) in a light frame (2).

耐 and 技 become 'En' and 'SP' in that style: the Ex icon is copied and its E / x replaced.
Terms: 耐久力 Endurance (END on the officer screen), 技能値 Skill Points (SP gauge).

    python tools/duel_icons.py preview <out.png>    original and English icons, 8x
Used by tools/build.py (patch()).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'source', 'disc', 'GRAPHIC', 'BA_BACK.BIN')
STRIDE = 512                    # bytes per row (1024 px)
ICON_X = {'Lv': 896, '耐': 912, '技': 928, 'Ex': 944}

# the glyph area of an icon: x 3-12, y 3-12 ('.' = keep the Ex icon's pixel there)
# capitals at x 0-4 (stroke 5, shading c left / above), small letter at x 6-9, y 8-12
BIG = {
    'E': ['ccccc', '55555', 'c5...', 'c5...', 'c5...', 'c5555', 'c5...', 'c5...', 'c5...',
          '55555'],
    'S': ['.cccc', 'c5555', '5c...', '5c...', '5c...', 'c555c', '....5', '....5', '....5',
          '5555c'],
}
SMALL = {
    'n': ['555f', '5ff5', '5ff5', '5ff5', '5ff5'],
    'P': ['555f', '5ff5', '555f', '5fff', '5fff'],
}
LABELS = {'耐': 'En', '技': 'SP'}


def get(d, x, y):
    b = d[y * STRIDE + x // 2]
    return (b >> 4) if x & 1 else (b & 15)


def put(d, x, y, v):
    o = y * STRIDE + x // 2
    d[o] = (d[o] & 0x0F) | (v << 4) if x & 1 else (d[o] & 0xF0) | v


def icon(d, jp, en):
    x0, ex = ICON_X[jp], ICON_X['Ex']
    for y in range(16):                             # start from the Ex icon
        for x in range(16):
            put(d, x0 + x, y, get(d, ex + x, y))
    for j, row in enumerate(BIG[en[0]]):            # capital: rows 3-12, x 3-7
        for i, c in enumerate(row):
            put(d, x0 + 3 + i, 3 + j, 15 if c == '.' else int(c, 16))
    for j, row in enumerate(SMALL[en[1]]):          # small letter: rows 8-12, x 9-12
        for i, c in enumerate(row):
            put(d, x0 + 9 + i, 8 + j, int(c, 16))


def patch(data=None):
    d = bytearray(open(SRC, 'rb').read() if data is None else data)
    for jp, en in LABELS.items():
        icon(d, jp, en)
    return bytes(d)


def preview(out):
    from PIL import Image
    pal = {2: (176, 192, 192), 5: (240, 176, 128), 6: (48, 80, 176), 12: (72, 56, 72),
           13: (56, 72, 72), 14: (40, 16, 16), 15: (0, 0, 0), 0: (96, 96, 96)}
    a, b = open(SRC, 'rb').read(), patch()
    im = Image.new('RGB', (64, 34))
    p = im.load()
    for k, d in enumerate((a, b)):
        for y in range(16):
            for x in range(64):
                p[x, y + 18 * k] = pal.get(get(d, 896 + x, y), (255, 0, 255))
    im.resize((512, 272), Image.NEAREST).save(out)


if __name__ == '__main__':
    if sys.argv[1:2] == ['preview']:
        preview(sys.argv[2])
