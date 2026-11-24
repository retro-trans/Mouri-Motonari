"""Push the current build into the running game (DuckStation + GDB), so a savestate
made with an older build shows the new text without replaying.

    python tools/hotload.py              write everything that can be written now
    python tools/hotload.py --dry-run    report what would be written
    python tools/hotload.py --bin PATH   another built .bin (default work/output/test)

Written (at a safe halt, see tools/emulink.py):
  * the VWF kernel code (hooks, dictionary, atlas state) and the font + UI string pool,
    exactly as the entry stub of the built MAIN.EXE would copy them at boot;
  * MAIN.EXE: every byte that differs from the original MAIN.EXE (hook jumps, strings
    translated in place, patched pointers / lui+addiu pairs), plus all translated
    string slots and patch sites (so a string that went back to its original form is
    rewritten too); the area from 0x80125458 (packet buffer at run time) is skipped;
  * FAT_DATA.BIN (the file table: rebuilt files move);
  * the event script in the VM buffer, if the VM is idle (no block running), replaced
    by the built version of the same file.
Not written: data the game copied into its own structures (DATA.E3 names, officer and
item tables in a running game) — those need a new game or a savestate made with the
new build. IMSG.E3 / PROFILE.E3 / scripts loaded later come from the disc anyway.
"""
import argparse
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eex                             # noqa: E402
from build_disc import Disc            # noqa: E402
import emulink                         # noqa: E402
import vwf                             # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_BIN = os.path.join(ROOT, 'work', 'output', 'test', 'MouriMotonari.bin')
ORIG_EXE = os.path.join(ROOT, 'work', 'source', 'disc', 'MAIN.EXE')
ORIG_DATA = os.path.join(ROOT, 'work', 'source', 'disc', 'DATA')
UI_ROWS = os.path.join(ROOT, 'work', 'source', 'text', 'ui_rows.json')
BASE = 0x80010000
PACKETS = 0x80125458                   # GsSetWorkBase area (inside the original image)


def stub_blocks(exe):
    """-> [(src, dst, words), ...] copied by the entry stub (tools/vwf.py STUB)"""
    pc, _, taddr, tsize = struct.unpack_from('<4I', exe, 0x10)
    body = exe[0x800:0x800 + tsize]
    reg = {}
    out = []
    o = pc - taddr
    for _ in range(64):
        w = struct.unpack_from('<I', body, o)[0]
        o += 4
        op, rs, rt, imm = w >> 26, (w >> 21) & 31, (w >> 16) & 31, w & 0xFFFF
        if op == 0x0F:                                   # lui
            reg[rt] = imm << 16
        elif op == 0x0D:                                 # ori
            reg[rt] = reg.get(rs, 0) | imm
        elif op == 0x09:                                 # addiu
            reg[rt] = (reg.get(rs, 0) + (imm - 0x10000 if imm & 0x8000 else imm)) & 0xFFFFFFFF
        elif op == 0x23 and rt == 11 and rs == 8:        # lw t3, 0(t0): copy loop
            out.append((reg[8], reg[9], reg[10]))
            if len(out) == 3:                        # code, font, CODE2 (0.2.17)
                break
    def blob(src, n):
        return body[src - taddr:src - taddr + 4 * n]
    return [(dst, blob(src, n)) for src, dst, n in out], body


def exe_writes(body, orig_body, rows):
    """-> {address: byte} for the MAIN.EXE image"""
    n = min(len(orig_body), PACKETS - BASE)
    want = set(i for i in range(n) if body[i] != orig_body[i])
    for r in rows:
        if r.get('src') != 'EXE' or not r.get('unit'):
            continue
        a = int(r['addr'], 16) - BASE
        want.update(range(a, a + r['slot'] + 1))
        for p in r.get('patch', []):
            for x in p[1:]:
                b = int(x, 16) - BASE
                want.update(range(b, b + 4))
    return {BASE + i: body[i] for i in sorted(want) if i < n}


def runs(writes):
    """{addr: byte} -> [(addr, bytes)] of consecutive runs"""
    out = []
    for a in sorted(writes):
        if out and out[-1][0] + len(out[-1][1]) == a:
            out[-1][1].append(writes[a])
        else:
            out.append([a, bytearray([writes[a]])])
    return [(a, bytes(b)) for a, b in out]


def shape(d, hlen, n=None):
    """(event count, block count per event) of an EEX image (may have trailing bytes)"""
    first = struct.unpack_from('<I', d, hlen)[0]
    nev = (first - hlen) // 4
    offs = struct.unpack_from('<%dI' % nev, d, hlen)
    return [struct.unpack_from('<H', d, o)[0] for o in offs]


def current_script(link, disc):
    """-> (name, built bytes, True if the VM holds exactly the built file)"""
    st = link.vm()
    ram = link.read(emulink.VM_BUF, emulink.VM_BUF_SIZE)
    try:
        ram_shape = shape(ram, st['hlen'])
    except struct.error:
        return None, None, False
    for a in emulink.VM_NAMES:
        name = link.read(a, 12).split(b'\0')[0].decode('latin1')
        if not name.endswith('.EEX'):
            continue
        new = disc.read_file('DATA/' + name)
        if eex.header_len(new) != st['hlen'] or shape(new, st['hlen']) != ram_shape:
            continue
        return name, new, ram[:len(new)] == new
    return None, None, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bin', default=DEFAULT_BIN)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--no-script', action='store_true')
    a = ap.parse_args()
    disc = Disc(a.bin, 'rb')
    exe = disc.read_file('MAIN.EXE')
    blocks, body = stub_blocks(exe)
    orig = open(ORIG_EXE, 'rb').read()
    orig_body = orig[0x800:0x800 + struct.unpack_from('<I', orig, 0x1C)[0]]
    rows = json.load(open(UI_ROWS, encoding='utf-8'))
    ew = runs(exe_writes(body, orig_body, rows))
    fat = disc.read_file('FAT_DATA.BIN')
    print('kernel: %s' % ', '.join('%d bytes at %08x' % (len(b), d) for d, b in blocks))
    print('MAIN.EXE: %d bytes in %d runs' % (sum(len(b) for _, b in ew), len(ew)))
    link = emulink.Link()
    try:
        name, new, same = current_script(link, disc)
        st = link.vm()
        print('script in the VM: %s (%s), VM %s' % (
            name or '?', 'current build' if same else 'older / original build',
            'idle' if link.vm_idle() else 'running a block'))
        if a.dry_run:
            return
        link.safe_halt()
        for dst, b in blocks:
            link.write(dst, b)
        # the glyph records start empty, as the entry stub leaves them (they may have moved
        # since the savestate's build: the old ones are dropped, the text comes back when redrawn)
        link.write(vwf.RECS, b'\xff' * (vwf.NRECS * 8))
        for addr, b in ew:
            link.write(addr, b)
        ram_fat = link.read(emulink.FAT, 16)
        if ram_fat == fat[:16]:
            link.write(emulink.FAT, fat)
        else:
            print('warning: FAT_DATA.BIN not found at %08x, not written' % emulink.FAT)
        if name and not same and not a.no_script:
            if not link.vm_idle():
                print('script not replaced: a block is running (run again when the scene is idle)')
            elif len(new) > emulink.VM_BUF_SIZE:
                print('script not replaced: %s is larger than the VM buffer' % name)
            else:
                link.write(emulink.VM_BUF, new)
                print('script replaced: %s (%d bytes)' % (name, len(new)))
        print('written')
    finally:
        link.close()


if __name__ == '__main__':
    main()
