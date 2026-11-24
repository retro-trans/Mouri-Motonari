"""English province names on the world maps in GRAPHIC/MMAP.E3 (painted into the images).

MMAP.E3 is 135 full-screen backgrounds, each 0x13000 bytes: a 256-colour CLUT (512 bytes,
15-bit), 320x240 8-bit pixels, 512 bytes of 0xFF padding. Images 0-2 are the maps of the
Chugoku region, of western Japan with Kyushu / Shikoku, and of the Kinai; their province
names are light cyan kanji with a dark drop shadow, painted over the terrain.

For each label: the kanji pixels inside a rough box (light cyan, plus 1 px around them for
the shadow) are erased and refilled (smooth fill from the edge of the hole plus the fine
texture of the terrain just above or below), then the English name is drawn with the dialogue font
(work/source/skies_font.png, scaled to the kanji size, smooth edges; 'm' is built from two
'n's so its stems survive) in the label cyan with a dark outline, centred on the old label
(dx / dy move it where neighbours or castles are in the way). The result is mapped back
to the image's own 256 colours.

    python tools/map_labels.py preview <out.png>    original and English maps, 2x
Used by tools/build.py (patch()). Spellings follow work/glossary (no macrons: Suo, Hoki).
"""
import os
import sys

import numpy as np


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'source', 'disc', 'GRAPHIC', 'MMAP.E3')
CH = 0x13000
W, H = 320, 240

# image: [(x0, y0, x1, y1 rough box of the kanji, jp, en, dx, dy)]
LABELS = {
    0: [(235, 55, 257, 66, '出雲', 'Izumo', 0, 0), (71, 86, 96, 98, '石見', 'Iwami', 0, 0),
        (178, 106, 201, 117, '安芸', 'Aki', 0, 0), (252, 113, 276, 125, '備後', 'Bingo', 0, 0),
        (33, 176, 57, 187, '周防', 'Suo', 0, 0)],
    1: [(278, 49, 302, 60, '出雲', 'Izumo', 0, 0), (266, 86, 291, 98, '備後', 'Bingo', 0, 0),
        (193, 103, 216, 115, '安芸', 'Aki', 0, 0), (139, 108, 162, 120, '石見', 'Iwami', 2, 0),
        (49, 114, 73, 126, '長門', 'Nagato', 0, 0), (126, 136, 151, 149, '周防', 'Suo', 0, 0),
        (44, 166, 67, 178, '豊前', 'Buzen', 3, 0), (57, 196, 82, 208, '豊後', 'Bungo', 0, 0),
        (230, 203, 255, 215, '伊予', 'Iyo', 0, 0)],
    2: [(207, 21, 229, 35, '越前', 'Echizen', 0, 0), (262, 25, 282, 37, '美濃', 'Mino', 0, 0),
        (275, 47, 297, 58, '尾張', 'Owari', 0, 0), (297, 63, 318, 73, '三河', 'Mikawa', 0, 0),
        (151, 63, 172, 74, '但馬', 'Tajima', 0, 0), (115, 72, 138, 85, '因幡', 'Inaba', 3, 0),
        (186, 85, 206, 95, '丹波', 'Tanba', 0, 0), (81, 102, 99, 113, '伯耆', 'Hoki', 0, 0),
        (46, 107, 65, 118, '出雲', 'Izumo', 0, 0), (154, 108, 173, 119, '播磨', 'Harima', -3, 0),
        (188, 106, 209, 117, '摂津', 'Settsu', -1, -4), (215, 113, 235, 123, '山城', 'Yamashiro', 4, 0),
        (250, 116, 269, 127, '伊勢', 'Ise', 8, 0), (119, 118, 139, 130, '美作', 'Mimasaka', 0, 0),
        (95, 143, 115, 153, '備前', 'Bizen', 0, 0), (225, 147, 245, 157, '大和', 'Yamato', 0, 0),
        (58, 164, 78, 174, '備中', 'Bitchu', -4, 0), (19, 175, 40, 186, '安芸', 'Aki', 0, 0),
        (194, 186, 216, 197, '紀伊', 'Kii', 0, 0)],
}
FILL = (112, 184, 216)          # label cyan (the kanji are 88-120, 160-176, 192-200)
TOP = (152, 208, 232)           # lighter top rows, as the kanji
EDGE = (8, 16, 24)              # outline / shadow


def load(d, i):
    o = i * CH
    pal = np.frombuffer(bytes(d[o:o + 512]), '<u2').astype(int)
    idx = np.frombuffer(bytes(d[o + 512:o + 512 + W * H]), np.uint8).reshape(H, W)
    rgb = np.stack([(pal & 31) << 3, ((pal >> 5) & 31) << 3, ((pal >> 10) & 31) << 3], 1)
    return pal, idx, rgb


def kanji_mask(img, box):
    x0, y0, x1, y1 = box
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    m = (b - r >= 30) & (g - r >= 20) & (b >= 120) & (g >= 110)
    inside = np.zeros_like(m)
    inside[y0 - 2:y1 + 3, x0 - 2:x1 + 3] = True             # the boxes are rough
    m &= inside
    out = m.copy()                                  # 1 px around: the shadow and soft edges
    for dy in (-1, 0, 1, 2):
        for dx in (-1, 0, 1, 2):
            out |= np.roll(np.roll(m, dy, 0), dx, 1)
    near = np.zeros_like(m)
    near[y0 - 3:y1 + 5, x0 - 3:x1 + 5] = True
    return out & near


def blur(a, n=2):
    out = a.copy()
    for _ in range(n):
        p = np.pad(out, ((1, 1), (1, 1), (0, 0)), mode='edge')
        out = (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:] + 4 * p[1:-1, 1:-1]) / 8
    return out


def fill(img, hole):
    """smooth fill of the hole from its edge (diffusion) + terrain texture from above / below"""
    a = img.astype(float)
    known = ~hole
    out = a.copy()
    out[hole] = a[known].mean(0)
    for _ in range(400):                            # Laplace fill
        p = np.pad(out, ((1, 1), (1, 1), (0, 0)), mode='edge')
        avg = (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]) / 4
        out[hole] = avg[hole]
    ys, xs = np.nonzero(hole)
    h = ys.max() - ys.min() + 3
    detail = a - blur(a)
    best = None
    for sy in (-h, h, -2 * h, 2 * h):               # a donor strip with no hole in it
        ty = ys + sy
        if ty.min() < 0 or ty.max() >= H or hole[ty, xs].any():
            continue
        err = np.abs(blur(a)[ty, xs] - out[ys, xs]).mean()
        if best is None or err < best[0]:
            best = (err, sy)
    if best:
        out[ys, xs] += detail[ys + best[1], xs]
    return np.clip(out, 0, 255)


SKIES = os.path.join(ROOT, 'work', 'source', 'skies_font.png')   # the dialogue font (2x cells)
CAP_TOP, BASE = 2, 20                        # cap top / baseline rows in a 12x24 cell
SCALE = {0: 0.6, 1: 0.6, 2: 0.5}             # 2x cells -> map pixels, per map (kanji size)


def glyph_alpha(c, scale):
    """one glyph of the dialogue font at map scale, own pixel grid (stems stay sharp)"""
    from PIL import Image
    if c == 'm':                     # two 'n's sharing a stem: 'm' scaled down reads as 'n'
        n = glyph_alpha('n', scale)
        return np.hstack([n[:, :-1], n])
    sheet = np.asarray(Image.open(SKIES).convert('L'))
    cell = sheet[:, (ord(c) - 32) * 12:(ord(c) - 31) * 12]
    cols = np.nonzero(cell.max(0) > 25)[0]
    cell = cell[:, cols[0]:cols[-1] + 1]
    w = max(1, int(round(cell.shape[1] * scale)))
    small = Image.fromarray(cell).resize((w, int(round(24 * scale))), Image.BOX)
    return np.clip(np.asarray(small, float) / 255 * 1.3, 0, 1)


def text_alpha(text, scale):
    """coverage (0-1) of the text at map scale, 1 px between glyphs; -> (alpha, cap_top, base)"""
    h = int(round(24 * scale))
    parts = []
    for c in text:
        parts.append(np.zeros((h, 3)) if c == ' ' else glyph_alpha(c, scale))
        parts.append(np.zeros((h, 1)))
    return np.hstack(parts[:-1]), CAP_TOP * scale, BASE * scale


def shift(a, dy, dx):
    out = np.zeros_like(a)
    h, w = a.shape
    out[max(dy, 0):h + min(dy, 0), max(dx, 0):w + min(dx, 0)] = \
        a[max(-dy, 0):h - max(dy, 0), max(-dx, 0):w - max(dx, 0)]
    return out


def draw(img, box, text, dx, dy, scale):
    x0, y0, x1, y1 = box
    t, top, base = text_alpha(text, scale)
    th, tw = t.shape
    ox = min(max((x0 + x1 + 1 - tw) // 2 + dx, 2), W - tw - 3)    # keep it on screen
    oy = int(round((y0 + y1 + 1) / 2 - (top + base) / 2)) + dy      # centre the capitals
    a = np.zeros((H, W))
    a[oy:oy + th, ox:ox + tw] = t
    edge = np.zeros_like(a)                                          # outline, heavier down-right
    for ddy, ddx, k in ((-1, 0, .8), (1, 0, 1), (0, -1, .8), (0, 1, 1), (1, 1, 1), (-1, -1, .5),
                        (1, -1, .7), (-1, 1, .7), (2, 1, .6), (1, 2, .6), (2, 2, .5)):
        edge = np.maximum(edge, shift(a, ddy, ddx) * k)
    edge = np.clip(edge * 1.3, 0, 1)[..., None]
    img[:] = img * (1 - edge) + np.array(EDGE) * edge
    grad = np.zeros((H, 1, 3)) + FILL                                 # lighter top, as the kanji
    grad[oy:oy + int(top + 3)] = TOP
    a = a[..., None]
    img[:] = img * (1 - a) + grad * a
    return ox, oy, tw


def nearest(rgb_pal, a):
    """map RGB pixels to the nearest palette index"""
    p = rgb_pal.astype(float)
    d = ((a[:, None, :] - p[None, :, :]) ** 2).sum(-1)
    return d.argmin(1).astype(np.uint8)



def patch(data=None):
    d = bytearray(open(SRC, 'rb').read() if data is None else data)
    for i, labels in LABELS.items():
        pal, idx, rgb = load(d, i)
        img = rgb[idx].astype(float)
        hole = np.zeros((H, W), bool)
        for x0, y0, x1, y1, jp, en, dx, dy in labels:
            hole |= kanji_mask(img, (x0, y0, x1, y1))
        new = fill(img, hole)
        for x0, y0, x1, y1, jp, en, dx, dy in labels:
            draw(new, (x0, y0, x1, y1), en, dx, dy, SCALE[i])
        changed = np.abs(new - img).sum(-1) > 0
        out = idx.copy()
        out[changed] = nearest(rgb, new[changed])
        o = i * CH + 512
        d[o:o + W * H] = out.tobytes()
    return bytes(d)


def render(d, i):
    pal, idx, rgb = load(d, i)
    return rgb[idx].astype(np.uint8)


def preview(path):
    from PIL import Image
    a, b = open(SRC, 'rb').read(), patch()
    rows = [np.hstack([render(a, i), np.zeros((H, 4, 3), np.uint8), render(b, i)]) for i in LABELS]
    im = Image.fromarray(np.vstack(rows))
    im.resize((im.width * 2, im.height * 2), Image.NEAREST).save(path)


if __name__ == '__main__':
    if sys.argv[1:2] == ['preview']:
        preview(sys.argv[2])
