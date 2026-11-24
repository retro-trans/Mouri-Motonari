"""The project text font: Skies of Arcadia's (USA, Dreamcast) Latin font, as used by
the Seireiki Rayblade translation (../Seireiki Rayblade, tools/analyze_skies_font.py).

The glyph pixels are SEGA/Overworks artwork: they are decoded at build time from
the user's own Skies disc and cached in work/source/ (never committed, like the
Japanese script).  Each of the 96 glyphs (codes 32-127) is stored in 1ST_READ.BIN
as 6x12 bytes of 2x2 VQ indices; each byte holds four 2-bit coverage levels
(TL, BL, TR, BR) -> a 12x24 mask with levels 0, 85, 187, 255.

    python tools/skies_font.py            -> work/source/skies_font.png (96 x 12x24, one row)
    SKIES_CUE=<path to the Skies Disc 1 .cue> overrides the default disc path.
"""
import hashlib
import os
import re
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUE = os.environ.get('SKIES_CUE', r'E:\Games\Skies of Arcadia (USA) (Disc 1).cue')
CACHE = os.path.join(ROOT, 'work', 'source', 'skies_font.png')
EXE_SHA256 = '4218c07829d63080be2da86413ec023e6d77001c13a1494648db6e2e5cb73611'
GLYPHS_PTR = 0x1A210                 # pointer to the glyph table in 1ST_READ.BIN
LEVELS_OFF = 0x3EA0F0                # the four ARGB4444 coverage colours
W, H, COUNT = 12, 24, 96
SECTOR, PAYLOAD = 2352, 2048
SYNC = b'\x00' + b'\xff' * 10 + b'\x00'


def _bcd(v):
    return (v >> 4) * 10 + (v & 15)


class Disc:
    """Read-only Redump CUE (MODE1/2352 data tracks, high-density area at LBA 45000)."""

    def __init__(self, cue):
        self.tracks = []
        base = os.path.dirname(cue)
        filename = mode = None
        for line in open(cue, encoding='utf-8-sig').read().splitlines():
            m = re.match(r'\s*FILE "(.+)" BINARY', line)
            if m:
                filename = m.group(1)
            m = re.match(r'\s*TRACK (\d+) (\S+)', line)
            if m:
                mode = m.group(2)
            m = re.match(r'\s*INDEX 01 (\d+):(\d+):(\d+)', line)
            if m and mode == 'MODE1/2352':
                path = os.path.join(base, filename)
                index = (int(m.group(1)) * 60 + int(m.group(2))) * 75 + int(m.group(3))
                with open(path, 'rb') as f:
                    f.seek(index * SECTOR)
                    hdr = f.read(16)
                assert hdr[:12] == SYNC and hdr[15] == 1, path
                lba = (_bcd(hdr[12]) * 60 + _bcd(hdr[13])) * 75 + _bcd(hdr[14]) - 150
                count = os.path.getsize(path) // SECTOR - index
                self.tracks.append((lba, lba + count, path, index))

    def read(self, lba, size):
        out = bytearray()
        while len(out) < size:
            lo, hi, path, index = next(t for t in self.tracks if t[0] <= lba < t[1])
            n = min((size - len(out) + PAYLOAD - 1) // PAYLOAD, hi - lba)
            with open(path, 'rb') as f:
                f.seek((index + lba - lo) * SECTOR)
                raw = f.read(n * SECTOR)
            for k in range(n):
                out += raw[k * SECTOR + 16:k * SECTOR + 16 + PAYLOAD]
            lba += n
        return bytes(out[:size])

    def file(self, name):
        pvd = self.read(45016, PAYLOAD)
        assert pvd[1:6] == b'CD001'
        lba, size = struct.unpack_from('<I', pvd, 158)[0], struct.unpack_from('<I', pvd, 166)[0]
        data = self.read(lba, size)
        pos = 0
        while pos < len(data):
            n = data[pos]
            if not n:
                pos = (pos // PAYLOAD + 1) * PAYLOAD
                continue
            rec = data[pos:pos + n]
            pos += n
            if rec[33:33 + rec[32]].decode('ascii', 'replace').split(';')[0] == name:
                return self.read(struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0])
        raise FileNotFoundError(name)


def extract():
    from PIL import Image
    exe = Disc(CUE).file('1ST_READ.BIN')
    assert hashlib.sha256(exe).hexdigest() == EXE_SHA256, 'unexpected Skies 1ST_READ.BIN'
    table = struct.unpack_from('<I', exe, GLYPHS_PTR)[0] - 0x8C010000
    levels = [(c >> 12) * 17 for c in struct.unpack_from('<4H', exe, LEVELS_OFF)]
    sheet = Image.new('L', (W * COUNT, H))
    for i in range(COUNT):
        raw = exe[table + i * 72:table + i * 72 + 72]
        for y in range(12):
            for x in range(6):
                v = raw[y * 6 + x]
                for dx, dy, sh in ((0, 0, 6), (0, 1, 4), (1, 0, 2), (1, 1, 0)):
                    sheet.putpixel((i * W + x * 2 + dx, y * 2 + dy), levels[v >> sh & 3])
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    sheet.save(CACHE)
    return sheet


def sheet():
    """The 96-glyph coverage sheet (L image, 1152 x 24), extracted once from the disc."""
    from PIL import Image
    if not os.path.exists(CACHE):
        return extract()
    return Image.open(CACHE).convert('L')


def glyph(ch):
    """12x24 coverage mask of an ASCII character, or None."""
    c = ord(ch)
    if not 32 <= c < 32 + COUNT:
        return None
    return sheet().crop(((c - 32) * W, 0, (c - 31) * W, H))


if __name__ == '__main__':
    extract()
    print(CACHE)
