"""Extract the menu / item / skill / profile text for translation (see docs/text_formats.md).

    python tools/extract_ui.py

Sources (Japanese, from work/source/disc):
  DATA/IMSG.E3     I-units: 100-byte records read on demand (item / skill descriptions,
                   sortie / retreat quotes, battle names, training-ground quotes)
  DATA/PROFILE.E3  P-units: character profiles, one per '$'-separated variant
  DATA/DATA.E3     D-units: item names (16 bytes), castle names (8), skill names (10)
  MAIN.EXE         E-units: menus, messages, format strings (in place, or relocated
                   when every reference to the string can be patched)

Writes (git-ignored):
  work/source/text/ui_units.json        unique strings: key, kind, src, jp, count, first,
                                        context and the limits (max_bytes, max_lines,
                                        line_px, line_bytes, wrap, ...)
  work/source/text/ui_rows.json         every occurrence (where to write it back)
  work/source/text/ui_slices/NNN.json   80 units per slice (translation input)
  work/source/text/ui_skipped.json      debug / unused strings left untranslated
"""
import collections
import json
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISC = os.path.join(ROOT, 'work', 'source', 'disc')
OUT = os.path.join(ROOT, 'work', 'source', 'text')
SLICE = 80

EXE_BASE = 0x80010000
GP = 0x80124040
DATA_LO, DATA_HI = 0x800AC000, 0x80125210      # initialised data (BSS starts at 0x80125210)
PTR_LO = 0x800AB400                             # pointer words are only taken from data

# ------------------------------------------------------------------------- helpers


def jp_px(s):
    """Width of Japanese text in the original 12 px font (half-width = 6 px)."""
    return sum(6 if ord(c) < 0x80 else 12 for c in s)


SPEC = re.compile(r'%(?:[-+ #0]*\d*(?:\.\d+)?l?[a-zA-Z%])?')


def specs(s):
    return SPEC.findall(s)


def strip_pad(s):
    return s.rstrip('　 ')


def chunk_sjis(b, n):
    """Split SJIS bytes into chunks of at most n bytes without splitting a pair."""
    out, cur = [], b''
    i = 0
    while i < len(b):
        k = 2 if (0x81 <= b[i] <= 0x9F or 0xE0 <= b[i] <= 0xEF) else 1
        if len(cur) + k > n:
            out.append(cur)
            cur = b''
        cur += b[i:i + k]
        i += k
    if cur:
        out.append(cur)
    return out


def is_lead(b):
    return 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xEF


# ------------------------------------------------------------------------- IMSG.E3
IMSG_REC = 100
# (kind, first record, count, context, limits)
IMSG_RANGES = [
    ('item_desc', 0x000, 0x100),
    ('skill_desc', 0x100, 0x41),
    ('sortie', 0x14B, 0x38),
    ('retreat', 0x187, 0x38),
    ('battle_name', 0x1C3, 0x1F),
    ('training', 0x28F, 0xB7),
]
IMSG_LIMITS = {
    # item / skill info panel (0x800779BC / 0x80077E5C): window printf '%s', line start
    # x+0xC, x max x+0xF0 (a char is drawn while x <= max): 228 px, 2 lines. The
    # 80-byte cut (sb zero,0x70(sp)) is raised to the full 100-byte record by
    # tools/vwf.py when translations exist.
    'item_desc': dict(wrap='auto', sep='\n', line_px=228, max_lines=2, max_bytes=99),
    'skill_desc': dict(wrap='auto', sep='\n', line_px=228, max_lines=2, max_bytes=99),
    # battle speech balloon 0x800865B4 -> line printer 0x8003DE8C, 26-byte line cap
    'sortie': dict(wrap='auto', sep='\n', line_px=156, line_bytes=26, max_bytes=99),
    'retreat': dict(wrap='auto', sep='\n', line_px=156, line_bytes=26, max_bytes=99),
    # copied into a 30-byte field (0x80069AC8); designer note: 10 full-width chars
    'battle_name': dict(wrap='none', line_px=120, max_lines=1, max_bytes=29),
    # training ground balloon 0x8003957C -> line printer, 20-byte line cap, '\r' breaks
    'training': dict(wrap='auto', sep='\\r', line_px=120, line_bytes=20, max_bytes=99),
}
IMSG_CONTEXT = {
    'item_desc': 'IMSG.E3 item description (item info panel, 2 lines of 228 px)',
    'skill_desc': 'IMSG.E3 skill description (skill info panel, 2 lines of 228 px)',
    'sortie': 'IMSG.E3 sortie quote of an officer (battle speech balloon)',
    'retreat': 'IMSG.E3 retreat quote of an officer (battle speech balloon)',
    'battle_name': 'IMSG.E3 battle name (battle start banner)',
    'training': 'IMSG.E3 training-ground duel quote (speech balloon); a lone % is replaced '
                'at runtime (counted as 16 bytes)',
}


def imsg_logical(kind, raw):
    """Record bytes -> readable Japanese with '\\n' line breaks."""
    if kind in ('item_desc', 'skill_desc'):
        lines = [strip_pad(c.decode('cp932')) for c in chunk_sjis(raw, 40)]
    elif kind in ('sortie', 'retreat'):
        lines = [strip_pad(c.decode('cp932')) for c in chunk_sjis(raw, 26)]
    elif kind == 'training':
        lines = raw.decode('cp932').split('\\r')
        while lines and lines[-1] == '':
            lines.pop()
    else:
        lines = [raw.decode('cp932')]
    while lines and lines[-1] == '':
        lines.pop()
    return '\n'.join(lines)


def extract_imsg(data_e3):
    d = open(os.path.join(DISC, 'DATA', 'IMSG.E3'), 'rb').read()
    items = item_records(data_e3)
    skills = skill_records(data_e3)
    used_desc = collections.defaultdict(list)
    for i, (name, rec) in enumerate(items):
        if name:
            used_desc[rec[20]].append(name)
    rows, skipped = [], []
    for kind, first, n in IMSG_RANGES:
        for k in range(n):
            idx = first + k
            raw = d[idx * IMSG_REC:(idx + 1) * IMSG_REC].split(b'\0')[0]
            jp_raw = raw.decode('cp932')
            if not raw or jp_raw == '終端':
                continue
            ctx = IMSG_CONTEXT[kind]
            if kind == 'item_desc':
                if idx not in used_desc:
                    skipped.append({'src': 'IMSG', 'rec': idx, 'jp': jp_raw, 'why': 'no item uses it'})
                    continue
                ctx += '; items: ' + ', '.join(used_desc[idx][:6])
            elif kind == 'skill_desc':
                ctx += '; skill: ' + (skills[k] if k < len(skills) else '?')
            elif kind in ('sortie', 'retreat'):
                ctx += '; officer #%d' % k
            jp = imsg_logical(kind, raw)
            lim = dict(IMSG_LIMITS[kind])
            if kind in ('sortie', 'retreat', 'training'):
                lim['max_lines'] = None          # set per kind below (Japanese maximum)
            rows.append({'src': 'IMSG', 'kind': kind, 'rec': idx, 'jp': jp, 'context': ctx,
                         'first': 'IMSG/%d' % idx, 'limits': lim})
    for kind in ('sortie', 'retreat', 'training'):
        m = max(r['jp'].count('\n') + 1 for r in rows if r['kind'] == kind)
        for r in rows:
            if r['kind'] == kind:
                r['limits']['max_lines'] = m
    # unused / debug ranges, for the record
    for lo, hi, why in ((0x1EB, 0x1F8, 'base-map descriptions: reader 0x800193E4 has no caller'),
                        (0x1FF, 0x20C, 'room descriptions: reader 0x8001940C has no caller'),
                        (0x213, 0x28F, 'sound-test names (debug menu 0x8007B7E0)')):
        for idx in range(lo, hi):
            raw = d[idx * IMSG_REC:(idx + 1) * IMSG_REC].split(b'\0')[0]
            if raw and raw.decode('cp932') != '終端':
                skipped.append({'src': 'IMSG', 'rec': idx, 'jp': raw.decode('cp932'), 'why': why})
    return rows, skipped


# ------------------------------------------------------------------------- DATA.E3
ITEM_OFF, ITEM_N, ITEM_REC, ITEM_NAME = 0xA8C0, 419, 33, 16
CASTLE_OFF, CASTLE_N, CASTLE_REC, CASTLE_NAME = 0xDEC3, 12, 134, 8
SKILL_OFF, SKILL_N, SKILL_REC, SKILL_NAME = 0xED6F, 65, 49, 10


def _names(d, off, n, size, field):
    out = []
    for i in range(n):
        rec = d[off + i * size:off + (i + 1) * size]
        raw = rec[:field].split(b'\0')[0]
        try:
            name = raw.decode('cp932') if raw and raw[0] not in (0xFF,) else ''
        except UnicodeDecodeError:
            name = ''
        out.append((name, rec))
    return out


def item_records(d):
    return _names(d, ITEM_OFF, ITEM_N, ITEM_REC, ITEM_NAME)


def skill_records(d):
    return [n for n, r in _names(d, SKILL_OFF, SKILL_N, SKILL_REC, SKILL_NAME)]


DATA_TABLES = [
    # kind, offset, count, record size, name field (bytes the game copies), context
    ('item_name', ITEM_OFF, ITEM_N, ITEM_REC, ITEM_NAME,
     'DATA.E3 item name (16-byte field, parser 0x8001913C; lists, shops, item panel)'),
    ('castle_name', CASTLE_OFF, CASTLE_N, CASTLE_REC, CASTLE_NAME,
     'DATA.E3 castle / base name (8-byte field, parser 0x80019D6C)'),
    ('skill_name', SKILL_OFF, SKILL_N, SKILL_REC, SKILL_NAME,
     'DATA.E3 skill name (10-byte field, parser 0x80019E60; skill panel 64 px)'),
]


# measured field widths where they exceed the longest Japanese name
FIELD_PX = {'skill_name': 64}      # skill panel 0x80077E5C: name at x+0x18, next field at x+0x58


def extract_data(d):
    rows = []
    for kind, off, n, size, field, ctx in DATA_TABLES:
        recs = _names(d, off, n, size, field)
        px = max(max(jp_px(nm) for nm, r in recs if nm), FIELD_PX.get(kind, 0))
        for i, (name, rec) in enumerate(recs):
            if not name or not any(is_lead(b) for b in rec[:field]):
                continue
            rows.append({'src': 'DATA', 'kind': kind, 'off': off + i * size, 'field': field,
                         'jp': name, 'context': ctx + '; #%d' % i, 'first': 'DATA/%s/%d' % (kind, i),
                         'limits': dict(wrap='none', max_bytes=field, max_lines=1, line_px=px)})
    return rows


# ------------------------------------------------------------------------- PROFILE.E3
PROF_LINE = 24            # bytes per display line (parser pads CRLF lines to 24 with spaces)
PROF_LINES = 50           # line array of the profile screen (0x8008158C: 50 x 25 bytes)
PROF_BUF = 1256           # output buffer sp+0x20 .. sp+0x508
PROF_SPECIAL = (48, 49)   # character ids whose text is a sprintf format (0x80081044)


def profile_variants():
    """-> list of dicts per '$' variant: owner header, chapter header, body lines."""
    d = open(os.path.join(DISC, 'DATA', 'PROFILE.E3'), 'rb').read()
    parts = d.split(b'$')[:-1]
    out = []
    owner = ''
    for k, p in enumerate(parts):
        lines = p.split(b'\r\n')
        if k > 0:
            lines = lines[1:]               # rest of the '$' line
        heads, body = [], []
        for l in lines:
            if l.startswith(b'//'):
                heads.append(l.decode('cp932', 'replace'))
            else:
                body.append(l)
        while body and body[-1] == b'':
            body.pop()
        for h in heads:
            m = re.match(r'//\s*(\d+)\s+(\S+)', h)
            if m:
                owner = '%s %s' % (m.group(1), m.group(2))
        chap = [h[2:].strip('　 ') for h in heads if not re.match(r'//\s*\d+\s', h)]
        out.append({'variant': k, 'owner': owner, 'chapter': ' / '.join(chap),
                    'jp': '\n'.join(b.decode('cp932') for b in body)})
    return out


def extract_profile():
    rows = []
    for v in profile_variants():
        cid = int(v['owner'].split()[0]) if v['owner'] else -1
        special = cid in PROF_SPECIAL
        lim = dict(wrap='profile', line_bytes=PROF_LINE, line_px=192, max_lines=PROF_LINES,
                   max_bytes=PROF_BUF)
        ctx = 'PROFILE.E3 character profile of %s (%s); screen: 9 visible lines, scrolls' % (
            v['owner'], v['chapter'])
        if special:
            lim['wrap'] = 'profile_fmt'
            ctx += '; sprintf format: %s = name of the officer who won 6 bouts (12 bytes)'
        rows.append({'src': 'PROFILE', 'kind': 'profile', 'variant': v['variant'], 'jp': v['jp'],
                     'context': ctx, 'first': 'PROFILE/%d' % v['variant'], 'limits': lim,
                     'char': cid})
    return rows


# ------------------------------------------------------------------------- MAIN.EXE
class Exe:
    def __init__(self, data):
        self.data = data
        self.body = data[0x800:]
        self.n = len(self.body) // 4
        self.words = struct.unpack_from('<%dI' % self.n, self.body)

    def a2o(self, a):
        return a - EXE_BASE

    def word(self, a):
        return self.words[(a - EXE_BASE) >> 2]


def regs_used(w):
    """-> (reads set, writes set) of GPRs for one instruction (None = control flow)."""
    op = w >> 26
    rs, rt, rd = (w >> 21) & 31, (w >> 16) & 31, (w >> 11) & 31
    if op == 0:
        fn = w & 63
        if fn in (8, 9):                       # jr / jalr
            return None
        if fn in (0x10, 0x12):                 # mfhi / mflo
            return set(), {rd}
        if fn in (0x11, 0x13):
            return {rs}, set()
        if fn in (0x18, 0x19, 0x1A, 0x1B):     # mult / div
            return {rs, rt}, set()
        if fn in (0, 2, 3):                    # sll / srl / sra
            return {rt}, {rd}
        if fn in (0x0C, 0x0D):                 # syscall / break
            return None
        return {rs, rt}, {rd}
    if op in (1, 4, 5, 6, 7, 2, 3):
        return None
    if 8 <= op <= 14:
        return {rs}, {rt}
    if op == 15:
        return set(), {rt}
    if 0x20 <= op <= 0x26:
        return {rs}, {rt}
    if 0x28 <= op <= 0x2E:
        return {rs, rt}, set()
    if op in (0x10, 0x11, 0x12, 0x13):
        return {rt}, {rt}                      # conservative
    if op in (0x32, 0x3A):                     # lwc2 / swc2
        return {rs}, set()
    return {rs, rt}, {rt}


def branch_targets(exe, lo, hi):
    """Targets of branches / jumps located in [lo, hi)."""
    out = set()
    for a in range(lo, hi, 4):
        if a < EXE_BASE or a >= EXE_BASE + exe.n * 4:
            continue
        w = exe.word(a)
        op = w >> 26
        if op in (1, 4, 5, 6, 7):
            off = w & 0xFFFF
            if off & 0x8000:
                off -= 0x10000
            out.add(a + 4 + off * 4)
        elif op in (2, 3):
            out.add((a & 0xF0000000) | ((w & 0x3FFFFFF) << 2))
    return out


def scan_refs(exe):
    """-> (ptrs {target: [word addr]}, code {target: [(lo addr, lui addr or None, kind)]})"""
    ptrs = collections.defaultdict(list)
    code = collections.defaultdict(list)
    for k, w in enumerate(exe.words):
        a = EXE_BASE + k * 4
        if a >= PTR_LO and DATA_LO <= w < DATA_HI:
            ptrs[w].append(a)
        op = w >> 26
        if op in (0x09, 0x0D, 0x20, 0x21, 0x23, 0x24, 0x25, 0x28, 0x29, 0x2B) and a < PTR_LO:
            rs = (w >> 21) & 31
            imm = w & 0xFFFF
            simm = imm - 0x10000 if (imm & 0x8000 and op != 0x0D) else imm
            if rs == 28:
                t = (GP + simm) & 0xFFFFFFFF
                if DATA_LO <= t < DATA_HI:
                    code[t].append((a, None, 'gp'))
                continue
            strict = True
            for m in range(1, 24):
                if k - m < 0:
                    break
                pw = exe.words[k - m]
                if pw >> 26 == 0x0F and (pw >> 16) & 31 == rs:
                    t = (((pw & 0xFFFF) << 16) + simm) & 0xFFFFFFFF
                    if DATA_LO <= t < DATA_HI:
                        code[t].append((a, EXE_BASE + (k - m) * 4,
                                        ('addiu' if op == 0x09 else 'mem') + ('' if strict else '?')))
                    break
                ru = regs_used(pw)
                if ru is not None and rs in ru[1]:
                    strict = False                 # rs redefined on this path: maybe another path
    return ptrs, code


def pair_safe(exe, lo_a, lui_a):
    """Can the lui/addiu pair (lui_a, lo_a) be retargeted without touching other users?"""
    if (lui_a, lo_a) in SAFE_PAIRS:
        return True
    w = exe.word(lo_a)
    if w >> 26 != 0x09:
        return False
    r = exe.word(lui_a) >> 16 & 31
    rt = (w >> 16) & 31
    for a in range(lui_a + 4, lo_a, 4):          # nothing in between touches r
        ru = regs_used(exe.word(a))
        if ru is None or r in ru[0] or r in ru[1]:
            return False
    if any(lui_a < t <= lo_a for t in branch_targets(exe, lo_a - 0x4000, lo_a + 0x4000)):
        return False
    if rt == r:
        return True
    a = lo_a + 4                                   # r must be dead after the addiu
    for _ in range(48):
        w2 = exe.word(a)
        ru = regs_used(w2)
        if ru is None:
            op = w2 >> 26
            # the delay slot runs first
            ru2 = regs_used(exe.word(a + 4))
            if ru2 is not None:
                if r in ru2[0]:
                    return False
                if r in ru2[1]:
                    return True
            if op == 3 or (op == 0 and (w2 & 63) == 9):   # call: dead unless an argument
                return r not in (4, 5, 6, 7)
            return False
        if r in ru[0]:
            return False
        if r in ru[1]:
            return True
        a += 4
    return False


def next_call(exe, a, limit=20):
    for k in range(1, limit):
        w = exe.word(a + 4 * k)
        if w >> 26 == 3:
            return ((a + 4 * k) & 0xF0000000) | ((w & 0x3FFFFFF) << 2)
    return None


def scan_strings(exe, halfwidth=False):
    """-> {addr: bytes}; halfwidth: also accept half-width kana / punctuation (0xA1-0xDF)"""
    body = exe.body
    lo, hi = DATA_LO - EXE_BASE, DATA_HI - EXE_BASE
    out = {}
    i = lo
    while i < hi:
        if body[i] == 0 or not (body[i - 1] == 0 or i % 4 == 0):
            i += 1
            continue
        j, sj, ok = i, 0, True
        while j < hi and body[j]:
            b = body[j]
            if is_lead(b) and 0x40 <= body[j + 1] <= 0xFC and body[j + 1] != 0x7F:
                sj += 1
                j += 2
            elif 0x20 <= b < 0x7F or b == 0x0A or (halfwidth and 0xA1 <= b <= 0xDF):
                j += 1
            else:
                ok = False
                break
        if ok and sj and body[j] == 0:
            try:
                body[i:j].decode('cp932')
                out[EXE_BASE + i] = body[i:j]
            except UnicodeDecodeError:
                pass
            i = j + 1
        else:
            i += 1
    return out


# printers recognised from the call that follows a reference
CALL_KIND = {
    0x8003F828: 'msgbox',       # message box sized by bytes: width = 8 px/byte + 32 (<= 36 bytes)
    0x800397CC: 'balloon20',    # speech balloon 144x64, line printer cap 20 bytes
    0x8003957C: 'balloon20',
    0x8006FE74: 'balloon26',    # shop / forge keeper balloon, cap 26 bytes
    0x800865B4: 'balloon26',
    0x8001BC3C: 'label',        # window printf at a fixed position
    0x8001BB74: 'label',        # window puts
    0x800A9DFC: 'format',       # sprintf into a buffer, printed later
}
BATTLE_QUOTES = (0x80101A80, 0x80101B30)        # pointer table of attack quotes -> balloon26

# developer-only / debug strings (left in Japanese; listed in docs/text_formats.md)
DEBUG_TABLES = [(0x800FF810, 0x800FF8E0, 'debug menu: movie / face / sound test')]
DEBUG_PATTERNS = ['::', 'ERROR', '不正', 'HD', '読み込みに失敗', 'アニメ領域', 'おかしいです',
                  'いけへん', 'ワープ', '０人プレイ']


# lui/addiu pairs checked by hand: the lui at 0x800162E8 sits in a beqz delay slot, but the
# taken path loads v0 again at 0x800162F4 (save-title prefix E0481)
SAFE_PAIRS = {(0x800162E8, 0x800162F0)}

# limits found in game or in the code (instead of the width of the Japanese); None = no px limit
LIMIT_OVERRIDES = {
    # save-title pieces: one sprintf / strcat title, checked as a whole by insert_ui (72-byte buffer)
    'E0065': {'line_px': None}, 'E0066': {'line_px': None}, 'E0067': {'line_px': None},
    'E0481': {'line_px': None}, 'E0482': {'line_px': None}, 'E0483': {'line_px': None},
    # particle inside the E0097 / E0216 messages (the whole line is checked there)
    'E0495': {'line_px': None},
    # weather: %s of the message box E0348, which grows with the text
    'E0718': {'line_px': None}, 'E0719': {'line_px': None}, 'E0720': {'line_px': None},
    # turn counter box above the victory conditions (x 240, box about 72 px; seen in game)
    'E0397': {'line_px': 70},
    # castle-town map facility label (free text on the map, like E0550-E0558; seen in game)
    'E0549': {'line_px': 60},
    # 攻撃: battle action-ring label (free text under the icon, seen in game next to
    # "Victory Cond."), item-effect lists (48 px) and the "<unit>: %s" caption
    'E0567': {'line_px': 48},
}
# world-map town labels (pointer table 0x800DDD40): free outlined text, centred on the town
# by its VWF width and kept on screen (vwf.py town_label), so not bound by the Japanese width
LIMIT_OVERRIDES.update({'E%04d' % n: {'line_px': 120, 'max_bytes': 16}
                        for n in list(range(128, 135)) + list(range(499, 549))})


def exe_category(exe, refs_code, refs_ptr):
    cats = set()
    for lo_a, lui_a, k in refs_code:
        t = next_call(exe, lo_a)
        cats.add(CALL_KIND.get(t, 'other'))
    for p in refs_ptr:
        if BATTLE_QUOTES[0] <= p < BATTLE_QUOTES[1]:
            cats.add('balloon26')
        else:
            cats.add('table')
    for c in ('balloon20', 'balloon26', 'msgbox', 'label', 'format', 'table', 'other'):
        if c in cats:
            return c, sorted(cats)
    return 'other', sorted(cats)


CAT_CONTEXT = {
    'msgbox': 'message box (grows with the longest line: 8 px per byte, max 36 bytes per line)',
    'balloon20': 'speech balloon (line printer, 20 bytes per line)',
    'balloon26': 'speech balloon (line printer, 26 bytes per line)',
    'label': 'fixed-position label / menu text',
    'format': 'format string (sprintf), shown later in a message',
    'table': 'entry of a pointer table (menu / list / names)',
    'other': 'other UI text',
}

# code areas -> screen (rough map for the context field)
AREAS = [
    (0x80015800, 0x80016E00, 'save / load screen'), (0x80018000, 0x80019C00, 'item get / level up'),
    (0x80022C00, 0x80023200, 'settings'), (0x80024200, 0x80025400, 'castle / town menu'),
    (0x80027000, 0x8002A800, 'storage / equipment'), (0x80031000, 0x80035800, 'training ground'),
    (0x80038000, 0x8003C400, 'battle (duel / effects)'), (0x8003E000, 0x80040000, 'message window'),
    (0x80040000, 0x80069C00, 'battle map'), (0x8006D800, 0x80072800, 'forge (workshop)'),
    (0x80072800, 0x80075800, 'shop'), (0x80077000, 0x8007B200, 'item / skill / officer panels'),
    (0x80081000, 0x80083C00, 'character profiles'), (0x80086000, 0x80087400, 'battle animation'),
]


def area(a):
    for lo, hi, name in AREAS:
        if lo <= a < hi:
            return name
    return ''


def extract_exe():
    data = open(os.path.join(DISC, 'MAIN.EXE'), 'rb').read()
    exe = Exe(data)
    strs = scan_strings(exe)
    ptrs, code = scan_refs(exe)
    starts = sorted(strs)
    # strings with half-width characters (｡ ｢ ｣ ...) were missed by the first scan; they get
    # keys after all existing units (rows_late), so the existing keys stay as they are
    late = {a: r for a, r in scan_strings(exe, halfwidth=True).items()
            if a not in strs and any(0xA1 <= b <= 0xDF for b in r)}
    # loose lui/lo matches ('?': the register is redefined in between on the straight path,
    # so the lui may come from another branch) count only when they hit a string start
    for t in list(code):
        if t not in strs and t not in late:
            code[t] = [c for c in code[t] if not c[2].endswith('?')]
    # references that land inside a string (not at its start): such strings stay as they are
    inner = set()
    for t in [t for t in list(ptrs) + list(code) if ptrs.get(t) or code.get(t)]:
        for s in starts:
            if s < t < s + len(strs[s]):
                inner.add(s)
    for t in [t for t in list(ptrs) + list(code) if ptrs.get(t) or code.get(t)]:
        for s in late:
            if s < t < s + len(late[s]):
                inner.add(s)
    rows, skipped, rows_late = [], [], []
    tables = {}
    for s in starts + sorted(late):
        is_late = s in late
        raw = late[s] if is_late else strs[s]
        jp = raw.decode('cp932')
        rp, rc = ptrs.get(s, []), code.get(s, [])
        why = None
        if not rp and not rc:
            why = 'not referenced'
        elif s in inner:
            why = 'referenced inside the string'
        elif any(lo <= p < hi for p in rp for lo, hi, _ in DEBUG_TABLES):
            why = 'debug menu'
        elif any(p in jp for p in DEBUG_PATTERNS):
            why = 'developer / debug message'
        if why:
            if not is_late or why != 'not referenced':     # late finds inside other strings
                skipped.append({'src': 'EXE', 'addr': '%08X' % s, 'jp': jp, 'why': why})
            continue
        # slot: string + NUL + padding up to the next object (4-byte aligned)
        end = s + len(raw) + 1
        lim_end = (end + 3) & ~3
        o = end - EXE_BASE
        while o < lim_end - EXE_BASE and exe.body[o] == 0:
            o += 1
        slot = EXE_BASE + o - s - 1
        patch = []
        reloc = True
        for lo_a, lui_a, k in rc:
            if k == 'addiu' and pair_safe(exe, lo_a, lui_a):
                patch.append(['hilo', '%08X' % lui_a, '%08X' % lo_a])
            else:
                reloc = False
        for p in rp:
            patch.append(['ptr', '%08X' % p])
        cat, cats = exe_category(exe, rc, rp)
        where = sorted({area(a) for a, _, _ in rc} - {''})
        ctx = 'MAIN.EXE %08X: %s' % (s, CAT_CONTEXT[cat])
        if where:
            ctx += '; ' + ', '.join(where)
        if rp:
            ctx += '; pointer table at %08X' % rp[0]
        lines = jp.split('\n')
        lim = dict(wrap='manual', max_bytes=slot)
        if cat == 'msgbox':
            lim.update(line_bytes=36, max_lines=len(lines) + 1)
        elif cat in ('balloon20', 'balloon26'):
            n = 20 if cat == 'balloon20' else 26
            lim.update(line_bytes=n, line_px=n * 6, max_lines=max(len(lines), 3 if n == 26 else 4))
        else:
            lim.update(line_px=max(jp_px(strip_specs(l)) for l in lines), max_lines=len(lines),
                       px_from='jp')
        row = {'src': 'EXE', 'kind': cat, 'addr': '%08X' % s, 'slot': slot, 'jp': jp,
               'context': ctx, 'first': 'EXE/%08X' % s, 'limits': lim, 'patch': patch,
               'reloc': reloc, 'gp': any(k == 'gp' for _, _, k in rc)}
        if rp and not rc:
            tables.setdefault(table_start(exe, rp[0]), []).append(row)
        (rows_late if is_late else rows).append(row)
    # entries of one pointer table share the widest entry's width
    for t, rs in tables.items():
        px = max(r['limits'].get('line_px') or 0 for r in rs)
        for r in rs:
            if r['kind'] == 'table':
                r['limits']['line_px'] = px
    return rows, skipped, rows_late


def strip_specs(s):
    return SPEC.sub('', s)


def table_start(exe, p):
    while DATA_LO <= exe.word(p - 4) < DATA_HI or exe.word(p - 4) == 0 and DATA_LO <= exe.word(p - 8) < DATA_HI:
        p -= 4
    return p


# ------------------------------------------------------------------------- units


def make_units(rows):
    units, index = [], {}
    prefix = {'IMSG': 'I', 'PROFILE': 'P', 'DATA': 'D', 'EXE': 'E'}
    counters = collections.Counter()
    for r in rows:
        k = (r['src'], r['kind'], r['jp'])
        if k not in index:
            counters[r['src']] += 1
            u = {'key': '%s%04d' % (prefix[r['src']], counters[r['src']]), 'kind': r['kind'],
                 'src': r['src'], 'first': r['first'], 'count': 0, 'jp': r['jp'],
                 'context': r['context']}
            u.update(r['limits'])
            index[k] = len(units)
            units.append(u)
        u = units[index[k]]
        u['count'] += 1
        r['unit'] = u['key']
        # the most restrictive occurrence wins
        for f in ('max_bytes', 'line_bytes', 'line_px', 'max_lines'):
            v = r['limits'].get(f)
            if v is not None and (u.get(f) is None or v < u[f]):
                u[f] = v
    for u in units:
        for f in ('line_bytes', 'line_px', 'max_lines'):
            u.setdefault(f, None)
    return units


def main():
    os.makedirs(os.path.join(OUT, 'ui_slices'), exist_ok=True)
    data_e3 = open(os.path.join(DISC, 'DATA', 'DATA.E3'), 'rb').read()
    i_rows, i_skip = extract_imsg(data_e3)
    d_rows = extract_data(data_e3)
    e_rows, e_skip, e_late = extract_exe()
    p_rows = extract_profile()
    rows = d_rows + e_rows + i_rows + p_rows + e_late
    e_rows = e_rows + e_late
    units = make_units(rows)
    # relocatable EXE units may grow beyond their slot (placed in free space by insert_ui)
    by_key = {u['key']: u for u in units}
    for r in e_rows:
        u = by_key[r['unit']]
        u.setdefault('_reloc', True)
        u['_reloc'] = u['_reloc'] and r['reloc'] and not r['gp']
    for u in units:
        if u.pop('_reloc', False):
            u['relocatable'] = True
            n = len(u['jp'].encode('cp932'))
            cap = u.get('line_bytes') and (u['line_bytes'] + 1) * (u['max_lines'] or 1) - 1
            u['max_bytes'] = max(u['max_bytes'], cap or n + n // 2 + 4)
        elif u['src'] == 'EXE':
            u['relocatable'] = False
    for u in units:
        if u['key'] in LIMIT_OVERRIDES:
            u.update(LIMIT_OVERRIDES[u['key']])
            u.pop('px_from', None)
    json.dump(rows, open(os.path.join(OUT, 'ui_rows.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    json.dump(units, open(os.path.join(OUT, 'ui_units.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(i_skip + e_skip, open(os.path.join(OUT, 'ui_skipped.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    sd = os.path.join(OUT, 'ui_slices')
    for f in os.listdir(sd):
        if f.endswith('.json'):
            os.remove(os.path.join(sd, f))
    for i in range(0, len(units), SLICE):
        json.dump(units[i:i + SLICE], open(os.path.join(sd, '%03d.json' % (i // SLICE)), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
    c = collections.Counter(u['src'] for u in units)
    print('units: %s; rows %d; skipped %d; slices %d' % (
        ', '.join('%s %d' % kv for kv in sorted(c.items())), len(rows), len(i_skip) + len(e_skip),
        (len(units) + SLICE - 1) // SLICE))


if __name__ == '__main__':
    main()
