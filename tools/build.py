"""Build the patched disc image.

    python tools/build.py [--test] [--name N]   -> work/output/test/<N>.bin/.cue (default
                                                   MouriMotonari; another name when that
                                                   image is open in an emulator)

Steps: MAIN.EXE gets the VWF hooks (tools/vwf.py); EEX scripts get the English
text from work/translation/en (tools/insert_text.py); menus, item / skill names and
descriptions and profiles come from work/translation/en/ui (tools/insert_ui.py:
MAIN.EXE strings, IMSG.E3, DATA.E3, PROFILE.E3); --test instead puts a few
hand-written English lines into the first scene (R_00.EEX). Files that grow are
moved to the end of the image; both the ISO9660 directory and the game's own
file table (FAT_DATA.BIN: 24-byte entries name[16], LBA, size) are updated.
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_disc import Disc     # noqa: E402
import vwf                      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_BIN = os.path.join(ROOT, 'Mouri Motonari - Chikai no Sanshi (Japan).bin')
SRC = os.path.join(ROOT, 'work', 'source', 'disc')
OUT = os.path.join(ROOT, 'work', 'output', 'test')
NAME = 'MouriMotonari'
VERSION = '0.8.0'


def update_fat(disc, fat, path):
    e = disc.entries[path.upper()]
    base = os.path.basename(path).encode()
    for o in range(0, len(fat), 24):
        if fat[o:o + 16].rstrip(b'\0') == base:
            struct.pack_into('<2I', fat, o + 16, e.lba, e.size)
            return
    raise KeyError(path)


def test_scripts():
    from eex import Script
    s = Script(open(os.path.join(SRC, 'DATA', 'R_00.EEX'), 'rb').read())
    soldier = '&毛利軍兵士'       # speaker header stays Japanese (portrait lookup)
    lines = [
        soldier + '1\nG-gods, this is awful...\n\n\nAwaya\'s whole unit\'s been\nwiped out, hasn\'t it?\n'
        + soldier + '2\nYeah...\nLooks that way.\n\nAnd it\'s not just here.\nThey say the fort on the\n'
        'Sawatari River was a sight\nyou couldn\'t bear to look at.\nThe longer this war drags on,\n'
        'the higher the bodies pile up...',
        soldier + '1\nAh!\n' + soldier + '2\nWhat is it?',
    ]
    strings = [a for ev, k, a, t in s.all_strings() if int.from_bytes(s.d[a - 4:a - 2], 'little') == 0x27]
    repl = {strings[i]: lines[i].encode('cp932') for i in range(len(lines))}
    return {'DATA/R_00.EEX': s.rebuild(repl)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--name', default=NAME, help='output file name (when the usual one is open elsewhere)')
    a = ap.parse_args()
    name = a.name
    files = {}
    import dte
    import insert_text
    words = []
    if not a.test:
        units = {u['key']: u for u in insert_text.load_units()}
        lo = insert_text.laid_out()
        words = dte.build_dict(t for k, t in sorted(lo.items()) if units[k]['kind'] == 'dialogue')
        print('dictionary:', b' | '.join(words).decode())
    import names
    import insert_ui
    data_e3 = names.patch_data_e3(open(os.path.join(SRC, 'DATA', 'DATA.E3'), 'rb').read(),
                                  names.build_map()[0])
    # menus / items / skills / profiles (tools/insert_ui.py): nothing changes without translations
    ui = insert_ui.Build() if a.test else insert_ui.build(data_e3)
    for line in ui.report:
        print('ui:', line)
    exe = insert_ui.patch_exe_strings(open(os.path.join(SRC, 'MAIN.EXE'), 'rb').read(), ui)
    if not a.test:
        ui.engine['full_names'] = names.full_names()      # profile / officer name readings
    exe, info = vwf.patch_exe(exe, dte.blob(words), ui.engine)
    if ui.engine:
        print('ui engine patches:', ', '.join(sorted(ui.engine)),
              '(pool %d of %d bytes)' % (len(ui.pool), vwf.ui_pool_capacity()))
    files['MAIN.EXE'] = exe
    files['DATA/DATA.E3'] = data_e3
    import title_label
    files['GRAPHIC/LOGO.E3'] = title_label.patch(VERSION)   # URL + version on the title
    if not a.test:
        import mark_labels
        files['GRAPHIC/MARK.E3'] = mark_labels.patch()     # stat / column label tiles
        import duel_icons
        files['GRAPHIC/BA_BACK.BIN'] = duel_icons.patch()  # duel status-panel icons (En / SP)
        import unit_labels
        files['GRAPHIC/BA_UNIT.BIN'] = unit_labels.patch() # 'SHIP' for the 船 stamped on a unit
        import map_labels
        files['GRAPHIC/MMAP.E3'] = map_labels.patch()      # province names on the world maps
    files.update(ui.files)
    if a.test:
        files.update(test_scripts())
    else:
        files.update(insert_text.build_scripts(words))
    import visited
    files.update(visited.patch_scripts(files))         # battle scripts: visited-place tables
    out_bin = os.path.join(OUT, name + '.bin')
    d = Disc.open_copy(SRC_BIN, out_bin)
    fat = bytearray(d.read_file('FAT_DATA.BIN'))
    # grown files go into OUTMOST.DAT (27 MB of padding at the end of the data area):
    # the game's CD reader hangs on sectors past the original end of the disc
    pad = d.entries['OUTMOST.DAT']
    free = [pad.lba, pad.lba + (pad.size + 2047) // 2048]

    def alloc(n):
        if free[0] + n > free[1]:
            raise RuntimeError('OUTMOST.DAT padding is full')
        free[0] += n
        return free[0] - n
    d.alloc = alloc
    for path, data in files.items():
        moved = d.replace(path, data)
        update_fat(d, fat, path)
        print('%-16s %8d bytes%s' % (path, len(data), ' (moved)' if moved else ''))
    d.replace('FAT_DATA.BIN', bytes(fat))
    # movies with subtitles / re-encoded frames (tools/movie.py patch): same sectors, in place
    mdir = os.path.join(ROOT, 'work', 'output', 'movie')
    for f in sorted(os.listdir(mdir)) if os.path.isdir(mdir) else []:
        if f.endswith('.raw'):
            n = d.write_raw_sectors('MOVIE/%s.STR' % f[:-4], open(os.path.join(mdir, f), 'rb').read())
            print('%-16s %8d sectors re-encoded' % ('MOVIE/' + f[:-4] + '.STR', n))
    print('padding used: %d of %d sectors' % (free[0] - pad.lba, free[1] - pad.lba))
    d.close()
    open(os.path.join(OUT, name + '.cue'), 'w').write(
        'FILE "%s.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n' % name)
    print('v%s ->' % VERSION, out_bin)


if __name__ == '__main__':
    main()
