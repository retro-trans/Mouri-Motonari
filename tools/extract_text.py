"""Extract the event-script text (DATA/R_xx.EEX, DATA/S_xx.EEX) for translation.

    python tools/extract_text.py

Writes (Japanese, git-ignored):
  work/source/text/rows.json     every string occurrence: id, file, ev, blk, off, op, unit
  work/source/text/units.json    unique strings in story order: key, kind, op, first, count, jp
  work/source/text/slices/NNN.json   80 units per slice (translation input)

Order: R_00, S_00, R_01, S_01, ... (R = story events of chapter part NN, S = the
battle-map events of the same part; the in-game order alternates).
Text conventions in jp: '\\n' line break, '&Name' at a line start = speaker
header (name box), '　' full-width space.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eex import Script, SRC   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'source', 'text')
SLICE = 80
KIND = {0x27: 'dialogue', 0x29: 'title', 0x2A: 'title', 0x2B: 'title', 0x12: 'choice',
        0x2C: 'label', 0x28: 'label'}


def story_files():
    out = []
    for n in range(30):
        for p in ('R', 'S'):
            f = os.path.join(SRC, '%s_%02d.EEX' % (p, n))
            if os.path.exists(f):
                out.append(f)
    return out


def main():
    os.makedirs(os.path.join(OUT, 'slices'), exist_ok=True)
    rows, units, index = [], [], {}
    for f in story_files():
        name = os.path.basename(f)[:-4]
        s = Script(open(f, 'rb').read(), name)
        for ev, blk, a, t in s.all_strings():
            op = int.from_bytes(s.d[a - 4:a - 2], 'little')
            jp = t.decode('cp932')
            if jp not in index:
                index[jp] = len(units)
                units.append({'key': 'U%05d' % len(units), 'kind': KIND.get(op, 'op%02x' % op),
                              'op': op, 'first': '%s/%d/%d/%x' % (name, ev, blk, a),
                              'count': 0, 'jp': jp})
            u = units[index[jp]]
            u['count'] += 1
            rows.append({'id': 'R%05d' % len(rows), 'file': name, 'ev': ev, 'blk': blk,
                         'off': a, 'op': op, 'unit': u['key']})
    json.dump(rows, open(os.path.join(OUT, 'rows.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    json.dump(units, open(os.path.join(OUT, 'units.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for i in range(0, len(units), SLICE):
        json.dump(units[i:i + SLICE], open(os.path.join(OUT, 'slices', '%03d.json' % (i // SLICE)), 'w',
                                           encoding='utf-8'), ensure_ascii=False, indent=1)
    print('rows', len(rows), 'units', len(units), 'slices', (len(units) + SLICE - 1) // SLICE)


if __name__ == '__main__':
    main()
