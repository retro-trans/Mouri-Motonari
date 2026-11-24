"""Remove stale breakpoints left by an interrupted gdbdbg run and resume the CPU.

    python tools/gdbreset.py [addr ...]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gdbmem import Gdb      # noqa: E402

DEFAULT = [0x80099428, 0x800A54C8, 0x8000E210]

g = Gdb()
for a in [int(x, 16) for x in sys.argv[1:]] or DEFAULT:
    g.cmd('z0,%x,4' % a)
g.close()
print('resumed')
