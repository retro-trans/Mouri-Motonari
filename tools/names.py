"""English character names for DATA.E3 and the script's '&Speaker' lines.

The dialogue handler looks the '&' line up in the character table (DATA.E3:
800 records of 54 bytes, name = 13-byte field, strcmp at 0x80023AE0) for the
portrait and shows it in the name box with trailing digits removed, so both
must carry the same English name of at most 12 bytes. Names are the glossary
'short' form (given name; "Surname I." on clashes) or 'en' when no short exists;
numbered generics keep their digits ("Soldier3" shows "Soldier").

    python tools/names.py          print the map and any problem
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_E3 = os.path.join(ROOT, 'work', 'source', 'disc', 'DATA', 'DATA.E3')
REC, NREC, NAME = 54, 800, 13
MAXLEN = 12

# names in DATA.E3 that are not glossary speakers (non-speaking units / officers)
EXTRA = {
    '一藤宜範': 'Yoshinori', '安田国継': 'Kunitsugu', '南条元続': 'Mototsugu',
    '松平信康': 'Nobuyasu', '下間頼簾': 'Rairen', '鈴木重秀': 'Shigehide',
    '足利義稙': 'Yoshitane', '三宅矢兵衛': 'Yahei', '職人空き': '(Empty)',
    '公家': 'Noble', '姫': 'Princess', '弓隊': 'Archers', '弓騎馬隊': 'Mtd.Archers',
    '鉄砲隊': 'Gunners', '砲隊': 'Cannons', '僧兵': 'Warrior Monk', '鼓笛隊': 'Drummers',
    '元就の母': 'Motonari Mom',      # Motonari's mother (12 bytes)
    # shorter / distinct forms (name box: 12 bytes with the digits)
    '町民': 'Townsfolk', '僧兵': 'War Monk', '荷駄隊': 'Supply', '毛利軍兵士': 'Mouri Troop',
    '謎の僧侶': 'Strange Monk', '室': 'Consort',
    '隆元の妻': 'Lady Ozaki', '元春の妻': 'Lady Shinjo', '隆景の妻': 'Lady Toida',
}
OVERRIDE_LEN = {'弓騎馬隊': 'Mtd.Archer'}


def glossary():
    out = {}
    for c in json.load(open(os.path.join(ROOT, 'work', 'glossary', 'characters.json'), encoding='utf-8')):
        out[c['jp']] = c
    return out


def table_names():
    d = open(DATA_E3, 'rb').read()
    return [d[i * REC:i * REC + NAME].split(b'\0')[0].decode('cp932') for i in range(NREC)]


def build_map():
    """-> ({japanese name: english name}, [problems]) for table names and speakers."""
    g = glossary()
    probs = []
    bases = {}
    for jp in set(table_names()) | set(g):
        b = re.sub(r'[0-9]+$', '', jp)
        if b in bases:
            continue
        c = g.get(b)
        if b in OVERRIDE_LEN:
            en = OVERRIDE_LEN[b]
        elif b in EXTRA:
            en = EXTRA[b]
        elif c:
            en = c.get('short') or c['en']
            if len(en) > MAXLEN and len(c['en'].split()) > 1:
                en = c['en'].split()[-1]          # given name
        else:
            probs.append('no English for %s' % b)
            continue
        bases[b] = en
    # clashes: the character with the most lines keeps the name, the others get
    # 'Surname I.' (or the full name when it fits)
    lines = {b: (g[b].get('lines') or 0) if b in g else 0 for b in bases}
    groups = {}
    for b, en in bases.items():
        groups.setdefault(en, []).append(b)
    for en, bs in groups.items():
        if len(bs) < 2:
            continue
        bs.sort(key=lambda b: -lines[b])
        for b in bs[1:]:
            full = g[b]['en'] if b in g else en
            parts = full.split()
            alt = full if len(full) <= MAXLEN else '%s %s.' % (parts[0][:MAXLEN - 3], parts[-1][0])
            bases[b] = alt
    used = {}
    for b, en in bases.items():
        if en in used and used[en] != b:
            probs.append('name clash: %s for %s and %s' % (en, used[en], b))
        used[en] = b
    out = {}
    for jp in set(table_names()) | set(g):
        b = re.sub(r'[0-9]+$', '', jp)
        if b not in bases:
            continue
        en = bases[b] + jp[len(b):]
        if len(en.encode('ascii')) > MAXLEN:
            probs.append('too long: %s -> %s' % (jp, en))
        out[jp] = en
    return out, probs


READING, READ_LEN = 13, 15     # half-width katakana reading after the name


def full_names():
    """-> 800 x (English full name or None) for the DATA.E3 records (glossary 'en' with a
    family name); printed by the VWF full_name hook where the game printed the reading"""
    g = glossary()
    shown = build_map()[0]               # the name the game already shows beside it
    out = []
    for jp in table_names():
        c = g.get(re.sub(r'[0-9]+$', '', jp))
        en = c['en'] if c else ''
        out.append(en if ' ' in en and en != shown.get(jp) else None)
    return out


def patch_data_e3(data, m):
    """English names. The katakana reading stays: the profile index groups characters by
    its first kana (A-O, Ka-Ko, ...); where the game printed it, the VWF full_name hook
    prints the English full name instead"""
    data = bytearray(data)
    for i in range(NREC):
        o = i * REC
        jp = data[o:o + NAME].split(b'\0')[0].decode('cp932')
        en = m.get(jp)
        if en:
            data[o:o + NAME] = en.encode('ascii')[:MAXLEN].ljust(NAME, b'\0')
    return bytes(data)


if __name__ == '__main__':
    m, probs = build_map()
    for k in sorted(m, key=lambda k: m[k]):
        sys.stdout.buffer.write(('%s\t%s\n' % (m[k], k)).encode('utf-8'))
    for p in probs:
        sys.stdout.buffer.write(('PROBLEM ' + p + '\n').encode('utf-8'))
    print(len(m), 'names,', len(probs), 'problems')
