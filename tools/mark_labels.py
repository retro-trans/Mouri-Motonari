"""English stat / column labels in GRAPHIC/MARK.E3 (image tiles, not text).

MARK.E3 holds a 4bpp sheet loaded to VRAM (320,0): 64 halfwords (256 px) per row from
file offset 0x3920. Its top rows are 24x16 label tiles (16 or 48 px for some) with a dotted
frame on a dark dithered fill and white kanji (palette: 4-7 white shades, 8-10 / 15 greys,
2 / 3 / 11-14 dark blues). Each tile here gets its kanji removed (interior pixels in a text
or grey shade are refilled from neighbouring fill pixels) and the English label drawn in
white with a 5x7 capital font (the tiles are drawn at 1x, without the VWF), centred.

    python tools/mark_labels.py preview <out.png>    original and English tiles, 4x
Also the six 16x16 status icons (STATUS, 4x7 capitals) and the two sortie-screen buttons
(BUTTONS, 8x10 bold capitals; `python tools/mark_labels.py buttons <out.png>` previews them).
Used by tools/build.py (patch()).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'source', 'disc', 'GRAPHIC', 'MARK.E3')
BASE, STRIDE = 0x3920, 128
WHITE = 4
INKY = {1, 4, 5, 6, 7, 8, 9, 10, 15}        # kanji shades (and greys inside the frame)

# (x, y, w, jp, en) - h is 16; terms from work/glossary/terms.json and the UI columns
TILES = [
    (0, 0, 24, '武将', 'NAME'), (24, 0, 24, '知力', 'INT'), (48, 0, 24, '運気', 'LUK'),
    (72, 0, 24, '命中', 'ACC'), (96, 0, 24, '速力', 'SPD'), (120, 0, 24, '耐久', 'END'),
    (144, 0, 24, '技能', 'SP'), (168, 0, 24, '攻撃', 'ATK'), (192, 0, 24, '防御', 'DEF'),
    (216, 0, 24, '装備', 'EQP'), (240, 0, 16, '金', 'G'),
    (0, 16, 24, '経験', 'EXP'), (24, 16, 24, '重さ', 'WT'), (64, 16, 24, '部隊', 'UNIT'),
    (88, 16, 24, '属性', 'TYPE'), (112, 16, 48, '所有道具', 'ITEMS'),
    (160, 16, 48, '修得特技', 'SKILLS'), (208, 16, 24, '効果', 'EFF'), (232, 16, 24, '回復', 'HEAL'),
]

# 16x16 status icons (bottom row of the sheet), shown over units on the battle map, e.g.
# after Binding / Seal Art or a poison / fire arrow. Statuses as work/translation/en/ui
# E0570-E0574 and the Rally command E0757; 3 letters in the narrow font (NARROW).
STATUS = [
    (80, 208, 16, '集', 'RLY'), (96, 208, 16, '禁', 'SEL'), (112, 208, 16, '深', 'WND'),
    (128, 208, 16, '不', 'BND'), (144, 208, 16, '混', 'CNF'), (160, 208, 16, '凶', 'UNL'),
]

# Sortie screen buttons (green, 16 high, bevel 2 px): 出陣 -> 'GO!' as the pre-battle menu
# (E0701, glossary short), 選択終了 'end selection' -> 'DONE'. The kanji fill the button, so
# these use BIG (8x10 capitals, 2 px strokes) in the kanji's style: white / lavender strokes
# (15 / 5), dark navy shadow down-right (12), dark green halo (9) on the green fill (7).
BUTTONS = [(0, 32, 36, '出陣', 'GO!'), (36, 32, 60, '選択終了', 'DONE')]
BTN_FILL, BTN_HALO, BTN_SHADE, BTN_INK, BTN_HI = 7, 9, 12, 5, 15

BIG = {
    'D': '######..|##...##.|##....##|##....##|##....##|##....##|##....##|##....##|##...##.|######..',
    'E': '########|##......|##......|##......|#######.|##......|##......|##......|##......|########',
    'G': '.######.|##....##|##......|##......|##..####|##....##|##....##|##....##|##....##|.######.',
    'N': '##....##|###...##|###...##|####..##|##.##.##|##.##.##|##..####|##...###|##...###|##....##',
    'O': '.######.|##....##|##....##|##....##|##....##|##....##|##....##|##....##|##....##|.######.',
    '!': '##|##|##|##|##|##|##|..|##|##',
}

NARROW = {                                  # 4x7 capitals (W 5 wide) for the 16 px status icons
    'B': '###.|#..#|#..#|###.|#..#|#..#|###.', 'C': '.##.|#..#|#...|#...|#...|#..#|.##.',
    'D': '###.|#..#|#..#|#..#|#..#|#..#|###.', 'E': '####|#...|#...|###.|#...|#...|####',
    'F': '####|#...|#...|###.|#...|#...|#...', 'L': '#...|#...|#...|#...|#...|#...|####',
    'N': '#..#|##.#|##.#|#.##|#.##|#..#|#..#', 'R': '###.|#..#|#..#|###.|#.#.|#..#|#..#',
    'S': '.###|#...|#...|.##.|...#|...#|###.', 'U': '#..#|#..#|#..#|#..#|#..#|#..#|.##.',
    'W': '#...#|#...#|#...#|#.#.#|#.#.#|##.##|#...#', 'Y': '#..#|#..#|#..#|.###|...#|...#|.##.',
}


GLYPHS = {                                  # 5x7 capitals (I is 3 wide), '#' = ink
    'A': '.###.|#...#|#...#|#####|#...#|#...#|#...#', 'C': '.###.|#...#|#....|#....|#....|#...#|.###.',
    'D': '####.|#...#|#...#|#...#|#...#|#...#|####.', 'E': '#####|#....|#....|####.|#....|#....|#####',
    'F': '#####|#....|#....|####.|#....|#....|#....', 'G': '.###.|#...#|#....|#.###|#...#|#...#|.####',
    'H': '#...#|#...#|#...#|#####|#...#|#...#|#...#', 'I': '###|.#.|.#.|.#.|.#.|.#.|###',
    'K': '#...#|#..#.|#.#..|##...|#.#..|#..#.|#...#', 'L': '#....|#....|#....|#....|#....|#....|#####',
    'M': '#...#|##.##|#.#.#|#.#.#|#...#|#...#|#...#', 'N': '#...#|##..#|#.#.#|#..##|#...#|#...#|#...#',
    'P': '####.|#...#|#...#|####.|#....|#....|#....', 'Q': '.###.|#...#|#...#|#...#|#.#.#|#..#.|.##.#',
    'S': '.####|#....|#....|.###.|....#|....#|####.', 'T': '#####|..#..|..#..|..#..|..#..|..#..|..#..',
    'U': '#...#|#...#|#...#|#...#|#...#|#...#|.###.', 'W': '#...#|#...#|#...#|#.#.#|#.#.#|##.##|#...#',
    'X': '#...#|#...#|.#.#.|..#..|.#.#.|#...#|#...#', 'Y': '#...#|#...#|.#.#.|..#..|..#..|..#..|..#..',
}


def font(glyphs=None):
    """{char: (width, rows of pixels)} for the label font (or NARROW)"""
    out = {}
    for c, g in (glyphs or GLYPHS).items():
        rows = [[1 if ch == '#' else 0 for ch in r] for r in g.split('|')]
        out[c] = (len(rows[0]), rows)
    return out


def get(d, x, y):
    b = d[BASE + y * STRIDE + x // 2]
    return (b >> 4) if x & 1 else (b & 15)


def put(d, x, y, v):
    o = BASE + y * STRIDE + x // 2
    d[o] = (d[o] & 0x0F) | (v << 4) if x & 1 else (d[o] & 0xF0) | v


def clear(d, x0, y0, w, h=16, edge=0):
    """refill interior text pixels with the surrounding fill (frame = left column and top
    row; the next tile's frame closes the other sides; edge=1 also keeps the right column
    and bottom row, as the status icons have a frame of their own there)"""
    todo = {(x, y) for y in range(y0 + 1, y0 + h - edge) for x in range(x0 + 1, x0 + w - edge)
            if get(d, x, y) in INKY}
    while todo:
        done = []
        for x, y in todo:
            nb = [get(d, a, b) for a, b in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
                  if x0 < a < x0 + w and y0 < b < y0 + h and (a, b) not in todo]
            if nb:
                done.append((x, y, max(set(nb), key=nb.count)))
        if not done:
            break
        for x, y, v in done:
            put(d, x, y, v)
            todo.discard((x, y))


def draw(d, x0, y0, w, text, f, h=16):
    room = w - 1                                    # right of the left frame column
    width = sum(f[c][0] for c in text) + len(text) - 1
    assert width <= room, 'label too wide: %s (%d px > %d)' % (text, width, room)
    x = x0 + 1 + (room - width + 1) // 2
    y = y0 + 1 + (h - 1 - 7) // 2
    for c in text:
        cw, g = f[c]
        for j, r in enumerate(g):
            for a, v in enumerate(r):
                if v:
                    put(d, x + a, y + j, WHITE)
        x += cw + 1


def button(d, x0, y0, w, text, f, h=16):
    """repaint a sortie-screen button's inside (bevel kept) with text in BIG"""
    ix0, ix1, iy0, iy1 = x0 + 2, x0 + w - 3, y0 + 2, y0 + h - 3     # inside the bevel
    width = sum(f[c][0] for c in text) + 2 * (len(text) - 1)
    assert width + 2 <= ix1 - ix0 + 1, 'button text too wide: %s' % text
    ink = set()
    x = ix0 + (ix1 - ix0 + 1 - width - 1) // 2
    y = iy0
    for c in text:
        cw, g = f[c]
        ink |= {(x + a, y + j) for j, r in enumerate(g) for a, v in enumerate(r) if v}
        x += cw + 2
    shade = {(a + 1, b + 1) for a, b in ink} - ink
    near = {(a + i, b + j) for a, b in ink | shade for i in (-1, 0, 1) for j in (-1, 0, 1)}
    for yy in range(iy0, iy1 + 1):
        for xx in range(ix0, ix1 + 1):
            p = (xx, yy)
            if p in ink:
                v = BTN_HI if (xx - 1, yy) not in ink or (xx, yy - 1) not in ink else BTN_INK
            elif p in shade:
                v = BTN_SHADE
            elif p in near:
                v = BTN_HALO
            else:
                v = BTN_FILL
            put(d, xx, yy, v)


def patch(data=None):
    d = bytearray(open(SRC, 'rb').read() if data is None else data)
    f = font()
    for x, y, w, jp, en in TILES:
        clear(d, x, y, w)
        draw(d, x, y, w, en, f)
    n = font(NARROW)
    for x, y, w, jp, en in STATUS:
        clear(d, x, y, w, edge=1)
        width = sum(n[c][0] for c in en) + len(en) - 1
        draw(d, x, y, w - (width < w - 1), en, n)    # inside the frame; 'WND' needs all 15 px
    b = font(BIG)
    for x, y, w, jp, en in BUTTONS:
        button(d, x, y, w, en, b)
    return bytes(d)


def preview_buttons(out):
    """original and English sortie buttons, 6x, in the colours seen in the game"""
    from PIL import Image
    pal = {5: (189, 189, 222), 15: (255, 255, 255), 7: (82, 181, 58), 9: (49, 115, 25),
           12: (25, 8, 58), 8: (74, 90, 123), 10: (64, 64, 64), 0: (0, 0, 0)}
    a, b = open(SRC, 'rb').read(), patch()
    im = Image.new('RGB', (96, 34))
    p = im.load()
    for k, d in enumerate((a, b)):
        for y in range(16):
            for x in range(96):
                p[x, y + 18 * k] = pal.get(get(d, x, 32 + y), (255, 0, 255))
    im.resize((im.width * 6, im.height * 6), Image.NEAREST).save(out)


def preview(out):
    from PIL import Image
    pal = {0: (0, 0, 0), 1: (255, 0, 255), 2: (40, 48, 104), 3: (32, 40, 96), 4: (240, 240, 248),
           5: (224, 224, 240), 6: (208, 208, 232), 7: (184, 184, 216), 8: (144, 144, 184),
           9: (120, 120, 168), 10: (104, 104, 152), 11: (24, 24, 80), 12: (0, 0, 24),
           13: (0, 0, 40), 14: (0, 0, 48), 15: (80, 72, 128)}
    a, b = open(SRC, 'rb').read(), patch()
    rows = list(range(32)) + list(range(208, 224))          # label tiles, status icons
    im = Image.new('RGB', (256, 2 * len(rows) + 2))
    p = im.load()
    for k, d in enumerate((a, b)):
        for j, y in enumerate(rows):
            for x in range(256):
                p[x, j + (len(rows) + 2) * k] = pal[get(d, x, y)]
    im.resize((im.width * 4, im.height * 4), Image.NEAREST).save(out)


if __name__ == '__main__':
    if sys.argv[1:2] == ['preview']:
        preview(sys.argv[2])
    elif sys.argv[1:2] == ['buttons']:
        preview_buttons(sys.argv[2])
