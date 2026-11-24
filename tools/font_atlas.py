"""Build the 2x-density (4x pixel) proportional font atlas for the VWF hooks.

Text font: Skies of Arcadia's Latin bitmap font (tools/skies_font.py, decoded from
the user's Skies disc at build time, as in the Seireiki Rayblade translation), with
GenEi (outline font below) for the few characters it lacks: [ \ ] ' ' -- ... e-acute.

Glyphs are rasterised at 2x the on-screen size and drawn by the game as
POLY_FT4 quads at 1x, so emulators with upscaling show the full detail.

Output (python dict / binary blobs):
  atlas   : 1bpp bitmap, 256 texels wide, ATLAS_H rows, 32 bytes per row, bit7 = left
  glyphs  : 128 entries x 8 bytes: u, v, w, h, xoff(s8), yoff, adv(px @1x), 0
            (u,v,w,h,xoff,yoff in texels; quads are w/2 x h/2 screen pixels)
Glyph ids: 0x20-0x7E ASCII, 0x01-0x07 extra punctuation (see EXTRA),
           0x7F placeholder box for characters without a glyph.

    python tools/font_atlas.py --preview work/ui/font/atlas.png
"""
import argparse
import math
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Text font (dialogue 2x atlas + 1x menu font).  RS_FONT=noto selects the old one.
FONTS = {
    # name: (file, ttc index, 2x size, 1x size, space advance on screen or None)
    'genei': (os.path.join(ROOT, 'tools', 'fonts', 'genei-latin', 'GenEiLateGo_v2.ttc'), 0, 24, 12, 3),
    'noto': (os.path.join(ROOT, 'tools', 'fonts', 'noto-sans-cjk-jp', 'NotoSansCJKjp-Regular.otf'), 0, 26, 13, None),
}
FONT_NAME = os.environ.get('RS_FONT', 'genei')
FONT, FONT_INDEX, SIZE, SIZE1X, SPACE_ADV = FONTS[FONT_NAME]
BASELINE = 24        # 2x px from the top of the 32 px (2x) line to the baseline


def load_font(size):
    return ImageFont.truetype(FONT, size, index=FONT_INDEX)


LINE_TOP = load_font(SIZE).getbbox('H')[3] - BASELINE    # PIL y that maps to the line top
ATLAS_W = 256
ATLAS_H = 126        # rows usable (row 127 holds the CLUT)
EXTRA = {0x01: '‘', 0x02: '’', 0x03: '“', 0x04: '”',
         0x05: '—', 0x06: '…', 0x07: 'é'}
PLACEHOLDER = 0x7F
WIDE_SPACE = 0x08   # full-width space: no ink, 16 px (keeps menu columns / cursor gaps)
THRESHOLD = 110      # coverage -> ink (1bpp)


def glyph_chars():
    m = {c: chr(c) for c in range(0x20, 0x7F)}
    m.update(EXTRA)
    return m


SS = 4               # supersampling factor for the 1bpp coverage
EMBOLDEN = {'genei': 1, 'noto': 0}.get(FONT_NAME, 0)   # stroke at SS scale = 1/SS px
COVER = {'genei': 100, 'noto': THRESHOLD}.get(FONT_NAME, THRESHOLD)  # ink if coverage >= COVER/255


def coverage(ch, size, pad=4):
    """Glyph coverage at `size`, rendered at SS x and box-filtered (thin strokes keep
    partial coverage instead of vanishing), slightly emboldened for thin fonts.
    Returns (L image, origin x, origin y): pen origin / PIL text origin in the image."""
    f = load_font(size * SS)
    x0, y0, x1, y1 = f.getbbox(ch, stroke_width=EMBOLDEN)
    ox, oy = pad * SS - (x0 // SS) * SS, pad * SS - (y0 // SS) * SS
    w = ((x1 - x0) // SS + 2 * pad + 1) * SS
    h = ((y1 - y0) // SS + 2 * pad + 1) * SS
    img = Image.new('L', (w, h), 0)
    ImageDraw.Draw(img).text((ox, oy), ch, font=f, fill=255, stroke_width=EMBOLDEN, stroke_fill=255)
    return img.resize((w // SS, h // SS), Image.BOX), ox // SS, oy // SS


def ink_rows(ch, size, cover):
    """(rows of 0/1, x of first column, y of first row) relative to the PIL text origin."""
    img, ox, oy = coverage(ch, size)
    px = img.load()
    w, h = img.size
    ink = [[1 if px[x, y] >= cover else 0 for x in range(w)] for y in range(h)]
    ys = [y for y in range(h) if any(ink[y])]
    xs = [x for x in range(w) if any(ink[y][x] for y in range(h))]
    if not ys:
        return [], 0, 0
    return [r[xs[0]:xs[-1] + 1] for r in ink[ys[0]:ys[-1] + 1]], xs[0] - ox, ys[0] - oy


# Bitmap text font (tools/skies_font.py: Skies of Arcadia's Latin font, as in the Rayblade
# translation).  RS_BITMAP=none renders everything from the outline font above.
BITMAP = os.environ.get('RS_BITMAP', 'skies')
SKIES_COVER = 128            # ink = the two strongest of its four coverage levels
SKIES_GAP = 2                # 2x texels between glyphs (1 screen px)
SKIES_MAP = {'“': '[', '”': ']'}   # its [ ] cells hold curly double quotes
SKIES_NONE = set('[\]')     # cells holding other glyphs (" yen ") -> outline font


def skies_mask(ch):
    """12x24 coverage mask of ch in the bitmap font, or None (outline font fallback)."""
    if BITMAP != 'skies' or ch in SKIES_NONE:
        return None
    import skies_font
    return skies_font.glyph(SKIES_MAP.get(ch, ch))


_SKIES_BASE = []


def skies_baseline():
    """Row below the ink of 'H' in the 12x24 cell."""
    if not _SKIES_BASE:
        m = skies_mask('H').load()
        _SKIES_BASE.append(max(y for y in range(24) for x in range(12) if m[x, y] >= SKIES_COVER) + 1)
    return _SKIES_BASE[0]


# Edge smoothing of the bitmap font in the 2x atlas (FONT_AA):
#   'stp' : 2 bits per texel = the font's four coverage levels; the faintest is a
#           semi-transparent CLUT entry (STP), drawn 50 % see-through by the
#           semi-transparent quads; the two strongest are solid ink.
#   'off' : 1 bit per texel, ink = the two strongest levels (builds 0.4.6-0.4.7).
FONT_AA = os.environ.get('RS_FONT_AA', 'stp')
AA = FONT_AA == 'stp' and BITMAP == 'skies'
SKIES_LEVEL = {0: 0, 85: 1, 187: 2, 255: 3}     # coverage -> atlas value (2-bit mode)


def skies_box(ch):
    """((crop rect in the 12x24 cell), yoff from the line top, xoff from the pen, ink width)
    of the even-aligned glyph box.  The pen sits at the left of the solid ink (levels
    >= SKIES_COVER); in the 2-bit mode the box also takes the faint edge pixels."""
    m = skies_mask(ch)
    if m is None:
        return None
    px = m.load()
    solid = [(x, y) for y in range(24) for x in range(12) if px[x, y] >= SKIES_COVER]
    if not solid:
        return None
    lo = 1 if AA else SKIES_COVER
    ink = [(x, y) for y in range(24) for x in range(12) if px[x, y] >= lo]
    left = min(x for x, _ in solid)
    ink_w = max(x for x, _ in solid) + 1 - left
    x0, x1 = min(x for x, _ in ink), max(x for x, _ in ink) + 1
    x0 -= (left - x0) & 1                           # xoff even (whole screen pixels)
    y0, y1 = min(y for _, y in ink), max(y for _, y in ink) + 1
    top = y0 + BASELINE - skies_baseline()          # line-relative (2x texels)
    if top & 1:
        y0, top = y0 - 1, top - 1
    x1 += (x1 - x0) & 1
    y1 += (y1 - y0) & 1
    return (x0, y0, x1, y1), top, x0 - left, ink_w


def render_skies(ch):
    b = skies_box(ch)
    if b is None:
        return None
    (x0, y0, x1, y1), top, xoff, ink_w = b
    px = skies_mask(ch).load()

    def cov(x, y):
        return px[x, y] if 0 <= x < 12 and 0 <= y < 24 else 0
    if AA:
        rows = [[SKIES_LEVEL[cov(x, y)] for x in range(x0, x1)] for y in range(y0, y1)]
    else:
        rows = [[1 if cov(x, y) >= SKIES_COVER else 0 for x in range(x0, x1)] for y in range(y0, y1)]
    return rows, xoff, top, (ink_w + SKIES_GAP + 1) // 2


def render(ch, font):
    """Return (bitmap rows as list of lists 0/1, xoff, yoff, adv_px) cropped to even box."""
    r = render_skies(ch)
    if r:
        return r
    adv = font.getlength(ch)
    rows0, x0, y0 = ink_rows(ch, font.size, COVER)
    if not rows0:
        return [], 0, 0, max(1, math.floor(adv / 2 + 0.5))
    x1, y1 = x0 + len(rows0[0]), y0 + len(rows0)
    # even-aligned box relative to pen origin / line top
    bx0 = x0 - (x0 & 1)
    by0 = y0 - ((y0 - LINE_TOP) & 1)
    bx1 = x1 + ((x1 - bx0) & 1)
    by1 = y1 + ((y1 - by0) & 1)
    rows = []
    for y in range(by0, by1):
        rows.append([rows0[y - y0][x - x0] if y0 <= y < y1 and x0 <= x < x1 else 0 for x in range(bx0, bx1)])
    # advance rounded half-up (Python's round() is half-to-even: 6.5 -> 6 but
    # 7.5 -> 8, which made some letters touch and others gap)
    return rows, bx0, by0 - LINE_TOP, max(1, math.floor(adv / 2 + 0.5))


def placeholder():
    w, h = 24, 24
    rows = [[1 if (x in (0, 1, w - 2, w - 1) or y in (0, 1, h - 2, h - 1)) else 0 for x in range(w)] for y in range(h)]
    return rows, 4, 6, 16


def build(size=SIZE):
    font = load_font(size)
    chars = glyph_chars()
    items = {gid: render(ch, font) for gid, ch in chars.items()}
    items[PLACEHOLDER] = placeholder()
    items[WIDE_SPACE] = ([], 0, 0, 16)
    if SPACE_ADV:
        items[0x20] = ([], 0, 0, SPACE_ADV)
    if AA:                               # outline-font / placeholder ink -> full level
        for g, (rows, xoff, yoff, adv) in items.items():
            if rows and g not in _skies_gids(chars):
                items[g] = ([[3 if v else 0 for v in r] for r in rows], xoff, yoff, adv)
    # shelf packing, tallest first
    order = sorted((g for g in items if items[g][0]), key=lambda g: (-len(items[g][0]), g))
    atlas = [[0] * ATLAS_W for _ in range(ATLAS_H)]
    place = {}
    shelf_y, shelf_h, x = 0, 0, 0
    for g in order:
        rows = items[g][0]
        w, h = len(rows[0]), len(rows)
        if x + w > ATLAS_W - 1:          # keep u+w <= 255
            shelf_y += shelf_h
            shelf_h, x = 0, 0
        if shelf_h == 0:
            shelf_h = h + (h & 1)
        if shelf_y + h > ATLAS_H:
            raise SystemExit('atlas overflow at glyph %02x (size %d)' % (g, size))
        for yy in range(h):
            atlas[shelf_y + yy][x:x + w] = rows[yy]
        place[g] = (x, shelf_y, w, h)
        x += w
    glyphs = bytearray(128 * 8)
    for g, (rows, xoff, yoff, adv) in items.items():
        u, v, w, h = place.get(g, (0, 0, 0, 0))
        glyphs[g * 8:g * 8 + 8] = bytes((u, v, w, h, xoff & 0xFF, yoff, adv, 0))
    used = shelf_y + shelf_h
    packed = bytearray()
    for y in range(ATLAS_H):
        if AA:                           # 2 bits per texel, first texel in the low bits
            for bx in range(0, ATLAS_W, 4):
                packed.append(sum(atlas[y][bx + k] << (2 * k) for k in range(4)))
        else:                            # 1 bit per texel, first texel in bit 7
            for bx in range(0, ATLAS_W, 8):
                b = 0
                for k in range(8):
                    b = (b << 1) | atlas[y][bx + k]
                packed.append(b)
    return {'atlas': bytes(packed), 'glyphs': bytes(glyphs), 'rows_used': used,
            'bitmap': atlas, 'place': place, 'items': items, 'row_bytes': ROW_BYTES}


ROW_BYTES = 64 if AA else 32             # atlas bytes per row (256 texels)
# CLUT of the expanded 4bpp atlas: 0 transparent, ink white.  2-bit mode: 1 = faint
# (STP set: 50 % see-through on the semi-transparent quads), 2-3 = solid.
CLUT = [0x0000, 0xFFFF, 0x7FFF, 0x7FFF] if AA else [0x0000, 0x7FFF]
QUAD_CODE = 0x2E if AA else 0x2C         # POLY_FT4, semi-transparent (mode 0: average) or opaque


def _skies_gids(chars):
    return {g for g, ch in chars.items() if render_skies(ch)}


_BUILT = []


def line_coverage(s, spacing=0):
    """Coverage image (L) of one line of text at the atlas' 2x density: 32 rows,
    baseline at BASELINE, pen positions as in the game (bitmap glyphs with their
    four coverage levels, outline-font fallback glyphs from the atlas).
    spacing: extra 2x texels between glyphs.  Returns (image, cap top row)."""
    from PIL import Image
    if not _BUILT:
        _BUILT.append(build())
    items = _BUILT[0]['items']
    gid_of = {c: g for g, c in glyph_chars().items()}
    parts, pen = [], 0
    for ch in s:
        g = gid_of.get(ch, PLACEHOLDER)
        rows, xoff, yoff, adv = items.get(g, items[PLACEHOLDER])
        b = skies_box(ch)
        if b:
            (x0, y0, x1, y1), top, xoff, _ = b
            parts.append((skies_mask(ch).crop((x0, y0, x1, y1)), pen + xoff, top))
        elif rows:
            img = Image.new('L', (len(rows[0]), len(rows)))
            img.putdata([255 if v else 0 for r in rows for v in r])
            parts.append((img, pen + xoff, yoff))
        pen += adv * 2 + spacing
    out = Image.new('L', (max(1, pen), 32), 0)
    for img, x, y in parts:
        out.paste(img, (x, y), img)
    m = skies_mask('H')
    if m:                                           # top of the solid ink of 'H'
        hp = m.load()
        cap_top = BASELINE - skies_baseline() + min(y for y in range(24) for x in range(12)
                                                     if hp[x, y] >= SKIES_COVER)
    else:
        cap_top = BASELINE - 17
    return out, cap_top


THRESHOLD1X = 80
COVER1X = {'genei': 90, 'noto': THRESHOLD1X}.get(FONT_NAME, THRESHOLD1X)


def build1x():
    """1x font for canvas-rendered UI text (menus, names): 1bpp rows, MSB = left.

    Returns {'table': 128 x 8 bytes (off u16, w, h, xoff s8, yoff, adv, bpr),
             'data': row bytes}.  Metrics are in screen pixels; yoff is from the
    top of the 16 px cell.  Advances match the 2x font (same em at half size)."""
    font = load_font(SIZE1X)
    big = build()['glyphs']
    _, _, _, base = font.getbbox('H')
    top = base - 12                     # baseline 12 px below the cell top
    table = bytearray(128 * 8)
    data = bytearray()
    for gid, ch in glyph_chars().items():
        adv = big[gid * 8 + 6]
        rows0, x0, y0 = ink_rows(ch, SIZE1X, COVER1X)
        if not rows0:
            table[gid * 8:gid * 8 + 8] = bytes((0, 0, 0, 0, 0, 0, adv, 0))
            continue
        x1, y1 = x0 + len(rows0[0]), y0 + len(rows0)
        cy0, cy1 = max(y0, top), min(y1, top + 16)
        w = x1 - x0
        bpr = (w + 7) // 8
        off = len(data)
        for y in range(cy0, cy1):
            bits = 0
            for x in range(bpr * 8):
                bits = (bits << 1) | (rows0[y - y0][x] if x < w else 0)
            data += bits.to_bytes(bpr, 'big')
        y0, h = cy0, cy1 - cy0
        table[gid * 8:gid * 8 + 8] = bytes((off & 0xFF, off >> 8, w, h, x0 & 0xFF, y0 - top, adv, bpr))
    # placeholder box and wide space
    off = len(data)
    rows = [0xFFF0] + [0x8010] * 10 + [0xFFF0]
    for r in rows:
        data += r.to_bytes(2, 'big')
    table[PLACEHOLDER * 8:PLACEHOLDER * 8 + 8] = bytes((off & 0xFF, off >> 8, 12, 12, 2, 2, 16, 2))
    table[WIDE_SPACE * 8:WIDE_SPACE * 8 + 8] = bytes((0, 0, 0, 0, 0, 0, 16, 0))
    return {'table': bytes(table), 'data': bytes(data)}


def measure(text, glyphs):
    """Pixel width of an ASCII/extra-glyph string using the built metrics."""
    return sum(glyphs[ord(c) * 8 + 6] if ord(c) < 128 else 16 for c in text)


def preview(res, path, sample=None):
    a = res['bitmap']
    img = Image.new('RGB', (ATLAS_W * 3, ATLAS_H * 2 + 80), (24, 24, 40))
    for y in range(ATLAS_H):
        for x in range(ATLAS_W):
            if a[y][x]:
                img.putpixel((x * 2, y * 2), (255, 255, 255))
                img.putpixel((x * 2 + 1, y * 2), (255, 255, 255))
                img.putpixel((x * 2, y * 2 + 1), (255, 255, 255))
                img.putpixel((x * 2 + 1, y * 2 + 1), (255, 255, 255))
    if sample:
        g = res['glyphs']
        pen = 4
        base = ATLAS_H * 2 + 8
        for ch in sample:
            gid = ord(ch) if ord(ch) < 128 else PLACEHOLDER
            u, v, w, h, xo, yo, adv, _ = g[gid * 8:gid * 8 + 8]
            xo = xo - 256 if xo > 127 else xo
            for yy in range(h):
                for xx in range(w):
                    if a[v + yy][u + xx]:
                        img.putpixel((pen * 2 + xo + xx, base + yo + yy), (240, 230, 200))
            pen += adv
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    img.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--size', type=int, default=SIZE)
    ap.add_argument('--preview')
    a = ap.parse_args()
    res = build(a.size)
    print('rows used %d / %d, glyphs %d' % (res['rows_used'], ATLAS_H, len(res['place'])))
    if a.preview:
        preview(res, a.preview, 'Search the area! They must have fled this way.')


if __name__ == '__main__':
    main()
