"""EEX op parser: walks condition / action parts op by op (see tools/eex.py).

    python tools/eex_ops.py              parse every script, report blocks that do not parse

Op signatures come from the VM (MAIN.EXE): the dispatcher 0x80020254 reads a u16 op
(< 0x4F) and jumps through the table at 0x8011B094 to one handler per op; each handler
reads its arguments with 0x800212D4(ctx, type): type 1 = raw u16; any other type reads
a u16 tag first and, if the tag equals the type, the value (type 4: u32, type 5:
NUL-terminated string, else u16); a different tag is consumed alone.

Op 1 (IF): the next op is the condition, then a raw u16 body length; the VM skips the
body by that length when the condition fails, otherwise runs it up to its op 0. Op 0
ends a block / IF body. Op 8 (flag test) reads two flag lists: tag 0x35, u16 count,
count raw u16.
"""
import struct
import sys

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import eex                            # noqa: E402

LIST = ('cnt', 53)                    # tag 0x35 + count + count raw u16


def REP(n, sig):
    """n records of sig"""
    return list(sig) * n


def CNT(tag):
    """tag + u16 count, then count raw u16 (a different tag: only the tag is read)"""
    return ('cnt', tag)

SIG = {
    0x00: [], 0x01: [], 0x02: [],
    0x03: [2, 35, 4, 36], 0x04: [3, 4, 36], 0x05: [4, 36], 0x06: [37], 0x07: [38],
    0x08: [LIST, LIST], 0x09: [40, 4, 36], 0x0A: [28, 12], 0x0B: [2], 0x0C: [2, 2],
    0x0D: [12], 0x0E: [2, 4, 4], 0x0F: [], 0x10: [], 0x11: [2, 4, 4, 4, 4],
    0x12: [5], 0x13: [4], 0x14: [], 0x15: [2, 2, 35], 0x16: [2, 35, 52, 4],
    0x17: [5], 0x18: [27], 0x19: [4, 4, 4, 4, 41],
    0x1C: [38, 38, 4, 50, 2, 50, 2] + REP(30, [2, 38, 38, 38, 4, 4, 43, 51, 23]),
    0x1D: [38] + REP(60, [2, 4, 4, 43, 51, 38, 38, 7, 2, 4, 4, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 23]),
    0x1E: [4, 4, 11], 0x1F: [2, 4, 4, 43, 13], 0x20: [44, 2, 4, 4, 4, 4, 3],
    0x21: [2, 4, 4, 43], 0x22: [2, 13, 43], 0x23: [2, 13], 0x24: [2, 19],
    0x25: [45, 12, 26, 28, 4, 4, 43], 0x26: [], 0x27: [5], 0x28: [5], 0x29: [5],
    0x2A: [5], 0x2B: [5], 0x2C: [5], 0x2D: [45, 12, 26, 28, 21],
    0x2E: [45, 12, 26, 28, 4, 4], 0x2F: [], 0x30: [], 0x31: [4, 4, 16], 0x32: [],
    0x33: [4, 4], 0x34: [4, 39], 0x35: [CNT(12), 38], 0x36: [46], 0x37: [54], 0x38: [],
    0x39: [], 0x3A: [23], 0x3B: [2, 7, 2, 4, 4], 0x3C: [2, 14], 0x3D: [40, 52, 4],
    0x3E: [2, 4], 0x3F: [2, 3], 0x40: [34], 0x41: [2],
    0x42: [44, 2, 4, 4, 4, 4, 3, 47, 24, 4, 48], 0x43: [],
    0x44: [44, 2, 4, 4, 4, 4, 3], 0x45: [], 0x46: [30, 4], 0x47: [9], 0x48: [],
    0x49: [18], 0x4A: [49], 0x4B: [2], 0x4C: [], 0x4E: [4],
}


class ParseError(Exception):
    pass


def u16(d, o):
    return struct.unpack_from('<H', d, o)[0]


def read_args(d, q, end, sig, strings):
    for t in sig:
        if q + 2 > end:
            raise ParseError('args past end at %x' % q)
        if isinstance(t, tuple):
            if u16(d, q) != t[1]:
                q += 2
                if t == LIST:
                    raise ParseError('list tag at %x' % (q - 2))
                return q               # the handler stops after a missing count
            q += 4 + 2 * u16(d, q + 2)
            continue
        if t == 1:
            q += 2
            continue
        tag = u16(d, q)
        q += 2
        if tag != t:
            continue
        if t == 4:
            q += 4
        elif t == 5:
            e = d.index(b'\0', q)
            strings.append((q, e))
            q = e + 1
        else:
            q += 2
    return q


def parse_ops(d, q, end, ifs, strings, until_end_op=True):
    """Parse ops from q; returns position after the op 0 that ends this level
    (or end when the part runs to the block end). ifs gets (len pos, body start, body end)."""
    while q < end:
        op = u16(d, q)
        if op not in SIG:
            raise ParseError('unknown op %#x at %x' % (op, q))
        q += 2
        if op == 0:
            return q
        if op == 1:
            cop = u16(d, q)
            if cop not in SIG or cop in (0, 1):
                raise ParseError('bad IF condition %#x at %x' % (cop, q))
            q = read_args(d, q + 2, end, SIG[cop], strings)
            size = u16(d, q)
            body = q + 2
            bend = body + size
            if bend > end:
                raise ParseError('IF body past end at %x' % q)
            after = parse_ops(d, body, bend, ifs, strings)
            if after != bend:
                raise ParseError('IF body at %x ends at %x, length says %x' % (body, after, bend))
            ifs.append((q, body, bend))
            q = bend
            continue
        q = read_args(d, q, end, SIG[op], strings)
    if until_end_op and q != end:
        raise ParseError('ran past end')
    return q


def parse_block(d, pos, end):
    """Block at pos (its u16 size field) ending at end -> (cpos, ifs, strings):
    cpos = offset of size2 (the condition part ends with op 0); raises ParseError."""
    ifs, strings = [], []
    cpos = parse_ops(d, pos + 2, end, [], [])            # condition part ends with op 0
    if cpos + 2 > end or cpos + 2 + u16(d, cpos) != end:
        raise ParseError('size2 at %x does not reach the block end %x' % (cpos, end))
    q = parse_ops(d, cpos + 2, end, ifs, strings, until_end_op=False)
    if q != end:
        raise ParseError('action ends at %x, block end %x' % (q, end))
    return cpos, ifs, strings


def main():
    tot = bad = nifs = 0
    wrong_size2 = []
    from collections import Counter
    why = Counter()
    for f in eex.files():
        d = open(f, 'rb').read()
        s = eex.Script(d, f)
        for ev, bl in enumerate(s.blocks):
            for k, b in enumerate(bl):
                tot += 1
                try:
                    cpos, ifs, strings = parse_block(d, b.pos, b.end)
                    nifs += len(ifs)
                    old = s.find_size2(b.pos + 2, b.end)
                    if cpos != old:
                        wrong_size2.append((f[-8:], ev, k, old, cpos, len(strings)))
                    extra = [x for x in b.strings if x not in strings]
                    if any(e - a > 1 for a, e in extra) or [x for x in strings if x not in b.strings]:
                        raise ParseError('strings differ: %d vs %d' % (len(strings), len(b.strings)))
                except ParseError as e:
                    bad += 1
                    msg = str(e)
                    why[msg.split(' at ')[0]] += 1
                    if bad <= 15:
                        print(f[-8:], ev, k, msg)
    print('blocks %d, failed %d, IFs %d' % (tot, bad, nifs))
    print('eex.py size2 search wrong in %d blocks:' % len(wrong_size2),
          ', '.join('%s ev%d blk%d' % w[:3] for w in wrong_size2))
    print(why.most_common(10))


if __name__ == '__main__':
    main()
