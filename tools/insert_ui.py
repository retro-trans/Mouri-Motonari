"""Insert the English menu / item / skill / profile text (see docs/text_formats.md).

    python tools/insert_ui.py check [work/translation/en/ui/NNN.json ...]   lint translations
    python tools/insert_ui.py stats                                        coverage per source
    python tools/insert_ui.py preview KEY ...                              lines as laid out
                                                                           (profiles: as the game builds them)

Input: work/translation/en/ui/*.json (lists of {key, en, note}) for the units of
work/source/text/ui_units.json (tools/extract_ui.py). Untranslated units keep their
Japanese bytes; with no translation at all every file is left exactly as it was.

tools/build.py calls build(): it returns the new DATA files, the MAIN.EXE string edits
and the engine options for tools/vwf.py (raised description cap, profile sector reader,
profile format markers, pool of relocated strings in kernel RAM, town-label centring).
"""
import glob
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vwf                            # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT = os.path.join(ROOT, 'work', 'source', 'text')
TR = os.path.join(ROOT, 'work', 'translation', 'en', 'ui')
DISC = os.path.join(ROOT, 'work', 'source', 'disc')
EXE_BASE = 0x80010000

SPEC = re.compile(r'%(?:[-+ #0]*\d*(?:\.\d+)?l?[a-zA-Z%])?')
PROF_SLOT = 2048                    # one CD sector per profile variant (vwf.py prof_load)
PROF_LINE = vwf.PROF_LINE          # bytes per profile line (loader patched from 24)
PROF_LINES = 50                     # lines in the 2512-byte loader buffer (vwf.py PROFV_ASM)
PROF_FMT_NAME = 12                  # '%-12s': officer names are at most 12 bytes (names.py)

_ADV = None


def adv():
    global _ADV
    if _ADV is None:
        _ADV = vwf.advances()
    return _ADV


def est(spec):
    """(bytes, px) a format specifier expands to at most."""
    if spec == '%':                                  # training quotes: runtime word
        return 16, 96
    if spec == '%%':
        return 1, 6
    m = re.match(r'%[-+ #0]*(\d*)', spec)
    w = int(m.group(1)) if m and m.group(1) else 0
    c = spec[-1].lower()
    if c == 's':
        return max(w, 12), max(w, 12) * 6
    if c in 'duwxi':
        n = max(w, 5)
        return n, n * 6
    return max(w, 1), max(w, 1) * 6


def tokens(s):
    """-> list of (text, is_spec)."""
    out, i = [], 0
    for m in SPEC.finditer(s):
        if m.start() > i:
            out.append((s[i:m.start()], False))
        out.append((m.group(0), True))
        i = m.end()
    if i < len(s):
        out.append((s[i:], False))
    return out


def measure(s, specs_as='est'):
    """-> (px, bytes) of one line; specs_as: 'est' expanded estimate, 'drop' ignored, 'raw' as text."""
    px = nb = 0
    a = adv()
    for t, sp in tokens(s):
        if sp and specs_as == 'est':
            b, p = est(t)
            px += p
            nb += b
        elif sp and specs_as == 'drop':
            continue
        else:
            px += sum(a.get(ord(c), 12) for c in t)
            nb += len(t)
    return px, nb


def wrap(par, line_px=None, line_bytes=None, first_bytes=None, first_px=None):
    """Greedy word wrap of one paragraph (specifiers counted at their expanded size)."""
    out, line = [], ''
    for word in par.split(' '):
        cand = word if not line else line + ' ' + word
        px, nb = measure(cand)
        lb = first_bytes if (first_bytes and not out) else line_bytes
        lp = first_px if (first_px and not out) else line_px
        if not line or ((lp is None or px <= lp) and (lb is None or nb <= lb)):
            line = cand
        else:
            out.append(line)
            line = word
    out.append(line)
    return out


def layout(u, en):
    """English unit text -> (list of game lines, problems)."""
    probs = []
    w = u.get('wrap')
    if w in ('auto', 'profile'):
        lines = []
        for par in en.split('\n'):
            lines += wrap(par.strip(), u.get('line_px'), u.get('line_bytes'))
    elif w == 'profile_fmt':
        lines = []
        for par in en.split('\n'):
            first = not lines                 # line 1 sits between two 16 px SJIS blanks
            lines += wrap(par.strip(), u.get('line_px'), u.get('line_bytes'),
                          first_bytes=u['line_bytes'] - 4 if first else None,
                          first_px=u['line_px'] - 32 if first else None)
    elif w == 'none':
        lines = [en]
        if '\n' in en:
            probs.append('line breaks are not allowed here')
    else:
        lines = en.split('\n')
    return lines, probs


def check_unit(u, en):
    """-> (lines, problems)"""
    probs = []
    if not en:
        return [], ['empty translation']
    bad = sorted({c for c in en if not (0x20 <= ord(c) < 0x7F or c == '\n')})
    if bad:
        probs.append('non-ASCII / control characters: %s' % ''.join(bad).encode('unicode_escape').decode())
    js, es = SPEC.findall(u['jp']), SPEC.findall(en)
    if js != es:
        probs.append('format specifiers %s != Japanese %s' % (es, js))
    if '\\' in en:
        probs.append('backslash not allowed')
    if u['src'] == 'PROFILE':
        for bad_seq in ('$', '//', '\t'):
            if bad_seq in en:
                probs.append('%r not allowed in a profile (parser control)' % bad_seq)
    lines, p = layout(u, en)
    probs += p
    if u.get('max_lines') and len(lines) > u['max_lines']:
        probs.append('%d lines > %d' % (len(lines), u['max_lines']))
    for l in lines:
        if u.get('px_from') == 'jp':
            px, nb = measure(l, 'drop')
        else:
            px, nb = measure(l)
        if u.get('line_px') and px > u['line_px']:
            probs.append('line too wide (%d px > %d): %s' % (px, u['line_px'], l))
        if u.get('line_bytes') and measure(l)[1] > u['line_bytes']:
            probs.append('line too long (%d bytes > %d): %s' % (measure(l)[1], u['line_bytes'], l))
    data = encode(u, lines)
    if u['src'] == 'PROFILE':
        if u['wrap'] == 'profile_fmt':
            n = len(lines) * PROF_LINE
            if n > 900:
                probs.append('profile text %d bytes > 900 (sprintf buffer)' % n)
            if measure(lines[0])[0] > u['line_px'] - 32:
                probs.append('first line too wide (%d px > %d)' % (measure(lines[0])[0], u['line_px'] - 32))
        if len(lines) > PROF_LINES:
            probs.append('profile %d lines > %d' % (len(lines), PROF_LINES))
        if len(data) + 8 > PROF_SLOT:
            probs.append('profile %d bytes > one sector' % len(data))
    elif len(data) > u['max_bytes']:
        probs.append('%d bytes > %d%s' % (len(data), u['max_bytes'],
                                           '' if u.get('relocatable') or u['src'] != 'EXE'
                                           else ' (string stays in place: shorten it)'))
    return lines, probs


def encode(u, lines):
    """Game bytes of a laid-out unit (no terminator)."""
    if u['src'] == 'PROFILE':
        if u['wrap'] == 'profile_fmt':
            return profile_fmt_bytes(lines)
        return b''.join(l.encode('ascii', 'replace') + b'\r\n' for l in lines)
    sep = u.get('sep', '\n')
    return sep.join(lines).encode('ascii', 'replace')


def profile_fmt_bytes(lines):
    """Format profile (characters 48/49, mode 0x30/0x31 of 0x80080E9C): the text goes
    through sprintf and is then re-padded only at SJIS 0x8140 markers (0x8142 '。' in the
    original, patched by tools/vwf.py). Layout: marker, line 1 padded, marker = 48 bytes (the
    game pads that segment to a multiple of 24), then lines pre-padded to exactly 48 bytes; '%s' -> '%-12s' so names expand to
    exactly 12 bytes."""
    out = b'\x81\x40'
    for i, l in enumerate(lines):
        b = l.replace('%s', '%%-%ds' % PROF_FMT_NAME).encode('ascii', 'replace')
        n = measure(l)[1]
        if i == 0:
            out += b + b' ' * (PROF_LINE - 4 - n) + b'\x81\x40'
        else:
            out += b + b' ' * (PROF_LINE - n) if i < len(lines) - 1 else b
    return out


# ------------------------------------------------------------------------- data


def load_units():
    units = json.load(open(os.path.join(TEXT, 'ui_units.json'), encoding='utf-8'))
    for u in units:
        if u['src'] == 'PROFILE':        # 48-byte lines (vwf.py profile patch)
            u.update(line_bytes=PROF_LINE, max_lines=PROF_LINES, max_bytes=PROF_LINE * PROF_LINES)
    return units


def load_rows():
    return json.load(open(os.path.join(TEXT, 'ui_rows.json'), encoding='utf-8'))


def tr_files():
    """working files; a clone of the repository has only the Japanese-free .en.json copies"""
    work = [f for f in glob.glob(os.path.join(TR, '*.json')) if not f.endswith('.en.json')]
    return sorted(work or glob.glob(os.path.join(TR, '*.en.json')))


def load_translations(paths=None):
    tr = {}
    for p in paths if paths is not None else tr_files():
        for item in json.load(open(p, encoding='utf-8')):
            if item.get('en'):
                tr[item['key']] = item['en']
    return tr


class Build:
    def __init__(self):
        self.files = {}               # disc path -> bytes
        self.exe_edits = []           # (addr, bytes) in the original image
        self.pool = b''               # relocated strings, copied to vwf.ui_pool_addr()
        self.engine = {}              # options for vwf.patch_exe
        self.report = []


def build(data_e3, tr=None):
    """data_e3: DATA.E3 bytes with the character names already patched (names.py)."""
    b = Build()
    tr = load_translations() if tr is None else tr
    if not tr:
        return b
    units = {u['key']: u for u in load_units()}
    rows = load_rows()
    done = {}
    for k, en in tr.items():
        if k not in units:
            raise KeyError('unknown UI key %s' % k)
        lines, probs = check_unit(units[k], en)
        if probs:
            b.report.append('%s: %s' % (k, '; '.join(probs)))
        done[k] = encode(units[k], lines)
    # ---------------------------------------------------------------- IMSG.E3
    imsg = bytearray(open(os.path.join(DISC, 'DATA', 'IMSG.E3'), 'rb').read())
    hit = False
    for r in rows:
        if r['src'] == 'IMSG' and r['unit'] in done:
            data = done[r['unit']][:99]
            imsg[r['rec'] * 100:(r['rec'] + 1) * 100] = data.ljust(100, b'\0')
            hit = True
            if r['kind'] in ('item_desc', 'skill_desc'):
                b.engine['desc_cap'] = True
    if hit:
        b.files['DATA/IMSG.E3'] = bytes(imsg)
    # ---------------------------------------------------------------- DATA.E3
    d3 = bytearray(data_e3)
    hit = False
    for r in rows:
        if r['src'] == 'DATA' and r['unit'] in done:
            data = done[r['unit']][:r['field']]
            d3[r['off']:r['off'] + r['field']] = data.ljust(r['field'], b'\0')
            hit = True
    if hit:
        b.files['DATA/DATA.E3'] = bytes(d3)
    # ---------------------------------------------------------------- PROFILE.E3
    prows = [r for r in rows if r['src'] == 'PROFILE']
    if any(r['unit'] in done for r in prows):
        b.files['DATA/PROFILE.E3'] = build_profile(prows, done, units)
        b.engine['profile'] = True
        fmt = [r for r in prows if units[r['unit']]['wrap'] == 'profile_fmt']
        n = sum(1 for r in fmt if r['unit'] in done)
        if n == len(fmt):
            b.engine['profile_fmt'] = True
        elif n:
            raise ValueError('translate all %d format profiles (%s) together' % (
                len(fmt), ', '.join(sorted({r['unit'] for r in fmt}))))
    # ---------------------------------------------------------------- MAIN.EXE
    erows = [r for r in rows if r['src'] == 'EXE' and r['unit'] in done]
    if erows:
        exe_strings(b, erows, done, units)
        # world-map town names (pointer table 0x800DDD40, 57 entries): centre by VWF width
        if any(p[0] == 'ptr' and 0x800DDD40 <= int(p[1], 16) < 0x800DDE24
               for r in erows for p in r['patch']):
            b.engine['town_label'] = True
        # English save titles: the save list's 40-byte line buffer is too small, the
        # episode title field (30 bytes) too (vwf SAVE_ASM)
        b.engine['save_desc'] = True
        if b.pool:
            b.engine['pool'] = b.pool
    return b


def build_profile(prows, done, units):
    """Slot format: variant k = one 2048-byte sector '//\\r\\n' + body + '$' (read by
    vwf.py prof_load, which clears the '$' skip count)."""
    src = open(os.path.join(DISC, 'DATA', 'PROFILE.E3'), 'rb').read()
    parts = src.split(b'$')[:-1]
    by_var = {r['variant']: r for r in prows}
    out = bytearray()
    for k, p in enumerate(parts):
        r = by_var.get(k)
        if r and r['unit'] in done:
            body = done[r['unit']]
        else:
            lines = p.split(b'\r\n')
            if k > 0:
                lines = lines[1:]
            body = b''.join(l + b'\r\n' for l in lines if not l.startswith(b'//'))
            body = body.rstrip(b'\r\n') + b'\r\n' if body.strip() else b''
        slot = b'//\r\n' + body + b'$\r\n'
        if len(slot) > PROF_SLOT:
            raise ValueError('profile variant %d is %d bytes (> one sector)' % (k, len(slot)))
        out += slot.ljust(PROF_SLOT, b'\0')
    return bytes(out)


def exe_strings(b, erows, done, units):
    """In-place writes; strings that do not fit their slot are moved (all references
    patched) to freed slots of other moved strings or the unused tails of shorter ones,
    then to the kernel-RAM pool."""
    edits = {}
    regions = []                   # slots freed by moved strings: [start, size, used, buffer]
    moves = []                     # (row, data)
    for r in erows:
        data = done[r['unit']]
        a = int(r['addr'], 16)
        if len(data) <= r['slot']:
            edits[a] = data + b'\0'
            # the rest of a shorter slot takes moved strings too (nothing points inside it)
            n = r['slot'] - len(data)
            if n:
                regions.append([a + len(data) + 1, n, 0, bytearray(n)])
        elif r['reloc'] and not r['gp']:
            moves.append((r, data))
            regions.append([a, r['slot'] + 1, 0, bytearray(r['slot'] + 1)])
        else:
            raise ValueError('%s: %d bytes do not fit the %d-byte slot at %s and the string cannot '
                             'be moved' % (r['unit'], len(data), r['slot'], r['addr']))
    # neighbouring free slots (strings stored back to back) form one larger region
    merged = []
    for reg in sorted(regions):
        if merged and merged[-1][0] + merged[-1][1] == reg[0]:
            merged[-1][1] += reg[1]
            merged[-1][3] += reg[3]
        else:
            merged.append(reg)
    regions = merged
    pool = bytearray()
    pool_addr = vwf.ui_pool_addr()
    pool_cap = vwf.ui_pool_capacity()
    patches = []
    moves.sort(key=lambda m: -len(m[1]))
    for r, data in moves:
        need = len(data) + 1
        dest = None
        for reg in sorted(regions, key=lambda g: g[1] - g[2]):     # best fit
            if reg[1] - reg[2] >= need:
                dest = reg[0] + reg[2]
                reg[3][reg[2]:reg[2] + need] = data + b'\0'
                reg[2] += need
                break
        if dest is None:
            dest = pool_addr + len(pool)
            pool += data + b'\0'
            pool += bytes((-len(pool)) % 4)
            if len(pool) > pool_cap:
                raise ValueError('kernel string pool full (%d > %d bytes)' % (len(pool), pool_cap))
        for p in r['patch']:
            patches.append((p, dest))
        b.report.append('moved %s %s -> %08X (%d bytes)' % (r['unit'], r['addr'], dest, len(data)))
    for reg in regions:
        edits[reg[0]] = bytes(reg[3])
    for a, data in sorted(edits.items()):
        b.exe_edits.append((a, data))
    for p, dest in patches:
        if p[0] == 'ptr':
            b.exe_edits.append((int(p[1], 16), struct.pack('<I', dest)))
        else:
            b.exe_edits.append(('hilo', int(p[1], 16), int(p[2], 16), dest))
    b.pool = bytes(pool)


def patch_exe_strings(exe, b):
    """Apply Build.exe_edits to the original MAIN.EXE bytes."""
    exe = bytearray(exe)
    for e in b.exe_edits:
        if e[0] == 'hilo':
            _, lui_a, lo_a, dest = e
            lo = dest & 0xFFFF
            hi = ((dest + 0x8000) >> 16) & 0xFFFF
            o1, o2 = 0x800 + lui_a - EXE_BASE, 0x800 + lo_a - EXE_BASE
            w1, w2 = struct.unpack_from('<I', exe, o1)[0], struct.unpack_from('<I', exe, o2)[0]
            assert w1 >> 26 == 0x0F and w2 >> 26 == 0x09, hex(lui_a)
            struct.pack_into('<I', exe, o1, (w1 & 0xFFFF0000) | hi)
            struct.pack_into('<I', exe, o2, (w2 & 0xFFFF0000) | lo)
        else:
            a, data = e
            o = 0x800 + a - EXE_BASE
            exe[o:o + len(data)] = data
    return bytes(exe)


# ------------------------------------------------------------------------- preview


def game_profile(slot, special=False, name=b'Takamoto', mark=0x40):
    """Python model of the profile loader 0x80080E9C on one variant slot (after
    prof_load: s0 = 0), as patched by tools/vwf.py -> list of display lines (PROF_LINE bytes)."""
    d = slot
    a3 = 0
    while not (d[a3] == 13 and d[a3 + 1] == 10):
        a3 += 1
    a3 += 2
    out, a2 = bytearray(), 0
    while d[a3] != 0x24:
        c, c1 = d[a3], d[a3 + 1]
        if c == 0x2F and c1 == 0x2F:
            while not (d[a3] == 13 and d[a3 + 1] == 10):
                a3 += 1
            if a2 == 0:
                a2 = PROF_LINE
            continue
        if c == 13 and c1 == 10:
            while a2 < PROF_LINE:
                out.append(0x20)
                a2 += 1
            a2 = 0
            a3 += 2
            continue
        if c != 9:
            out.append(c)
            a2 += 1
        a3 += 1
    if special:
        fmt = bytes(out)
        buf = re.sub(rb'%-?(\d*)s', lambda m: name.ljust(int(m.group(1) or 0)), fmt) + b'\0'
        out, a3 = bytearray(), 0

        def marker(i):
            return buf[i] == 0x81 and buf[i + 1] == mark
        if marker(0):
            out += buf[:2]
            a3, a2 = 2, 2
        else:
            while True:
                out.append(buf[a3])
                a3 += 1
                a2 += 1
                if marker(a3):
                    out += buf[a3:a3 + 2]
                    a3 += 2
                    a2 += 2
                    break
        while True:                                   # segment 2: up to the next marker
            a2 %= 24
            if marker(a3):
                out += buf[a3:a3 + 2]
                a3 += 2
                a2 += 2
                while a2 < 24:
                    out.append(0x20)
                    a2 += 1
                break
            if buf[a3] == 0:
                raise ValueError('format profile without its second marker: the game overruns')
            out.append(buf[a3])
            a3 += 1
            a2 += 1
        a2 = 0
        while buf[a3]:
            a2 %= 24
            if marker(a3):
                out += buf[a3:a3 + 2]
                a3 += 2
                a2 += 2
                pad = 12 if a2 < 13 else 36 if a2 < 36 else a2
                while a2 < pad:
                    out.append(0x20)
                    a2 += 1
            else:
                out.append(buf[a3])
                a3 += 1
                a2 += 1
    lines = []
    i = 0
    while i < len(out) and len(lines) < PROF_LINES:
        lines.append(bytes(out[i:i + PROF_LINE]))
        i += PROF_LINE
    return lines


def preview(key):
    units = {u['key']: u for u in load_units()}
    u = units[key]
    en = load_translations().get(key)
    if not en:
        print('%s has no translation' % key)
        return
    lines, probs = check_unit(u, en)
    data = encode(u, lines)
    if u['src'] == 'PROFILE':
        shown = game_profile(b'//\r\n' + data + b'$', special=u['wrap'] == 'profile_fmt')
        for l in shown:
            print('|%s|' % l.decode('cp932', 'replace'))
    else:
        for l in lines:
            px, nb = measure(l)
            print('%4d px %3d B |%s|' % (px, nb, l))
    for p in probs:
        print('PROBLEM', p)


# ------------------------------------------------------------------------- CLI


def save_title_problems(units, tr):
    """The save title is sprintf(E0065, E0481|E0482, number) + episode[i] + battle part (E0066
    with battle[i], E0483 with a castle name, or E0067 with a clan name), built in a 72-byte
    stack buffer (0x80015EB8): 71 bytes at most. Digits come from table E0484 (ASCII)."""
    def get(k):
        if k in tr:
            return encode(units[k], check_unit(units[k], tr[k])[0])
        return units[k]['jp'].encode('cp932')
    name = max(len(get('E0481')), len(get('E0482')))
    head = len(get('E0065')) - 4 + name + 2 * len(get('E0484'))
    eps = [get('E%04d' % i) for i in range(8, 36)]
    battles = [get('E%04d' % i) for i in range(36, 65)]
    other = max(len(get('E0483')) - 2 + 8, len(get('E0067')) - 2 + 12)    # castle 8 B, clan <= 12 B
    out = []
    for i, ep in enumerate(eps):
        tails = [other] + ([len(get('E0066')) - 6 + len(battles[i]) + 2] if i < len(battles) else [])
        n = head + len(ep) + max(tails)
        if n > 71:
            out.append('save title for E%04d is %d bytes (> 71, 72-byte stack buffer)' % (i + 8, n))
    return out


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'check'
    units = {u['key']: u for u in load_units()}
    if cmd == 'check':
        paths = sys.argv[2:] or tr_files()
        n = bad = 0
        for p in paths:
            for item in json.load(open(p, encoding='utf-8')):
                k = item.get('key')
                if k not in units:
                    print('%s: unknown key %s' % (os.path.basename(p), k))
                    bad += 1
                    continue
                if not item.get('en'):
                    continue
                n += 1
                _, probs = check_unit(units[k], item['en'])
                for pr in probs:
                    bad += 1
                    print('%s %s: %s' % (os.path.basename(p), k, pr))
        for pr in save_title_problems(units, load_translations()):
            bad += 1
            print(pr)
        print('%d units checked, %d problems' % (n, bad))
        sys.exit(1 if bad else 0)
    elif cmd == 'preview':
        for k in sys.argv[2:]:
            preview(k)
    elif cmd == 'stats':
        tr = load_translations()
        for src in ('IMSG', 'PROFILE', 'DATA', 'EXE'):
            ks = [k for k, u in units.items() if u['src'] == src]
            print('%-8s %4d / %4d' % (src, sum(1 for k in ks if k in tr), len(ks)))


if __name__ == '__main__':
    main()
