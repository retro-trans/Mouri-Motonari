"""Minimal VCDIFF (RFC 3284, the xdelta3 patch format) encoder and decoder.

    python tools/vcdiff.py make  <source> <target> <patch>
    python tools/vcdiff.py apply <source> <patch> <target>

The encoder is tuned for raw 2352-byte CD images: each target sector is copied from the
same offset of the source when identical; otherwise from any source sector with the same
subheader + user data (Mode 2 Form 1 EDC/ECC do not depend on the sector address, so a
moved sector only differs in its 4-byte header); otherwise added literally. It writes plain
VCDIFF (no secondary compression, default code table, VCD_SOURCE windows that cover the
whole source file), so `xdelta3 -d -s <source> <patch> <target>` can apply it too.
"""
import hashlib
import sys

SECTOR = 2352
WIN_SECTORS = 4096                  # 9.6 MB target windows (xdelta3 limit is 16 MB)
MAGIC = b'\xd6\xc3\xc4\x00'
VCD_SOURCE = 0x01


def varint(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append(0x80 | (n & 0x7F))
        n >>= 7
    return bytes(reversed(out))


def read_varint(b, p):
    n = 0
    while True:
        c = b[p]
        p += 1
        n = (n << 7) | (c & 0x7F)
        if not c & 0x80:
            return n, p


# ---------------------------------------------------------------- default code table
def code_table():
    t = [((0, 0, 0), (0, 0, 0))] * 256     # (type, size, mode); type 0 noop, 1 add, 2 run, 3 copy
    t = list(t)
    t[0] = ((2, 0, 0), (0, 0, 0))
    i = 1
    for s in range(18):
        t[i] = ((1, s, 0), (0, 0, 0))
        i += 1
    for m in range(9):
        t[i] = ((3, 0, m), (0, 0, 0))
        i += 1
        for s in range(4, 19):
            t[i] = ((3, s, m), (0, 0, 0))
            i += 1
    for m in range(6):
        for a in range(1, 5):
            for c in range(4, 7):
                t[i] = ((1, a, 0), (3, c, m))
                i += 1
    for m in range(6, 9):
        for a in range(1, 5):
            t[i] = ((1, a, 0), (3, 4, m))
            i += 1
    for m in range(9):
        t[i] = ((3, 4, m), (1, 1, 0))
        i += 1
    assert i == 256
    return t


TABLE = code_table()
ADD0 = 1            # ADD, size in the instruction stream
COPY0_SELF = 19     # COPY mode 0 (VCD_SELF), size in the instruction stream


# ---------------------------------------------------------------- encoder
def _window(ops, srclen):
    """ops: [('copy', addr, n) | ('add', bytes)] -> delta encoding of one window."""
    data, inst, addr = bytearray(), bytearray(), bytearray()
    tlen = 0
    for op in ops:
        if op[0] == 'add':
            inst.append(ADD0)
            inst += varint(len(op[1]))
            data += op[1]
            tlen += len(op[1])
        else:
            inst.append(COPY0_SELF)
            inst += varint(op[2])
            addr += varint(op[1])
            tlen += op[2]
    body = varint(tlen) + b'\x00' + varint(len(data)) + varint(len(inst)) + varint(len(addr))
    body += bytes(data) + bytes(inst) + bytes(addr)
    return bytes([VCD_SOURCE]) + varint(srclen) + varint(0) + varint(len(body)) + body


def make(src, tgt):
    index = {}
    for o in range(0, len(src) - SECTOR + 1, SECTOR):
        index.setdefault(hashlib.blake2b(src[o + 16:o + SECTOR], digest_size=16).digest(), o)
    out = bytearray(MAGIC + b'\x00')
    pos = 0
    while pos < len(tgt):
        end = min(len(tgt), pos + WIN_SECTORS * SECTOR)
        ops = []

        def copy(a, n):
            if ops and ops[-1][0] == 'copy' and ops[-1][1] + ops[-1][2] == a:
                ops[-1] = ('copy', ops[-1][1], ops[-1][2] + n)
            else:
                ops.append(('copy', a, n))

        def add(b):
            if ops and ops[-1][0] == 'add':
                ops[-1] = ('add', ops[-1][1] + b)
            else:
                ops.append(('add', bytes(b)))
        o = pos
        while o < end:
            n = min(SECTOR, end - o)
            t = tgt[o:o + n]
            if o + n <= len(src) and src[o:o + n] == t:
                copy(o, n)
            elif n == SECTOR:
                s = index.get(hashlib.blake2b(t[16:], digest_size=16).digest())
                if s is not None and src[s + 16:s + SECTOR] == t[16:]:
                    if src[s:s + 12] == t[:12]:
                        copy(s, 12)
                    else:
                        add(t[:12])
                    add(t[12:16])
                    copy(s + 16, SECTOR - 16)
                else:
                    add(t)
            else:
                add(t)
            o += n
        out += _window(ops, len(src))
        pos = end
    return bytes(out)


# ---------------------------------------------------------------- decoder
def apply(src, patch, fout):
    """Writes the target to the open file fout (windows are streamed: 32-bit Python safe)."""
    if patch[:4] != MAGIC:
        raise ValueError('not a VCDIFF file')
    hdr = patch[4]
    p = 5
    if hdr & 0x01:
        raise ValueError('secondary compression is not supported')
    if hdr & 0x02:
        raise ValueError('custom code tables are not supported')
    if hdr & 0x04:                       # application data
        n, p = read_varint(patch, p)
        p += n
    total = 0
    while p < len(patch):
        wi = patch[p]
        p += 1
        seg = b''
        if wi & 0x03:
            sl, p = read_varint(patch, p)
            sp, p = read_varint(patch, p)
            if not wi & 0x01:
                raise ValueError('VCD_TARGET windows are not supported')
            seg = memoryview(src)[sp:sp + sl]
        dlen, p = read_varint(patch, p)
        q = p
        p += dlen
        tlen, q = read_varint(patch, q)
        di = patch[q]
        q += 1
        if di:
            raise ValueError('compressed sections are not supported')
        ld, q = read_varint(patch, q)
        li, q = read_varint(patch, q)
        la, q = read_varint(patch, q)
        if wi & 0x04:                    # xdelta3 adler32 extension
            q += 4
        data = patch[q:q + ld]
        inst = patch[q + ld:q + ld + li]
        addr = patch[q + ld + li:q + ld + li + la]
        dp = ip = ap = 0
        near = [0] * 4
        nxt = 0
        same = [0] * (3 * 256)
        win = bytearray()
        S = len(seg)
        while ip < len(inst):
            code = inst[ip]
            ip += 1
            for typ, size, mode in TABLE[code]:
                if typ == 0:
                    continue
                if size == 0:
                    size, ip = read_varint(inst, ip)
                if typ == 1:
                    win += data[dp:dp + size]
                    dp += size
                elif typ == 2:
                    win += data[dp:dp + 1] * size
                    dp += 1
                else:
                    here = S + len(win)
                    if mode == 0:
                        a, ap = read_varint(addr, ap)
                    elif mode == 1:
                        a, ap = read_varint(addr, ap)
                        a = here - a
                    elif mode < 6:
                        a, ap = read_varint(addr, ap)
                        a += near[mode - 2]
                    else:
                        a = same[(mode - 6) * 256 + addr[ap]]
                        ap += 1
                    near[nxt] = a
                    nxt = (nxt + 1) % 4
                    same[a % (3 * 256)] = a
                    if a + size <= S:
                        win += seg[a:a + size]
                    else:
                        for k in range(size):     # may overlap the bytes being produced
                            x = a + k
                            win.append(seg[x] if x < S else win[x - S])
        if len(win) != tlen:
            raise ValueError('window length mismatch')
        fout.write(win)
        total += len(win)
    return total


if __name__ == '__main__':
    cmd, a, b, c = sys.argv[1:5]
    if cmd == 'make':
        d = make(open(a, 'rb').read(), open(b, 'rb').read())
    else:
        with open(c, 'wb') as f:
            n = apply(open(a, 'rb').read(), open(b, 'rb').read(), f)
        print(c, n)
        sys.exit(0)
    open(c, 'wb').write(d)
    print(c, len(d))
