"""Edit movie frames for the translation: burned-in subtitles and replaced on-screen labels.

    python tools/movie_edit.py MOVIE01 [--frames 1000-1100] [--sheet out.png]

Input:  work/translation/en/movie/<name>.json (subtitles in seconds, labels in frames) and the
        frames decoded by jPSXdec (work/source/movie/<name>/, tools/movie.py decode).
Output: work/output/movie/<name>/NNNN.png (only the frames that change) + replace.xml for
        jPSXdec -replaceframes (whole-frame replace: one quantization scale per STRv2 frame).

Subtitles: a black band over the bottom three macroblock rows (y 192-239) while a line is
shown, text centred on it. A flat band costs almost nothing to encode, so the text keeps a
low quantization scale (sharp) in the 8 video sectors each frame has.

Labels (white kanji with a dark shadow over the map): the map behind them is still, so the
Japanese is removed by putting back the same pixels from a frame before the labels appear
("ref", same phase of the 4-frame water cycle), scaled by a smooth per-pixel gain field (the
map dims around the portraits). Where the map moves ("motion"), the ref is warped with a
zoom + shift found by search. The English is drawn where the Japanese was, following its
position, size and opacity frame by frame (fly-in, fade), measured from the removed pixels.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TR = os.path.join(ROOT, 'work', 'translation', 'en', 'movie')
SRC = os.path.join(ROOT, 'work', 'source', 'movie')
OUT = os.path.join(ROOT, 'work', 'output', 'movie')
FONT = os.path.join(ROOT, 'tools', 'fonts', 'genei-latin', 'GenEiLateGo_v2.ttc')
FPS = 15
W, H = 320, 240
BAND = 192                 # subtitle band: macroblock rows 12-14
SUB_SIZE = 12              # px
SUB_LINE = 14
SUB_COLOR = (232, 232, 232)
SUB_WIDTH = 304
SS = 4                     # supersampling for label text


def frame_path(name, n):
    return os.path.join(SRC, name, '%04d.png' % n)


_cache = {}


def frame(name, n):
    k = (name, n)
    if k not in _cache:
        if len(_cache) > 64:
            _cache.clear()
        _cache[k] = np.asarray(Image.open(frame_path(name, n)).convert('RGB'), dtype=np.float32)
    return _cache[k]


def font(size):
    return ImageFont.truetype(FONT, max(4, int(round(size))), index=0)


# ------------------------------------------------------------------ subtitles

def wrap(text, f, width):
    d = ImageDraw.Draw(Image.new('L', (1, 1)))
    lines, cur = [], ''
    for w in text.split():
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=f) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def balance(text, f, width):
    """two lines of similar length when the text needs two"""
    lines = wrap(text, f, width)
    if len(lines) != 2:
        return lines
    d = ImageDraw.Draw(Image.new('L', (1, 1)))
    words = text.split()
    best = None
    for i in range(1, len(words)):
        a, b = ' '.join(words[:i]), ' '.join(words[i:])
        wa, wb = d.textlength(a, font=f), d.textlength(b, font=f)
        if wa <= width and wb <= width:
            score = max(wa, wb)
            if best is None or score < best[0]:
                best = (score, [a, b])
    return best[1] if best else lines


SUB_STYLE = 'box'          # band: black band y 192-239; outline: text with a dark outline and
                           # shadow over the picture; box: translucent box around the text only
SUB_BOTTOM = 7             # outline / box: px between the last line and the bottom edge


def draw_subtitle(img, text, style=None):
    style = style or SUB_STYLE
    f = font(SUB_SIZE)
    lines = balance(text, f, SUB_WIDTH)
    if len(lines) > 2:
        raise ValueError('subtitle needs %d lines: %s' % (len(lines), text))
    mask = Image.new('L', (W, H), 0)
    dm = ImageDraw.Draw(mask)
    if style == 'band':
        top = BAND + (H - BAND - SUB_LINE * len(lines)) // 2 - 1
    else:
        top = H - SUB_BOTTOM - SUB_LINE * len(lines) - 1
    widths = []
    for i, s in enumerate(lines):
        w = dm.textlength(s, font=f)
        widths.append(w)
        dm.text(((W - w) / 2, top + i * SUB_LINE), s, font=f, fill=255)
    if style == 'band':
        ImageDraw.Draw(img).rectangle((0, BAND, W - 1, H - 1), fill=(0, 0, 0))
    elif style == 'box':
        bw = int(max(widths)) + 12
        box = Image.new('L', (W, H), 0)
        ImageDraw.Draw(box).rounded_rectangle(((W - bw) // 2, top - 1, (W + bw) // 2,
                                               top + SUB_LINE * len(lines) + 3), 4, fill=150)
        img.paste(Image.new('RGB', (W, H), (0, 0, 0)), (0, 0), box)
    if style in ('outline', 'box'):
        edge = mask.filter(ImageFilter.MaxFilter(3))                   # 1 px outline
        shadow = Image.new('L', (W, H), 0)
        shadow.paste(edge, (1, 1))
        shadow = shadow.filter(ImageFilter.GaussianBlur(1.0))
        dark = Image.fromarray(np.maximum(np.asarray(edge), np.asarray(shadow) * 0.8).astype(np.uint8))
        img.paste(Image.new('RGB', (W, H), (0, 0, 0)), (0, 0), dark)
    mask = mask.filter(ImageFilter.GaussianBlur(0.5))
    img.paste(Image.new('RGB', (W, H), SUB_COLOR), (0, 0), mask)
    return lines


# ------------------------------------------------------------------ labels

def box_blur(a, r):
    """mean filter (2r+1)^2 over the last two axes of a 2-D array, edges clamped"""
    p = np.pad(a, r, mode='edge')
    c = p.cumsum(0).cumsum(1)
    c = np.pad(c, ((1, 0), (1, 0)))
    k = 2 * r + 1
    s = c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]
    return s / (k * k)


def warp(img, s, tx, ty):
    """img sampled at s*(p - c) + c + t (bilinear), c = frame centre"""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    sx = s * (xx - W / 2) + W / 2 + tx
    sy = s * (yy - H / 2) + H / 2 + ty
    x0 = np.clip(np.floor(sx).astype(int), 0, W - 2)
    y0 = np.clip(np.floor(sy).astype(int), 0, H - 2)
    fx = np.clip(sx - x0, 0, 1)[..., None]
    fy = np.clip(sy - y0, 0, 1)[..., None]
    a = img[y0, x0] * (1 - fx) + img[y0, x0 + 1] * fx
    b = img[y0 + 1, x0] * (1 - fx) + img[y0 + 1, x0 + 1] * fx
    return a * (1 - fy) + b * fy


def find_motion(cur, ref, ignore, init=(1.0, 0.0, 0.0), steps=None):
    """(s, tx, ty) with cur ~ warp(ref, s, tx, ty), searched coarse to fine on luma"""
    lc, lr = cur.mean(2), ref.mean(2)
    keep = ~ignore
    best = tuple(init)

    def err(p):
        w = warp(lr[..., None], *p)[..., 0]
        return float(np.mean(np.minimum(np.abs(w - lc), 40)[keep]))
    e0 = err(best)
    for step_s, step_t, n in steps or ((0.02, 4.0, 3), (0.005, 1.0, 3), (0.001, 0.25, 3)):
        improved = True
        while improved:
            improved = False
            s0, x0, y0 = best
            for ds in range(-n, n + 1):
                for dx in range(-n, n + 1):
                    for dy in range(-n, n + 1):
                        p = (s0 + ds * step_s, x0 + dx * step_t, y0 + dy * step_t)
                        if p == best:
                            continue
                        e = err(p)
                        if e < e0:
                            e0, best, improved = e, p, True
    return best, e0


def static_ref(name, lab, n):
    """a frame without labels from the same still shot, same phase of the 4-frame water cycle"""
    lo, hi = lab['ref']
    cands = [r for r in range(lo, hi + 1) if (r - n) % 4 == 0] or [lo]
    return frame(name, cands[0])


def label_box(lab, n):
    for until, box in lab.get('early_boxes', []):               # fly-in: wider search box
        if n < until:
            return box
    return lab['box']


def crop_of(box, m=10):
    x0, y0, x1, y1 = box
    return max(0, x0 - m), max(0, y0 - m), min(W, x1 + m), min(H, y1 + m)


def remove_label(cur, ref, box, excl, neutral=False):
    """-> {'at': (X0, Y0), 'mask', 'clean' (crops), 'p': measured params or None}"""
    x0, y0, x1, y1 = box
    X0, Y0, X1, Y1 = crop_of(box)
    c = cur[Y0:Y1, X0:X1]
    r = ref[Y0:Y1, X0:X1]
    lc, lr = c.mean(2), np.maximum(r.mean(2), 1)
    g0 = np.median(lc) / np.median(lr)
    calm = np.abs(lc - g0 * lr) < 18
    for _ in range(2):                                   # smooth gain from the calm pixels
        wsum = box_blur(calm.astype(np.float32), 6)
        gain = box_blur(np.where(calm, lc, 0), 6) / np.maximum(box_blur(np.where(calm, lr, 0), 6), 1)
        gain = np.where(wsum > 0.15, gain, g0)
        calm = np.abs(lc - gain * lr) < 18
    clean = r * gain[..., None]
    D = c - clean
    inbox = np.zeros(lc.shape, bool)
    inbox[y0 - Y0:y1 - Y0, x0 - X0:x1 - X0] = True
    for ex0, ey0, ex1, ey1 in excl:
        inbox[max(0, ey0 - Y0):max(0, ey1 - Y0), max(0, ex0 - X0):max(0, ex1 - X0)] = False
    mask = (np.abs(D).max(2) > 22) & inbox
    if neutral:      # warped plate: keep only white / dark changes (the text), not misregistration
        Dm = D.mean(2)
        chroma = np.abs(D - Dm[..., None]).max(2)
        mask &= (np.abs(Dm) > 18) & (chroma < 0.4 * np.abs(Dm) + 8)
        mask = dilate(mask)
    if not neutral:                                      # soft shadow halo: grow into weak changes
        weak = (np.abs(D).max(2) > 8) & inbox
        for _ in range(3):
            mask |= dilate(mask) & weak
    mask = dilate(mask) & inbox                          # shadow edges
    core = (D.mean(2) > 45) & inbox
    p = None
    if core.sum() >= 6:
        ys, xs = np.nonzero(core)
        a = D.mean(2)[core] / np.maximum(255 - clean.mean(2)[core], 20)
        p = {'cx': (xs.min() + xs.max() + 1) / 2 + X0, 'cy': (ys.min() + ys.max() + 1) / 2 + Y0,
             'h': ys.max() - ys.min() + 1, 'w': xs.max() - xs.min() + 1,
             'alpha': float(np.clip(np.percentile(a, 80), 0, 1))}
    return {'at': (X0, Y0), 'mask': mask, 'clean': clean, 'p': p}


def dilate(m):
    d = m.copy()
    d[1:] |= m[:-1]
    d[:-1] |= m[1:]
    d[:, 1:] |= m[:, :-1]
    d[:, :-1] |= m[:, 1:]
    return d


def apply(img, r):
    X0, Y0 = r['at']
    h, w = r['mask'].shape
    sub = img[Y0:Y0 + h, X0:X0 + w]
    sub[r['mask']] = r['clean'][r['mask']]


def unblend(cur, s_cur, s_res, a=None, off=(0, 0)):
    """remove a fading label whose matte is taken from a still frame (s_cur, s_res):
    cur = bg (1 - a m) + L a m, L = white for the text, black for the shadow; a is the
    opacity that leaves the smoothest result"""
    X0, Y0 = s_res['at']
    h, w = s_res['mask'].shape
    cl = s_res['clean']
    D = s_cur[Y0:Y0 + h, X0:X0 + w] - cl
    pos = D > 0
    L = np.where(pos, 255.0, 0.0)
    m = np.where(pos, D / np.maximum(255 - cl, 8), -D / np.maximum(cl, 8))
    m = np.clip(m, 0, 0.98) * s_res['mask'][..., None]
    X0, Y0 = X0 + off[0], Y0 + off[1]
    c = cur[Y0:Y0 + h, X0:X0 + w]
    region = dilate(dilate(s_res['mask']))
    if a is None:
        best = None
        for a in np.arange(0, 1.0001, 0.02):
            bg = (c - L * a * m) / (1 - a * m)
            e = np.abs(bg - box_blur(bg.mean(2), 1)[..., None]).mean(2)[region].sum()
            if best is None or e < best[0]:
                best = (e, a)
        a = best[1]
    bg = (c - L * a * m) / (1 - a * m)
    return {'at': (X0, Y0), 'mask': s_res['mask'], 'clean': np.clip(bg, 0, 255), 'p': None, 'a': float(a)}


def fade_estimator(s_cur, s_res):
    """opacity of the label in a frame, relative to the still frame: least-squares fit of the
    label's fine detail (matte times contrast against the blurred frame) to the frame's"""
    X0, Y0 = s_res['at']
    h, w = s_res['mask'].shape
    cl = s_res['clean']
    D = s_cur[Y0:Y0 + h, X0:X0 + w] - cl
    pos = D > 0
    L = np.where(pos, 255.0, 0.0)
    m = np.clip(np.where(pos, D / np.maximum(255 - cl, 8), -D / np.maximum(cl, 8)), 0, 0.98) * s_res['mask'][..., None]

    def hp(x):
        return x - np.stack([box_blur(x[..., i], 2) for i in range(3)], -1)

    def est(cur, off=(0, 0), corr=False):
        x, y = X0 + off[0], Y0 + off[1]
        if x < 0 or y < 0 or x + w > W or y + h > H:
            return -1.0
        c = cur[y:y + h, x:x + w]
        g = m * (L - np.stack([box_blur(c[..., i], 3) for i in range(3)], -1))
        hg, hc = hp(g), hp(c)
        if corr:
            return float((hc * hg).sum() / max(np.sqrt((hg ** 2).sum() * (hc ** 2).sum()), 1e-6))
        return float((hc * hg).sum() / max((hg ** 2).sum(), 1e-6))
    return est


def process_label(name, lab):
    """-> {frame: removal result} for one label over its frames"""
    a, b = lab['frames']
    excl = lab.get('exclude', [])
    chains = lab.get('chain', [])                         # [from, to, 'back' | 'fwd']
    fades = lab.get('fade', [])                           # [from, to, still frame]
    special = {n for c in chains for n in range(c[0], c[1] + 1)} |               {n for f in fades for n in range(f[0], f[1] + 1)}
    res = {}
    for n in range(a, b + 1):
        if n not in special:
            res[n] = remove_label(frame(name, n), static_ref(name, lab, n), label_box(lab, n), excl)

    def clean_full(n):
        img = frame(name, n).copy()
        if n in res:
            apply(img, res[n])
        return img
    ign = np.zeros((H, W), bool)                          # overlays move with the labels, not the map
    for bx in [lab['box']] + [e[1] for e in lab.get('early_boxes', [])] + lab.get('motion_ignore', []):
        X0, Y0, X1, Y1 = crop_of(bx, 6)
        ign[Y0:Y1, X0:X1] = True
    for c0, c1, d in chains:
        # frame-to-frame motion composed back to the anchor (the nearest still frame), so the
        # anchor's clean plate is resampled once (no blur build-up)
        seq = range(c1, c0 - 1, -1) if d == 'back' else range(c0, c1 + 1)
        anchor = c1 + 1 if d == 'back' else c0 - 1
        plate = clean_full(anchor)
        S, TX, TY = 1.0, 0.0, 0.0
        for n in seq:
            nb = n + 1 if d == 'back' else n - 1
            (s, tx, ty), e = find_motion(frame(name, n), frame(name, nb), ign)
            S, TX, TY = S * s, S * tx + TX, S * ty + TY
            # refine on a ring around the label (the map may not move as one plane)
            ring = np.ones((H, W), bool)
            X0, Y0, X1, Y1 = crop_of(label_box(lab, n), 24)
            ring[Y0:Y1, X0:X1] = False
            X0, Y0, X1, Y1 = crop_of(label_box(lab, n), 2)
            ring[Y0:Y1, X0:X1] = True
            (S, TX, TY), e = find_motion(frame(name, n), plate, ring, (S, TX, TY),
                                         ((0.002, 0.5, 2), (0.0005, 0.125, 2)))
            ref = warp(plate, S, TX, TY)
            res[n] = remove_label(frame(name, n), ref, label_box(lab, n), excl, neutral=True)
    for f0, f1, s in fades:
        est = fade_estimator(frame(name, s), res[s])
        a1 = est(frame(name, s))
        for n in range(f0, f1 + 1):
            off = (0, 0)
            if lab.get('fade_search'):                  # the label slides while it fades
                dx, dy = lab['fade_search']
                cands = [(ox, oy) for ox in range(-dx, dx + 1) for oy in range(-dy, dy + 1)]
                off = max(cands, key=lambda o: est(frame(name, n), o, corr=True))
            a = float(np.clip(est(frame(name, n), off) / a1, 0, 1))
            res[n] = unblend(frame(name, n), frame(name, s), res[s], a, off)
            res[n]['off'] = off
    return res


def text_layer(lines, size):
    """RGBA image of the label text (white, dark outline + shadow), its anchor = centre"""
    f = font(size * SS)
    d = ImageDraw.Draw(Image.new('L', (1, 1)))
    lh = int(size * SS * 1.15)
    ws = [d.textlength(s, font=f) for s in lines]
    pad = 4 * SS
    w = int(max(ws)) + 2 * pad
    h = lh * len(lines) + 2 * pad
    fill = Image.new('L', (w, h), 0)
    df = ImageDraw.Draw(fill)
    for i, s in enumerate(lines):
        df.text(((w - ws[i]) / 2, pad + i * lh - SS), s, font=f, fill=255)
    ow = max(1, int(round(SS * (1.2 if size < 16 else 1.6))))
    outline = fill.filter(ImageFilter.MaxFilter(2 * ow + 1)).filter(ImageFilter.GaussianBlur(SS * 0.6))
    shadow = Image.new('L', (w, h), 0)
    shadow.paste(outline, (SS, SS))
    dark = Image.fromarray(np.maximum(np.asarray(outline), np.asarray(shadow)))
    rgba = Image.new('RGBA', (w, h), (12, 14, 30, 0))
    rgba.putalpha(dark.point(lambda v: int(v * 0.85)))
    white = Image.new('RGBA', (w, h), (246, 246, 240, 0))
    white.putalpha(fill)
    rgba = Image.alpha_composite(rgba, white)
    return rgba


def place_text(img, layer, cx, cy, scale, alpha):
    w, h = layer.size
    nw, nh = max(1, int(round(w * scale / SS))), max(1, int(round(h * scale / SS)))
    t = layer.resize((nw, nh), Image.LANCZOS)
    if alpha < 1:
        a = np.asarray(t.getchannel('A'), dtype=np.float32) * alpha
        t.putalpha(Image.fromarray(a.astype(np.uint8)))
    base = img.convert('RGBA')
    x, y = int(round(cx - nw / 2)), int(round(cy - nh / 2))
    tmp = Image.new('RGBA', base.size, (0, 0, 0, 0))
    tmp.paste(t, (x, y))
    return Image.alpha_composite(base, tmp).convert('RGB'), (x, y, x + nw, y + nh)


def smooth(params, keys=('cx', 'cy', 'h', 'alpha')):
    """median of 3 over measured frames; fade frames ({'fade': a}) pass through"""
    ns = sorted(params)
    out = {}
    for i, n in enumerate(ns):
        p = params[n]
        if p is None or 'fade' in p:
            out[n] = p
            continue
        win = [params[m] for m in ns[max(0, i - 1):i + 2] if params[m] and 'fade' not in params[m]]
        out[n] = {k: float(np.median([q[k] for q in win])) for k in keys}
    return out


# ------------------------------------------------------------------ main

def build(name, only=None, sheet=None):
    spec = json.load(open(os.path.join(TR, name + '.json'), encoding='utf-8'))
    total = len([f for f in os.listdir(os.path.join(SRC, name)) if f.endswith('.png')])
    subs = {}
    for s in spec['subtitles']:
        a, b = int(round(s['start'] * FPS)) + 1, int(round(s['end'] * FPS)) + 1
        for n in range(a, min(b, total) + 1):
            subs[n] = s['en']
    labels = spec.get('labels', [])
    # pass 1: remove the Japanese, measure each label per frame
    params, results = {}, {}
    for lab in labels:
        if only and not any(n in only for n in range(lab['frames'][0], lab['frames'][1] + 1)):
            continue
        res = process_label(name, lab)
        results[lab['id']] = res
        params[lab['id']] = {n: (r['p'] if r['p'] else ({'fade': r['a'], 'off': r.get('off', (0, 0))}
                                                         if 'a' in r else None))
                             for n, r in res.items()}
    edited = {}
    for n in sorted({n for res in results.values() for n in res}):
        if only and n not in only:
            continue
        img = frame(name, n).copy()
        for res in results.values():
            if n in res:
                apply(img, res[n])
        edited[n] = np.clip(img, 0, 255).astype(np.uint8)       # 32-bit Python: keep it small
    # pass 2: English labels
    final = {}
    for lab in labels:
        if lab['id'] not in params:
            continue
        ps = smooth(params[lab['id']])
        st = lab.get('settled')
        sp = ps.get(st) if st else None
        ref_h = sp['h'] if sp and 'h' in sp else None
        layer = text_layer(lab['en'], lab['size'])
        hold = lab.get('hold')
        # a label that shares frames with subtitles sits above the band all the time
        lift = 0
        if sp and any(n in subs for n in ps):
            nh = layer.size[1] / SS
            lift = max(0, sp['cy'] + nh / 2 - (BAND - 2))
        for n, p in ps.items():
            if p is None or n not in edited:
                continue
            if 'fade' in p:
                if not sp:
                    continue
                q = dict(sp, alpha=sp['alpha'] * p['fade'])
                q['cx'] += p['off'][0]
                q['cy'] += p['off'][1]
            else:
                q = dict(p)
                if hold and hold[0] <= n <= hold[1] and sp:
                    q = dict(sp, alpha=p['alpha'])
            if q['alpha'] < 0.04:
                continue
            scale = 1.0 if (lab.get('fixed_scale') or not ref_h) else float(np.clip(q['h'] / ref_h, 0.4, 4))
            base = Image.fromarray(final.get(n, edited[n]))
            cy = q['cy'] + lab.get('dy', 0) - lift
            alpha = min(1.0, q['alpha'] * 1.05)
            img, bb = place_text(base, layer, q['cx'], cy, scale, alpha)
            if n in subs and bb[3] > BAND - 1:                         # keep clear of the band
                img, bb = place_text(base, layer, q['cx'], cy - (bb[3] - BAND + 2), scale, alpha)
            final[n] = np.asarray(img)
    for n in edited:
        final.setdefault(n, edited[n])
    # pass 3: subtitles, write
    od = os.path.join(OUT, name)
    os.makedirs(od, exist_ok=True)
    todo = sorted(set(final) | set(subs))
    if only:
        todo = [n for n in todo if n in only]
    xml = ['<?xml version="1.0"?>', '<str-replace version="0.3">']
    for n in todo:
        img = Image.fromarray(final[n] if n in final else frame(name, n).astype(np.uint8))
        if n in subs:
            draw_subtitle(img, subs[n])
        img.save(os.path.join(od, '%04d.png' % n))
        diff = np.abs(np.asarray(img, dtype=np.float32) - frame(name, n)).max(2) > 0
        if not diff.any():
            continue
        # whole-frame replace: these STRv2 frames have one quantization scale, in the frame
        # header, for every block; jPSXdec's partial-replace encoded the changed blocks at a
        # new scale but kept the header's, so they decoded too dark (by old / new: the
        # subtitles came out grey and soft at q4-7, as on the console)
        xml.append(' <replace frame="%d">%04d.png</replace>' % (n - 1, n))
    xml.append('</str-replace>')
    open(os.path.join(od, 'replace.xml'), 'w').write('\n'.join(xml) + '\n')
    print('%s: %d frames edited (%d with subtitles), replace.xml written' % (name, len(todo), len(set(subs) & set(todo))))
    if sheet:
        make_sheet(name, sheet, todo)


def make_sheet(name, path, frames, step=None):
    frames = frames[::step or max(1, len(frames) // 48)]
    cols = 6
    rows = (len(frames) + cols - 1) // cols
    sh = Image.new('RGB', (cols * W, rows * H))
    for k, n in enumerate(frames):
        im = Image.open(os.path.join(OUT, name, '%04d.png' % n))
        ImageDraw.Draw(im).text((2, 2), str(n), fill=(255, 255, 0))
        sh.paste(im, ((k % cols) * W, (k // cols) * H))
    sh.save(path)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('name')
    ap.add_argument('--frames')
    ap.add_argument('--sheet')
    ap.add_argument('--style', choices=('band', 'outline', 'box'), help='subtitle style (default SUB_STYLE)')
    a = ap.parse_args()
    if a.style:
        SUB_STYLE = a.style
    only = None
    if a.frames:
        lo, hi = map(int, a.frames.split('-'))
        only = set(range(lo, hi + 1))
    build(a.name, only, a.sheet)
