"""Insert the English script text into the EEX files.

    python tools/insert_text.py check [work/translation/en/NNN.json ...]   lint translations
    python tools/insert_text.py stats                                     coverage per file

Input: work/translation/en/NNN.json (lists of {key, en, note}) for the units of
work/source/text/units.json. Untranslated units keep their Japanese bytes.

Dialogue (op 0x27): sections start with a '&Speaker' line, copied from the
Japanese (the game looks the name up in its character table for the portrait;
see docs/TRANSLATING.md). Each section's text is word-wrapped to LINE_PX with
the VWF widths; a blank line in the English forces a new page; pages are 3
lines (the window pages every 3 lines, so a page break = pad to 3 lines).
Titles (caption box) keep the translator's line breaks, up to TITLE_PX. Op 0x28
labels show in the dialogue window without a portrait (0x8003E470: box 256 x 112,
text x 40..280, 6 lines per page): narration (prose, not battle names / condition
lists) is re-wrapped to NARR_PX, each block between blank lines padded to whole
pages, as the Japanese blank lines did; other op 0x28 labels keep their breaks, up
to NARR_PX. Op 0x2C labels (scene goals, text box 0x8003F828, sized by VWF width
since 0.2.14) keep their breaks, up to LABEL_PX. Choices keep the Japanese width
limit (12 px per full-width character).
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eex import Script               # noqa: E402
import vwf                            # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT = os.path.join(ROOT, 'work', 'source', 'text')
TR = os.path.join(ROOT, 'work', 'translation', 'en')
DATA = os.path.join(ROOT, 'work', 'source', 'disc', 'DATA')
LINE_PX = 168
LINE_BYTES = 80              # dialogue line printer cap (patched from 26/28 in tools/vwf.py)
PAGE = 3
BUFFER_MAX = 0x18000           # script load buffer (0x801A8000)

_ADV = None


def adv():
    global _ADV
    if _ADV is None:
        _ADV = vwf.advances()
    return _ADV


def width(s):
    a = adv()
    return sum(a.get(ord(c), 12) for c in s)


def jp_width(s):
    return sum(6 if ord(c) < 0x80 else 12 for c in s)


def wrap(par, limit=LINE_PX):
    """Greedy word wrap of one paragraph (explicit '\\n' kept)."""
    out = []
    for hard in par.split('\n'):
        line = ''
        for word in hard.split(' '):
            cand = word if not line else line + ' ' + word
            if (width(cand) <= limit and len(cand) <= LINE_BYTES) or not line:
                line = cand
            else:
                out.append(line)
                line = word
        out.append(line)
    return out


_NAMES = None


def speaker(jp_line):
    """'&日本語名3' -> '&English3' (tools/names.py; the same names go into DATA.E3)."""
    global _NAMES
    if _NAMES is None:
        import names
        _NAMES = names.build_map()[0]
    name = jp_line[1:]
    en = _NAMES.get(name)
    if en is None:
        base = re.sub(r'[0-9]+$', '', name)
        en = _NAMES.get(base, base) + name[len(base):]
    return '&' + en


def layout_dialogue(en):
    """English dialogue unit -> game text (str) and list of problems."""
    probs = []
    out = []
    sections = re.split(r'(?:^|\n)(?=&)', en.strip('\n'))
    for sec in sections:
        if not sec:
            continue
        if sec.startswith('&'):
            head, _, body = sec.partition('\n')
            out.append(speaker(head))
        else:
            body = sec
        pars = re.split(r'\n\s*\n', body.strip('\n'))
        lines = []
        for k, par in enumerate(pars):
            wl = wrap(par.strip())
            for l in wl:
                if width(l) > LINE_PX or len(l) > LINE_BYTES:
                    probs.append('line too wide (%d px, %d bytes): %s' % (width(l), len(l), l))
            lines += wl
            if k < len(pars) - 1:
                lines += [''] * ((-len(lines)) % PAGE)
        out += lines
        if len('\n'.join(lines)) > 1000:
            probs.append('speaker section over 1000 bytes (1 KB text buffer); split it with a repeated speaker line')
    return '\n'.join(out), probs


TITLE_PX = 288                 # caption box (0x8003F4E4) sized by VWF width since 0.2.12: text + 32 px frame <= 320
TITLE_BYTES = 63               # caption line buffer (0x40 per line)


LABEL_PX = 256                 # text box 0x8003F828 (vwf.py box_w): text + 32 px frame, centred
NARR_PX = 240                  # op 0x28 window text area x 40..280
NARR_PAGE = 6                  # lines per page of that window


def is_narration(u, en):
    """op 0x28 prose: not a battle name / victory-condition list"""
    return (u.get('op') == 0x28 and 'Conditions' not in en
            and not any(l.startswith('  ') for l in en.split('\n')))


def reflow(en, limit=NARR_PX, page=NARR_PAGE):
    """join each block of non-blank lines and wrap it to limit px; every block but the last
    is padded with blank lines to whole pages (the blank lines between blocks were that)"""
    blocks, cur = [], []
    for l in en.split('\n'):
        if l.strip():
            cur.append(l.strip())
        elif cur:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)
    out = []
    for i, b in enumerate(blocks):
        lines = wrap(' '.join(b), limit)
        if i < len(blocks) - 1:
            lines += [''] * (-len(lines) % page)
        out += lines
    return '\n'.join(out)


def layout_plain(jp, en, kind='', u=None):
    probs = []
    jl, el = jp.split('\n'), en.split('\n')
    limit = max(jp_width(l) for l in jl)
    if kind == 'label':
        if u is not None and is_narration(u, en):
            en = reflow(en)
            el = en.split('\n')
        lim = NARR_PX if u is not None and u.get('op') == 0x28 else LABEL_PX
        for l in el:
            if width(l) > lim:
                probs.append('line too wide (%d px > %d): %s' % (width(l), lim, l))
        if len(el) > max(12, len(jl)):
            probs.append('%d lines > 12 (box taller than the screen)' % len(el))
        return en, probs
    if kind == 'title':
        for l in el:
            if len(l) > TITLE_BYTES or width(l) > TITLE_PX:
                probs.append('caption over %d px / %d bytes (%d px): %s' % (TITLE_PX, TITLE_BYTES, width(l), l))
        if len(el) != len(jl):
            probs.append('line count %d != Japanese %d' % (len(el), len(jl)))
        return en, probs
    for l in el:
        if width(l) > max(limit, 24):
            probs.append('line too wide (%d px > %d): %s' % (width(l), limit, l))
    if len(el) != len(jl):
        probs.append('line count %d != Japanese %d' % (len(el), len(jl)))
    return en, probs


def check_unit(u, en):
    probs = []
    try:
        en.encode('ascii')
    except UnicodeEncodeError:
        if u['kind'] != 'dialogue' or any(ord(c) > 0x7F for l in en.split('\n') if not l.startswith('&') for c in l):
            probs.append('non-ASCII characters')
    if u['kind'] == 'dialogue':
        jh = [l for l in u['jp'].split('\n') if l.startswith('&')]
        eh = [l for l in en.split('\n') if l.startswith('&')]
        if jh != eh:
            probs.append('speaker headers differ from the Japanese (%d vs %d)' % (len(eh), len(jh)))
        text, p = layout_dialogue(en)
    else:
        text, p = layout_plain(u['jp'], en, u['kind'], u)
    return text, probs + p


def load_units():
    return json.load(open(os.path.join(TEXT, 'units.json'), encoding='utf-8'))


def tr_files():
    """working files; a clone of the repository has only the Japanese-free .en.json copies"""
    return (sorted(glob.glob(os.path.join(TR, '[0-9][0-9][0-9].json')))
            or sorted(glob.glob(os.path.join(TR, '[0-9][0-9][0-9].en.json'))))


def load_translations(paths=None):
    tr = {}
    for p in paths or tr_files():
        for item in json.load(open(p, encoding='utf-8')):
            if item.get('en'):
                tr[item['key']] = item['en']
    return tr


def laid_out():
    """-> {unit key: game text} for every translated unit."""
    units = {u['key']: u for u in load_units()}
    return {k: check_unit(units[k], en)[0] for k, en in load_translations().items() if k in units}


def build_scripts(words=None):
    """-> {disc path: new EEX bytes} for every script with translated units.
    words: dictionary (tools/dte.py) used to encode dialogue bodies."""
    import dte
    units = {u['key']: u for u in load_units()}
    rows = json.load(open(os.path.join(TEXT, 'rows.json'), encoding='utf-8'))
    tr = load_translations()
    by_file = {}
    for r in rows:
        by_file.setdefault(r['file'], []).append(r)
    out = {}
    for name, rs in by_file.items():
        repl = {}
        for r in rs:
            en = tr.get(r['unit'])
            if not en:
                continue
            text, probs = check_unit(units[r['unit']], en)
            if words and units[r['unit']]['kind'] == 'dialogue':
                repl[r['off']] = dte.encode(text, words)
            else:
                repl[r['off']] = text.encode('cp932')
        if not repl:
            continue
        s = Script(open(os.path.join(DATA, name + '.EEX'), 'rb').read(), name)
        data = s.rebuild(repl)
        # the rebuilt script must parse op by op with the same blocks and IFs
        chk = Script(data, name)
        if chk.problems or [len(b) for b in chk.blocks] != [len(b) for b in s.blocks] or \
                [len(b.ifs) for bl in chk.blocks for b in bl] != [len(b.ifs) for bl in s.blocks for b in bl]:
            raise ValueError('%s: rebuilt script does not parse: %s' % (name, chk.problems[:3]))
        if len(data) > BUFFER_MAX:
            print('WARNING: %s is %d bytes, over the %d-byte script buffer' % (name, len(data), BUFFER_MAX))
        out['DATA/%s.EEX' % name] = data
    return out


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'check'
    units = {u['key']: u for u in load_units()}
    if cmd == 'check':
        paths = sys.argv[2:] or None
        n = bad = 0
        for p in paths or tr_files():
            for item in json.load(open(p, encoding='utf-8')):
                if item['key'] not in units:
                    print('%s: unknown key %s' % (p, item['key']))
                    bad += 1
                    continue
                n += 1
                _, probs = check_unit(units[item['key']], item.get('en', ''))
                for pr in probs:
                    bad += 1
                    print('%s %s: %s' % (os.path.basename(p), item['key'], pr))
        print('%d units checked, %d problems' % (n, bad))
    elif cmd == 'stats':
        tr = load_translations()
        print('%d / %d units translated' % (len(tr), len(units)))


if __name__ == '__main__':
    main()
