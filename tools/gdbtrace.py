"""Log which of the given functions run while pressing a button (GDB).

    python tools/gdbtrace.py <button> <frames> <addr> [addr ...]
Prints the first hits per (pc, ra) with a0..a3 and 0x24 bytes at a0.
"""
import os
import socket
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gdbmem import Gdb          # noqa: E402
from gdbdbg import BTN          # noqa: E402

PAD = 0x80099428


def main():
    btn = BTN[sys.argv[1]] if sys.argv[1] != 'none' else 0
    frames = int(sys.argv[2])
    bps = [int(a, 16) for a in sys.argv[3:]]
    g = Gdb()
    g.s.settimeout(10)

    def regs():
        r = g.cmd('g')
        return [struct.unpack('<I', bytes.fromhex(r[i * 8:i * 8 + 8].replace('x', '0')))[0] for i in range(len(r) // 8)]
    for a in bps + [PAD]:
        g.cmd('Z0,%x,4' % a)
    seen = {}
    n = 0
    try:
        while n < frames:
            g.s.sendall(b'$c#63')
            g._recv_packet()
            r = regs()
            pc = r[37]
            if pc == PAD:
                n += 1
                if n <= 4 and btn:
                    g.cmd('P2=%s' % struct.pack('<I', r[2] | btn).hex())
                continue
            k = (pc, r[31])
            seen[k] = seen.get(k, 0) + 1
            if seen[k] <= 2:
                mem = g.read(r[4], 0x24) if 0x80000000 <= r[4] < 0x80200000 else b''
                print('%08x ra %08x a0 %08x a1 %08x a2 %08x a3 %08x  %s' % (pc, r[31], r[4], r[5], r[6], r[7], mem.hex()))
    except socket.timeout:
        print('timeout')
        g.s.sendall(b'\x03')
        g._recv_packet()
    finally:
        for a in bps + [PAD]:
            g.cmd('z0,%x,4' % a)
        g.close()
    for k, v in sorted(seen.items()):
        print('%08x <- %08x x%d' % (k[0], k[1], v))


if __name__ == '__main__':
    main()
