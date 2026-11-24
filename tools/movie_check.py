"""Check a re-encoded movie: decode the patched frames with jPSXdec and compare them with the
edited PNGs (tools/movie_edit.py output).

    python tools/movie_check.py MOVIE05

Prints, per film, how many edited frames decode with the subtitle band (y 192-239) and the
picture above it close to the edited image, and lists the worst frames. A partial-replace
with a different quantization scale than the frame header decoded too dark (band max ~150
instead of ~210); see docs/movies.md.
"""
import os
import re
import shutil
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import movie  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'output', 'movie')


def main(name):
    ed = os.path.join(OUT, name)
    frames = sorted(int(f[:4]) for f in os.listdir(ed) if f.endswith('.png') and f[:4].isdigit())
    work = os.path.join(OUT, 'check_' + name)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    shutil.copyfile(os.path.join(OUT, name + '.raw'), os.path.join(work, name + '.raw'))
    idx = movie.index(work, os.path.join(work, name + '.raw'))
    movie.jpsxdec(work, '-x', idx, '-i', '0', '-vf', 'png', '-num', 'Header', '-noaud',
                  '-frames', '%d-%d' % (frames[0], frames[-1]), '-dir', 'out')
    dec = {}                                       # jPSXdec pads the number to the film's digits
    for f in os.listdir(os.path.join(work, 'out')):
        m = re.search(r'#(\d+)\]\.png$', f)
        if m:
            dec[int(m.group(1))] = os.path.join(work, 'out', f)
    rows = []
    for n in frames:
        a = np.asarray(Image.open(dec[n]).convert('L'), np.float32)
        b = np.asarray(Image.open(os.path.join(ed, '%04d.png' % n)).convert('L'), np.float32)
        rows.append((n, float(np.abs(a[192:] - b[192:]).mean()), float(np.abs(a[:192] - b[:192]).mean())))
    bad = [r for r in rows if r[1] > 4]
    print('%s: %d edited frames, band error mean %.2f max %.2f, picture error mean %.2f max %.2f, '
          '%d frames with band error > 4' % (name, len(rows), np.mean([r[1] for r in rows]),
                                              max(r[1] for r in rows), np.mean([r[2] for r in rows]),
                                              max(r[2] for r in rows), len(bad)))
    for r in sorted(rows, key=lambda r: -r[1])[:5]:
        print('  frame %d band %.2f picture %.2f' % r)
    shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    for n in sys.argv[1:]:
        main(n)
