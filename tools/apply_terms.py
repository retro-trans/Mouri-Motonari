"""Normalise glossary terms across the English script, unit by unit.

    python tools/apply_terms.py                 dry run: print every change, change nothing
    python tools/apply_terms.py --apply         write the changes to work/translation/en/NNN.json
    python tools/apply_terms.py --only ID[,ID]  limit the run to some fixes (by "id")

The replacement table is work/glossary/term_fixes.json ("fixes": a list, applied
in order). Each fix:

  id        short name, printed with every change
  jp        Japanese term; a unit is touched only if its Japanese (units.json
            "jp") contains it. "jp_re" (a regex) may be given instead.
  wrong     list of wrong English renderings (literal, case-sensitive, whole
            words; a trailing plural "s" is kept: "Spear General" also fixes
            "Spear Generals"). A rendering that starts with a lower-case letter
            also matches its capitalised form, and the fix is capitalised too.
  wrong_re  list of regexes instead of literal renderings; "en" may then use
            group references (\\1).
  en        the glossary form that replaces them.
  line      true: label/title units only; the Japanese term must be on the same
            line number as the English line (victory-condition lists, where the
            same unit holds "X retreats" for both sides).
  kinds     restrict to unit kinds (dialogue, title, label, choice).
  keys      restrict to these unit keys; "skip_keys" excludes units.
  note      why (documentation only).

Rules: '&' speaker lines are never modified. A literal match that already sits
inside the correct form is left alone, so the table can be re-run after later
review passes without doubling anything. The dry run also runs the
tools/insert_text.py checker on each changed unit and flags new problems.
The files are edited in place (only the "en" value of changed units), so their
formatting and notes are kept.
"""
import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import insert_text                    # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXES = os.path.join(ROOT, 'work', 'glossary', 'term_fixes.json')
UNITS = os.path.join(ROOT, 'work', 'source', 'text', 'units.json')
TR = os.path.join(ROOT, 'work', 'translation', 'en')


def cap(s):
    return s[:1].upper() + s[1:]


def compile_fix(f):
    pats = []          # (regex, replacement, literal correct form or None)
    for w in f.get('wrong', []):
        forms = [(w, f['en'])]
        if w[:1].islower():
            forms.append((cap(w), cap(f['en'])))
        for ww, en in forms:
            rx = re.compile(r'(?<![A-Za-z0-9])' + re.escape(ww) + r'(?=s?(?![A-Za-z0-9]))')
            pats.append((rx, en, en))
    for w in f.get('wrong_re', []):
        pats.append((re.compile(w), f['en'], None))
    f['_pats'] = pats
    f['_jp'] = re.compile(f['jp_re']) if 'jp_re' in f else re.compile(re.escape(f['jp']))
    return f


def fix_line(line, f):
    """Apply one fix to one English line. Returns the new line."""
    for rx, rep, literal in f['_pats']:
        if literal is None:
            line = rx.sub(lambda m: m.expand(rep), line)
            continue
        out, pos = [], 0
        for m in rx.finditer(line):
            s, e = m.span()
            # already correct? (the match lies inside an occurrence of the correct form)
            inside = False
            for c in re.finditer(re.escape(literal), line):
                if c.start() <= s and e <= c.end():
                    inside = True
                    break
            if inside:
                continue
            out.append(line[pos:s])
            out.append(rep)
            pos = e
        out.append(line[pos:])
        line = ''.join(out)
    return line


def apply_unit(unit, en, fixes):
    """-> (new en, [(fix id, old line, new line)])"""
    jp = unit['jp']
    jl = jp.split('\n')
    lines = en.split('\n')
    changes = []
    for f in fixes:
        if 'keys' in f and unit['key'] not in f['keys']:
            continue
        if unit['key'] in f.get('skip_keys', ()):
            continue
        if 'kinds' in f and unit['kind'] not in f['kinds']:
            continue
        if not f['_jp'].search(jp):
            continue
        aligned = f.get('line')
        if aligned and (unit['kind'] == 'dialogue' or len(jl) != len(lines)):
            continue
        for i, line in enumerate(lines):
            if line.startswith('&'):
                continue                      # speaker line: never touched
            if aligned and not f['_jp'].search(jl[i]):
                continue
            new = fix_line(line, f)
            if new != line:
                changes.append((f['id'], line, new))
                lines[i] = new
    return '\n'.join(lines), changes


def replace_in_file(raw, key, old, new):
    """Swap the "en" value of one unit inside the raw JSON text."""
    m = re.search(r'"key":\s*"%s"' % re.escape(key), raw)
    if not m:
        raise ValueError('%s not found' % key)
    nxt = re.compile(r'"key":\s*"').search(raw, m.end())
    end = nxt.start() if nxt else len(raw)
    for ea in (False, True):
        o = json.dumps(old, ensure_ascii=ea)
        mm = re.compile(r'"en":(\s*)' + re.escape(o)).search(raw, m.end(), end)
        if mm:
            return raw[:mm.start()] + '"en":' + mm.group(1) + json.dumps(new, ensure_ascii=ea) + raw[mm.end():]
    raise ValueError('%s: en value not found verbatim' % key)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--apply', action='store_true', help='write the files (default: dry run)')
    ap.add_argument('--only', help='comma-separated fix ids')
    a = ap.parse_args()

    table = json.load(open(FIXES, encoding='utf-8'))
    fixes = [compile_fix(f) for f in table['fixes']]
    if a.only:
        want = set(a.only.split(','))
        fixes = [f for f in fixes if f['id'] in want]
    units = {u['key']: u for u in json.load(open(UNITS, encoding='utf-8'))}

    total = nunits = newprobs = 0
    for path in sorted(glob.glob(os.path.join(TR, '[0-9][0-9][0-9].json'))):
        raw = open(path, encoding='utf-8', newline='').read()
        edited = raw
        for item in json.loads(raw):
            k, en = item['key'], item.get('en')
            if not en or k not in units:
                continue
            new, ch = apply_unit(units[k], en, fixes)
            if not ch:
                continue
            nunits += 1
            total += len(ch)
            before = set(insert_text.check_unit(units[k], en)[1])
            after = [p for p in insert_text.check_unit(units[k], new)[1] if p not in before]
            for fid, o, n in ch:
                print('%s (%s) [%s]\n  - %s\n  + %s' % (k, os.path.basename(path)[:3], fid, o, n))
            for p in after:
                newprobs += 1
                print('  ! CHECK: %s' % p)
            edited = replace_in_file(edited, k, en, new)
        if a.apply and edited != raw:
            with open(path, 'w', encoding='utf-8', newline='') as fh:
                fh.write(edited)
    print('\n%d line changes in %d units; %d new checker problems; %s' % (
        total, nunits, newprobs, 'APPLIED' if a.apply else 'dry run (use --apply to write)'))


if __name__ == '__main__':
    main()
