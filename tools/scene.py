"""Show any script text in the running game at once (DuckStation + GDB), without
playing to its scene.

    python tools/scene.py U00307                 the unit as the game shows it
    python tools/scene.py U00307 U00308 ...      several units, one after another
    python tools/scene.py U00051 --block         every text op of the unit's event block
    python tools/scene.py U00307 --out DIR       screenshots (default work/ui/shots/scene)
    python tools/scene.py U00307 --no-hotload    skip tools/hotload.py first

How: the text ops (dialogue 0x27, captions 0x28-0x2B, labels 0x2C, choices 0x12) are
taken from the built script on the test disc (so they carry the build's dictionary
encoding), put into a one-block action — u16 length, the ops, op 0000 — in the unused
tail of the script VM buffer, and the VM is told to start it: read pointer = that
block, start marker (+0xC) != 0xFFFF, written when the scene's script tick enters the
event-start routine 0x80021CB4 with the VM idle; that same call then runs it like any
event block: portraits, name boxes, paging and choices are the game's own.
The ops have no side effects (no flags, units or items), and when the block ends the
VM is idle again in the same scene.

Needs: an idle VM (no event running) in a scene whose script tick runs — castle rooms,
the town map and the battle map in the player phase work. Run tools/hotload.py first
(done by default) so the kernel dictionary matches the build the text comes from.
Screenshots: one per page, both framebuffers side by side; Circle is pressed between
pages until the block has ended.
"""
import argparse
import json
import os
import struct
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eex                             # noqa: E402
import eex_ops                         # noqa: E402
import emulink                         # noqa: E402
import gdbdbg                          # noqa: E402
from build_disc import Disc            # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROWS = os.path.join(ROOT, 'work', 'source', 'text', 'rows.json')
ORIG = os.path.join(ROOT, 'work', 'source', 'disc', 'DATA')
TEXT_OPS = (0x12, 0x27, 0x28, 0x29, 0x2A, 0x2B, 0x2C)
RUN_JAL = 0x0C000000 | (0x80022314 >> 2) & 0x3FFFFFF   # jal 0x80022314 (run the block)
TICK = 0x80021CB4                      # event start / continue, called by every scene's
#                                       script tick with a0 = the VM context


def runs_block(link, ra):
    """True if the caller of 0x80021CB4 goes on to run the block (jal 0x80022314 within
    a few instructions); some battle code calls it only as a query"""
    code = struct.unpack('<8I', link.read(ra, 32))
    return RUN_JAL in code


def block_strings(d, b):
    """op-parser strings of a block, in file order"""
    _, _, strings = eex_ops.parse_block(d, b.pos, b.end)
    return sorted(strings)


def ops_for(units, whole_block, disc):
    rows = json.load(open(ROWS, encoding='utf-8'))
    first = {}
    for r in rows:
        first.setdefault(r['unit'], r)
    cache = {}
    out = bytearray()
    for u in units:
        r = first.get(u)
        if not r:
            raise SystemExit('%s: no such script unit' % u)
        name = r['file'] + '.EEX'
        if name not in cache:
            od = open(os.path.join(ORIG, name), 'rb').read()
            nd = disc.read_file('DATA/' + name)
            cache[name] = (od, eex.Script(od, name), nd, eex.Script(nd, name))
        od, os_, nd, ns = cache[name]
        ob, nb = os_.blocks[r['ev']][r['blk']], ns.blocks[r['ev']][r['blk']]
        ostr, nstr = block_strings(od, ob), block_strings(nd, nb)
        j = [a for a, _ in ostr].index(r['off'])
        picks = range(len(nstr)) if whole_block else [j]
        for i in picks:
            a, e = nstr[i]
            op = struct.unpack_from('<H', nd, a - 4)[0]
            if op not in TEXT_OPS:
                continue
            out += struct.pack('<HH', op, 5) + nd[a:e] + b'\0'
    out += b'\0\0'
    return bytes(out)


def save_pair(d, path):
    a = d.grab(0, 0, 320, 240)
    b = d.grab(0, 240, 320, 240)
    rows = []
    for y in range(240):
        rows.append(a[y * 640:(y + 1) * 640] + b[y * 640:(y + 1) * 640])
    gdbdbg.write_png(path, 640, 240, b''.join(rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('units', nargs='+')
    ap.add_argument('--block', action='store_true')
    ap.add_argument('--out', default=os.path.join(ROOT, 'work', 'ui', 'shots', 'scene'))
    ap.add_argument('--no-hotload', action='store_true')
    ap.add_argument('--bin', default=os.path.join(ROOT, 'work', 'output', 'test', 'MouriMotonari.bin'))
    ap.add_argument('--wait', type=int, default=50, help='frames before each screenshot')
    ap.add_argument('--max-pages', type=int, default=40)
    a = ap.parse_args()
    disc = Disc(a.bin, 'rb')
    ops = ops_for(a.units, a.block, disc)
    if not a.no_hotload:
        subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'hotload.py'), '--bin', a.bin],
                       check=True)
    blob = struct.pack('<H', len(ops)) + ops
    os.makedirs(a.out, exist_ok=True)
    d = gdbdbg.Dbg()
    link = emulink.Link.__new__(emulink.Link)        # share Dbg's connection
    link.g, link.bps = d.g, set()
    try:
        # halt at the script tick (main thread, just outside the VM) while the VM is idle;
        # the writes then take effect in this same tick
        d.g.cmd('Z0,%x,4' % TICK)
        for _ in range(3000):
            d.g.s.sendall(b'$c#63')
            d.g._recv_packet()
            v = d.regs()
            if v[37] == TICK and v[4] == emulink.VM_CTX and link.vm_idle() and runs_block(link, v[31]):
                break
        else:
            d.g.cmd('z0,%x,4' % TICK)
            raise SystemExit('no idle script tick within 3000 stops (an event running, or no '
                             'script in this scene?)')
        d.g.cmd('z0,%x,4' % TICK)
        st = link.vm()
        buf = emulink.VM_BUF + emulink.VM_BUF_SIZE - ((len(blob) + 15) & ~15)
        names = [link.read(x, 12).split(b'\0')[0].decode('latin1') for x in emulink.VM_NAMES]
        used = max((len(disc.read_file('DATA/' + n)) for n in names if n.endswith('.EEX')), default=0)
        if buf < st['buf'] + used:
            raise SystemExit('text too long for the free tail of the VM buffer (%d bytes)' % len(blob))
        link.write(buf, blob)
        link.write(emulink.VM_CTX + 4, struct.pack('<II', 0, buf))
        link.write(emulink.VM_CTX + 0xC, struct.pack('<H', 0))
        print('injected %d bytes of text ops at %08x (%s)' % (len(ops), buf, ' '.join(a.units)))
        tag = a.units[0] + ('_block' if a.block else '')
        started = False
        for page in range(a.max_pages):
            d.wait(a.wait)
            s = link.vm()
            if s['busy']:
                started = True
            elif started or page > 2:
                break
            path = os.path.join(a.out, '%s_%02d.png' % (tag, page))
            save_pair(d, path)
            print('shot', os.path.relpath(path, ROOT))
            d.press('circle', 2)
        if not started:
            print('warning: the block did not start (no script tick in this scene?)')
    finally:
        d.close()


if __name__ == '__main__':
    main()
