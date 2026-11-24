"""Shared helpers for driving the running game over DuckStation's GDB server
(tools/gdbmem.py): register reads, a safe halt for writing code / data into RAM,
input injection and the script VM context.

Safe halt: the pad read at the end of PadRead (0x80099428) runs in the VSync
interrupt every frame, so a breakpoint there always hits, without pressing any
button. The interrupted main thread is described by the BIOS thread control block
(pointer [[0x80000108]]): registers at +0x08, EPC at +0x88. A halt is safe for
rewriting the VWF kernel code when neither the main thread (EPC, RA, the words on
its stack) nor the interrupt stack holds an address inside that code; otherwise
the next frame is tried.
"""
import os
import socket
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gdbmem import Gdb                 # noqa: E402

PAD = 0x80099428                       # end of PadRead (v0 = buttons, active high)
BTN = {'l2': 0x1, 'r2': 0x2, 'l1': 0x4, 'r1': 0x8, 'triangle': 0x10, 'circle': 0x20,
       'cross': 0x40, 'square': 0x80, 'select': 0x100, 'start': 0x800,
       'up': 0x1000, 'right': 0x2000, 'down': 0x4000, 'left': 0x8000}
KCODE = ((0x8000EB80, 0x80010000),     # VWF kernel code (tools/vwf.py CODE_ADDR..)
         (0x8000D980, 0x8000DF00))     # and CODE2 (atlas homes, upload; 0.2.17)

# script VM (MAIN.EXE 0x80021E8C init, 0x80021CB4 event start, 0x80022314 block run)
VM_CTX = 0x800C0BF0                    # +0 event, +4 pos, +8 read ptr, +0xC start marker
#                                       (0xFFFF = none), +0x10 resume ordinal (-1 none),
#                                       +0x1C buffer, +0x20 block count, +0x24 enabled,
#                                       +0x28 busy, +0x2C header length
VM_BUF = 0x800C4190                    # script copy, 0x18000 bytes
VM_BUF_SIZE = 0x18000
VM_NAMES = (0x800C4010, 0x800C401C)    # "R_xx.EEX" / "S_xx.EEX" name templates
FAT = 0x800AB36C                       # FAT_DATA.BIN in RAM (245 x 24 bytes)


def phys(a):
    return 0x80000000 | (a & 0x1FFFFF)


class Link:
    def __init__(self, timeout=20):
        self.g = Gdb()
        self.g.s.settimeout(timeout)
        self.bps = set()

    # ---------------------------------------------------------------- basics
    def regs(self):
        r = self.g.cmd('g')
        return [struct.unpack('<I', bytes.fromhex(r[i * 8:i * 8 + 8].replace('x', '0')))[0]
                for i in range(len(r) // 8)]

    def read(self, a, n):
        return self.g.read(a, n)

    def write(self, a, data):
        self.g.write(a, data)

    def u32(self, a):
        return struct.unpack('<I', self.read(a, 4))[0]

    def bp(self, a, on=True):
        if on and a not in self.bps:
            self.g.cmd('Z0,%x,4' % a)
            self.bps.add(a)
        elif not on and a in self.bps:
            self.g.cmd('z0,%x,4' % a)
            self.bps.discard(a)

    def cont(self):
        """continue until the next breakpoint; returns the registers"""
        self.g.s.sendall(b'$c#63')
        self.g._recv_packet()
        return self.regs()

    def close(self):
        for a in list(self.bps):
            self.bp(a, False)
        self.g.close()

    # ---------------------------------------------------------------- frames / input
    def frames(self, n, press=None, hold=4):
        """let n pad reads pass; press: button name(s) 'a+b' held for the first `hold`"""
        mask = 0
        for b in (press or '').split('+'):
            if b:
                mask |= BTN[b]
        self.bp(PAD)
        for i in range(n):
            v = self.cont()
            while v[37] != PAD:
                v = self.cont()
            if mask and i < hold:
                self.g.cmd('P2=%s' % struct.pack('<I', v[2] | mask).hex())

    # ---------------------------------------------------------------- safe halt
    def main_thread(self):
        pcb = self.u32(0x80000108)
        tcb = self.u32(pcb)
        t = self.read(tcb, 0x98)
        r = struct.unpack('<32I', t[8:0x88])
        return {'epc': struct.unpack_from('<I', t, 0x88)[0], 'ra': r[31], 'sp': r[29]}

    def _stack_has(self, sp, lo, hi, n=0x400):
        sp = phys(sp)
        n = min(n, 0x80200000 - sp)
        if n <= 0:
            return False
        d = self.read(sp, n)
        return any(lo <= w < hi for w in struct.unpack('<%dI' % (n // 4), d[:n - n % 4]))

    def safe_halt(self, avoid=KCODE, tries=600):
        """halt at the VSync pad read with no frame of `avoid` live in either thread"""
        self.bp(PAD)
        ranges = [avoid] if isinstance(avoid[0], int) else list(avoid)
        why = 'no pad read'
        for _ in range(tries):
            v = self.cont()
            if v[37] != PAD:
                continue
            m = self.main_thread()
            bad = None
            for lo, hi in ranges:
                if lo <= m['epc'] < hi or lo <= m['ra'] < hi:
                    bad = 'main thread at %08x / ra %08x' % (m['epc'], m['ra'])
                elif self._stack_has(m['sp'], lo, hi):
                    bad = 'main thread stack (sp %08x) holds a return into %08x..%08x' % (m['sp'], lo, hi)
                elif self._stack_has(v[29], lo, hi, 0x200):
                    bad = 'interrupt stack holds a return into %08x..%08x' % (lo, hi)
                if bad:
                    break
            if bad:
                why = bad
                continue
            return v
        raise RuntimeError('no safe halt point within %d frames (last: %s); try again in '
                           'another moment of the game' % (tries, why))

    # ---------------------------------------------------------------- script VM
    def vm(self):
        w = struct.unpack('<12I', self.read(VM_CTX, 0x30))
        return {'event': w[0], 'pos': w[1], 'ptr': w[2], 'start': w[3] & 0xFFFF,
                'resume': w[4] if w[4] < 0x80000000 else w[4] - (1 << 32),
                'buf': w[7], 'blocks': w[8], 'enabled': w[9], 'busy': w[10], 'hlen': w[11]}

    def vm_idle(self):
        s = self.vm()
        return s['start'] == 0xFFFF and s['busy'] == 0 and s['resume'] < 0 and s['enabled']


def wait_ok(fn, *a, **k):
    try:
        return fn(*a, **k)
    except socket.timeout:
        raise RuntimeError('the emulator did not answer (is DuckStation running with the GDB server?)')
