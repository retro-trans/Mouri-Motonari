"""GitHub social preview (1280x640), same layout as the other retro-trans repositories
(Elminage II / III, Getter Robo Daikessen): navy background, framed box art on the left, platform / title / gold
rule / "English translation patch" / "retro-trans" on the right.

    python tools/social_preview.py [COVER]   # default incoming/boxart/mouri_motonari_jp_front.png
Output: work/release/social-preview.png (upload in the repository's Settings -> Social preview).
The cover (libretro-thumbnails Sony_-_PlayStation, "Mouri Motonari - Chikai no Sanshi (Japan).png") is not
in the repository (incoming/ is ignored). PS1 covers are square, so the frame is square.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
COVER = os.path.join(ROOT, 'incoming', 'boxart', 'mouri_motonari_jp_front.png')
OUT = os.path.join(ROOT, 'work', 'release', 'social-preview.png')
FONTS = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
W, H = 1280, 640
CREAM = (246, 239, 222)
BLUE = (132, 170, 232)
GOLD = (232, 188, 74)
FRAME = (214, 206, 186)


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def background():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((x - 760) / 900) ** 2 + ((y - 300) / 520) ** 2)
    t = np.clip(d, 0, 1)[..., None] ** 1.3
    inner, outer = np.array((20, 46, 116), np.float32), np.array((6, 15, 45), np.float32)
    return Image.fromarray((inner * (1 - t) + outer * t).astype(np.uint8), 'RGB')


def fit(name, s, width):
    """Font size whose ink width of s is closest to width."""
    best = None
    for size in range(10, 200):
        b = font(name, size).getbbox(s)
        if best is None or abs((b[2] - b[0]) - width) < abs(best[1] - width):
            best = (size, b[2] - b[0])
    return font(name, best[0])


def text_at(draw, x, cap_top, s, f, fill, spacing=0):
    """Draw s with the top of its capitals at cap_top (letter spacing in px)."""
    top = f.getbbox('H')[1]
    if not spacing:
        draw.text((x, cap_top - top), s, font=f, fill=fill)
        return x + draw.textlength(s, font=f)
    for ch in s:
        draw.text((x, cap_top - top), ch, font=f, fill=fill)
        x += draw.textlength(ch, font=f) + spacing
    return x - spacing


def main():
    cover_path = sys.argv[1] if len(sys.argv) > 1 else COVER
    img = background()
    # square cover with a soft shadow and a cream frame
    side = 470
    fx0, fy0 = 64, (H - side) // 2
    fx1, fy1 = fx0 + side, fy0 + side
    sh = Image.new('L', (W, H), 0)
    ImageDraw.Draw(sh).rectangle((fx0 + 6, fy0 + 10, fx1 + 6, fy1 + 10), fill=150)
    sh = sh.filter(ImageFilter.GaussianBlur(12))
    img = Image.composite(Image.new('RGB', (W, H), (0, 0, 0)), img, sh)
    d = ImageDraw.Draw(img)
    d.rectangle((fx0, fy0, fx1 - 1, fy1 - 1), fill=FRAME)
    d.rectangle((fx0 + 3, fy0 + 3, fx1 - 4, fy1 - 4), fill=(30, 30, 36))
    cw = side - 8
    cover = Image.open(cover_path).convert('RGB').resize((cw, cw), Image.LANCZOS)
    img.paste(cover, (fx0 + 4, fy0 + 4))

    d = ImageDraw.Draw(img)
    left, right = 596, 1216
    text_at(d, left, 123, 'PLAYSTATION', font('segoeuib.ttf', 25), BLUE, spacing=7)
    big = fit('segoeuib.ttf', 'CHIKAI NO SANSHI', right - left)
    text_at(d, left - 2, 186, 'MOURI MOTONARI', big, CREAM)
    text_at(d, left - 2, 186 + int(big.size * 0.86), 'CHIKAI NO SANSHI', big, CREAM)
    rule = 186 + int(big.size * 0.86) * 2 + 4
    d.rounded_rectangle((left, rule, left + 298, rule + 6), radius=3, fill=GOLD)
    text_at(d, left, rule + 37, 'English translation patch',
            fit('segoeuib.ttf', 'English translation patch', 489), CREAM)
    f = font('segoeuib.ttf', 26)
    s, sp = 'retro-trans', 3
    width = sum(d.textlength(c, font=f) for c in s) + sp * (len(s) - 1)
    text_at(d, 1222 - width, 580, s, f, BLUE, spacing=sp)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT)
    print(OUT, 'title size', big.size)


if __name__ == '__main__':
    main()
