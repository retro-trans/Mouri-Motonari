"""Play any film in the running game: on the title menu (NEW GAME / CONTINUE shown, Continue
highlighted) this presses Left + Circle, and when New Game asks for MOVIE01 it plays MOVIEnn
instead (sprintf(buf, "MOVIE%02d.STR", n) at 0x800149CC, a2 = n).

    python tools/play_movie.py 5      then capture with  tools/emu.ps1 grab out.png

gdbdbg screenshots wait for a pad read, which films do not do; use the window grab.
"""
import struct
import sys
import time

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import emulink  # noqa

target = int(sys.argv[1])
SPR = 0x800149CC                 # jal sprintf(buf, "MOVIE%02d.STR", n): a2 = n
L = emulink.Link(timeout=60)
L.g.s.sendall(b'\x03')
time.sleep(0.3)
L.regs()
L.bp(SPR)
L.bp(emulink.PAD)
n = 0
while True:
    v = L.cont()
    if v[37] == SPR:
        print('movie', v[6])
        if v[6] == 1:
            L.g.cmd('P6=%s' % struct.pack('<I', target).hex())
            print('-> movie', target)
            break
        continue
    n += 1
    btn = {5: 'left', 6: 'left', 7: 'left', 40: 'circle', 41: 'circle', 42: 'circle',
           120: 'circle', 121: 'circle', 200: 'circle', 201: 'circle'}.get(n)
    if btn:
        L.g.cmd('P2=%s' % struct.pack('<I', v[2] | emulink.BTN[btn]).hex())
    if n > 3000:
        raise SystemExit('no New Game film')
L.close()
