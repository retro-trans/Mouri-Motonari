"""EEX event script (DATA/R_xx.EEX, DATA/S_xx.EEX) parser / rebuilder.

Layout (MAIN.EXE VM at 0x80021E8C init, 0x800220B0 step):
  0x00  "EEX\\0", u8 1, u8 2, then (u16 type, u16 size, data) chunks ended by type 0
        (the VM keeps type 1 and skips others; built S_xx.EEX add type 0x5456, the
        visited-place table of tools/visited.py)
  hdr   u32 event offsets (absolute; the first one gives the table length)
  event u16 count, then count blocks:
          u16 size                     (bytes after this field)
          condition ops ... op 0000    (status 3 ends the condition)
          u16 size2                    (action part, skipped when the condition fails)
          action ops                   (op 0000 ends)
  op    u16 opcode + tagged args: u16 tag, then u32 (tag 4), NUL-terminated
        Shift-JIS string (tag 5) or u16 (any other tag). Raw u16 for reader type 1.
        Per-op signatures: tools/eex_ops.py.
  IF    op 0001, a condition op, u16 body length, body ending with op 0000 (nested;
        the VM skips the body by its length when the condition fails)

Strings only grow/shrink inside action parts, so a rebuild has to fix the event
offsets, the block size, size2 and the length of every IF around a changed string.
size2 and the IFs come from the op parser (tools/eex_ops.py); the old size2 search
(find_size2) is kept only as a cross-check, it picks a wrong u16 in 20 blocks.

    python tools/eex.py check            parse every EEX, report problems
"""
import glob
import os
import struct
import sys

SRC = 'work/source/disc/DATA'


def u16(d, o):
    return struct.unpack_from('<H', d, o)[0]


def u32(d, o):
    return struct.unpack_from('<I', d, o)[0]


def header_len(d):
    assert d[:4] == b'EEX\0', 'bad magic'
    o = 6
    while True:
        t, s = u16(d, o), u16(d, o + 2)
        o += 4
        if t == 0:
            return o
        o += s


def is_text_byte_run(d, o):
    """d[o:] is a printable SJIS/ASCII run ended by NUL; returns end (NUL pos) or None."""
    i = o
    n = len(d)
    while i < n:
        c = d[i]
        if c == 0:
            return i if i > o else None
        if 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC:
            if i + 1 >= n or not (0x40 <= d[i + 1] <= 0xFC and d[i + 1] != 0x7F):
                return None
            i += 2
        elif c in (0x0A, 0x0D) or 0x20 <= c <= 0x7E or 0xA0 <= c <= 0xDF or c == 0x1B:
            i += 1
        else:
            return None
    return None


class Block:
    def __init__(self, pos, size, cpos, size2):
        self.pos = pos        # offset of the u16 size field
        self.size = size
        self.cpos = cpos      # offset of the u16 size2 field
        self.size2 = size2
        self.strings = []     # (offset of first text byte, end = NUL offset); extraction list
        self.op_strings = set()   # string arguments found by the op parser
        self.ifs = []         # (offset of the IF length field, body start, body end)

    @property
    def end(self):
        return self.pos + 2 + self.size


class Script:
    def __init__(self, data, name=''):
        self.name = name
        self.d = bytes(data)
        d = self.d
        self.hlen = header_len(d)
        first = u32(d, self.hlen)
        self.nev = (first - self.hlen) // 4
        self.events = [u32(d, self.hlen + 4 * i) for i in range(self.nev)]
        self.blocks = []      # list per event
        self.problems = []
        bounds = self.events[1:] + [len(d)]
        for ev, (start, stop) in enumerate(zip(self.events, bounds)):
            cnt = u16(d, start)
            o = start + 2
            bl = []
            for k in range(cnt):
                size = u16(d, o)
                end = o + 2 + size
                import eex_ops
                try:
                    cpos, ifs, op_strings = eex_ops.parse_block(d, o, end)
                except eex_ops.ParseError as e:
                    self.problems.append('ev%d blk%d @%x: %s' % (ev, k, o, e))
                    bl.append(Block(o, size, None, None))
                else:
                    b = Block(o, size, cpos, u16(d, cpos))
                    b.ifs = ifs
                    b.op_strings = set(op_strings)
                    # extraction keeps the old string search (unit keys depend on it);
                    # its few false hits inside flag lists are never replaced
                    old = self.find_size2(o + 2, end)
                    b.strings = self.find_strings(old if old is not None else cpos, end)
                    bl.append(b)
                o = end
            # tail padding up to the next event must be zero bytes
            if o > stop or any(d[o:stop]):
                self.problems.append('ev%d: blocks end %x, next event %x' % (ev, o, stop))
            self.blocks.append(bl)

    def find_size2(self, a, end):
        hits = []
        for q in range(a + 2, end - 1):
            if u16(self.d, q) == end - (q + 2) and u16(self.d, q - 2) == 0:
                hits.append(q)
        if not hits:
            return None
        return hits[0]

    def find_strings(self, a, end):
        out = []
        d = self.d
        q = a
        while q < end - 2:
            if d[q] == 5 and d[q + 1] == 0:
                e = is_text_byte_run(d, q + 2)
                if e is not None and e < end and self.has_jp_or_text(q + 2, e):
                    out.append((q + 2, e))
                    q = e + 1
                    continue
            q += 1
        return out

    def has_jp_or_text(self, a, e):
        s = self.d[a:e]
        return any(c >= 0x81 for c in s) or len(s) >= 2

    def all_strings(self):
        for ev, bl in enumerate(self.blocks):
            for k, b in enumerate(bl):
                for (a, e) in b.strings:
                    yield ev, k, a, self.d[a:e]

    def rebuild(self, repl):
        """repl: {offset of first text byte: new bytes (no NUL)} -> new file bytes.
        Fixes the event offsets, block sizes, size2 and every IF length."""
        d = self.d
        out = bytearray(d[:self.hlen + 4 * self.nev])
        new_events = []
        bounds = self.events[1:] + [len(d)]
        used = set()
        for ev, (start, stop) in enumerate(zip(self.events, bounds)):
            new_events.append(len(out))
            out += d[start:start + 2]
            for b in self.blocks[ev]:
                if b.cpos is None:
                    raise ValueError('%s ev%d: block at %x does not parse' % (self.name, ev, b.pos))
                body = bytearray()
                cur = b.pos + 2
                shifts = []           # (end of a replaced string, growth)
                for (a, e) in b.strings:
                    if a in repl:
                        if (a, e) not in b.op_strings:
                            raise ValueError('%s: %x is not a string argument' % (self.name, a))
                        body += d[cur:a] + repl[a]
                        shifts.append((e, len(repl[a]) - (e - a)))
                        cur = e
                        used.add(a)
                body += d[cur:b.end]
                base = b.pos + 2

                def new(x):
                    """body offset of original offset x (x outside replaced strings)"""
                    return x - base + sum(g for e, g in shifts if e <= x)

                for at, s0, s1 in [(b.cpos, b.cpos + 2, b.end)] + b.ifs:
                    n = new(s1) - new(s0)
                    assert 0 <= n < 0x10000, 'length out of range'
                    struct.pack_into('<H', body, new(at), n)
                assert len(body) < 0x10000, 'block too large'
                out += struct.pack('<H', len(body)) + body
            pad = stop - (self.blocks[ev][-1].end if self.blocks[ev] else start + 2)
            out += b'\0' * pad
        for i, v in enumerate(new_events):
            struct.pack_into('<I', out, self.hlen + 4 * i, v)
        missing = set(repl) - used
        if missing:
            raise ValueError('%s: replacements outside any string: %s' % (
                self.name, ', '.join('%x' % a for a in sorted(missing))))
        return bytes(out)


def files():
    return sorted(glob.glob(os.path.join(SRC, 'R_*.EEX')) + glob.glob(os.path.join(SRC, 'S_*.EEX')))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'check'
    if cmd == 'check':
        tot = 0
        chars = 0
        for f in files():
            s = Script(open(f, 'rb').read(), os.path.basename(f))
            n = 0
            for ev, k, a, t in s.all_strings():
                n += 1
                chars += len(t)
            tot += n
            same = s.rebuild({}) == s.d
            print('%-10s events %3d blocks %4d strings %5d problems %d rebuild %s' % (
                s.name, s.nev, sum(len(b) for b in s.blocks), n, len(s.problems), 'ok' if same else 'DIFF'))
            for p in s.problems[:5]:
                print('   ', p)
        print('total strings', tot, 'bytes', chars)


if __name__ == '__main__':
    main()
