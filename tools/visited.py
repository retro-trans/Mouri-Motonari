"""Battle map: a small ticked box on every place a player unit has already visited.

Visits (villages, towns, houses, storehouses, mines, shrines, hidden treasure, forts) are
battle-script events (DATA/S_xx.EEX): a block whose condition is op 0x0E (1025 = a player
unit, x, y: the unit visits that cell) plus op 0x08 (flag F clear), and whose action sets
flag F (op 0x34) — so F stays set once the place is visited. Every location has exactly
one such flag (455 places in the 29 battles, flags < 180).

Build: each S_xx.EEX gets a header chunk (type VTYPE, n x {x, y, flag, 0}) before the
chunk list's end marker; the event offsets (absolute) move by the chunk's length. The VM
(0x80021E8C) skips unknown chunks and copies the whole script to its buffer (ctx+0x1C =
0x800C4190), so the table is in RAM while that battle runs.

Run time: 0x80010D00 (per-frame draw: GsClearOt, display list 0x80010F78, BG list
0x800112D0, GsSortClear, GsDrawOt) calls `visit_draw` instead of 0x800112D0. After the
original call, if the current script (byte 0x800F45EF: 2 * n + 1 for S_n) is a battle
script, it walks the table, and for each place whose flag is set (ctx 0x800C0BF0 + 0x3C
+ 4 * flag) and that is on screen, links 10 flat rectangles (GP0 0x60) into OT entry PRI:
above the map (entry 15: map quads, grid lines), below the units and cursor (entry 9) and
the windows (entry 2). Cell (x, y) is at (32x + X0, 24y + Y0), where (X0, Y0) is the
position of the map's top-left quad, display-list entry 1017 (0x800BE288, a GsSortSprite
entry: x +4, y +6, type +0x25 = 7), as drawn in this frame. The scroll target
0x800FEFB0 / 0x800FEFB4 (half cells: X0 = 16 - 16 SX, Y0 = 24 - 12 SY) runs a frame ahead
of the drawn map while the camera pans in the enemy phase.

    python tools/visited.py list [S_00]       visit places per battle
    python tools/visited.py preview <out.png>  the badge, 8x
Used by tools/vwf.py (patch_exe: code after the name table) and tools/build.py (chunks).
"""
import glob
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eex                              # noqa: E402
import eex_ops                          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'source', 'disc', 'DATA')
VTYPE = 0x5456                          # header chunk type ('VT')
PLAYER = 1025                           # op 0x0E first argument: a player unit
PRI = 12                                # OT entry (map 15, units / cursor 9, windows 2)

# badge, in draw order: (dx, dy, w, h, (r, g, b)) from the cell's top-left (cell 32 x 24)
CHECK = ['.......##',
         '......##.',
         '##...##..',
         '.##.##...',
         '..###....',
         '...#.....']
BX, BY, BW, BH = 19, 1, 13, 10
FRAME, BOX, TICK = (232, 224, 200), (40, 48, 64), (120, 232, 96)


def badge():
    rects = [(BX, BY, BW, BH, FRAME), (BX + 1, BY + 1, BW - 2, BH - 2, BOX)]
    for y, row in enumerate(CHECK):
        x = 0
        while x < len(row):
            if row[x] == '#':
                s = x
                while x < len(row) and row[x] == '#':
                    x += 1
                rects.append((BX + 2 + s, BY + 2 + y, x - s, 1, TICK))
            else:
                x += 1
    return rects


def _u16(d, o):
    return struct.unpack_from('<H', d, o)[0]


def _args(d, q, sig):
    out = []
    for t in sig:
        if isinstance(t, tuple):
            if _u16(d, q) != t[1]:
                return q + 2, out
            n = _u16(d, q + 2)
            out.append([_u16(d, q + 4 + 2 * i) for i in range(n)])
            q += 4 + 2 * n
            continue
        if t == 1:
            out.append(_u16(d, q))
            q += 2
            continue
        tag = _u16(d, q)
        q += 2
        if tag != t:
            out.append(None)
        elif t == 4:
            out.append(struct.unpack_from('<I', d, q)[0])
            q += 4
        elif t == 5:
            e = d.index(b'\0', q)
            out.append(d[q:e])
            q = e + 1
        else:
            out.append(_u16(d, q))
            q += 2
    return q, out


def _ops(d, q, end, depth=0):
    """top-level ops of a condition / action part: [(op, args)] (IF bodies skipped)"""
    out = []
    while q < end:
        op = _u16(d, q)
        q += 2
        if op == 0:
            break
        if op == 1:
            cop = _u16(d, q)
            q, _ = _args(d, q + 2, eex_ops.SIG[cop])
            q += 2 + _u16(d, q)
            continue
        q, a = _args(d, q, eex_ops.SIG[op])
        out.append((op, a))
    return out


def places(data):
    """battle script bytes -> sorted [(x, y, flag)] of the player visit events"""
    s = eex.Script(data)
    found = {}
    for bl in s.blocks:
        for b in bl:
            cpos, _, _ = eex_ops.parse_block(data, b.pos, b.end)
            cond = _ops(data, b.pos + 2, cpos)
            loc = [a for op, a in cond if op == 0x0E]
            if not loc or loc[0][0] != PLAYER:
                continue
            clear = {f for op, a in cond if op == 0x08 and len(a) > 1 for f in a[1]}
            sets = [a[0] for op, a in _ops(data, cpos + 2, b.end) if op == 0x34]
            flags = [f for f in sets if f in clear]
            if flags:
                key = (loc[0][1], loc[0][2])
                assert found.get(key, flags[0]) == flags[0], 'two flags for one place'
                found[key] = flags[0]
    out = sorted((x, y, f) for (x, y), f in found.items())
    assert all(x < 256 and y < 256 and f < 256 for x, y, f in out)
    return out


def add_chunk(data, entries):
    """insert the VTYPE chunk before the header's end marker; event offsets move"""
    d = bytearray(data)
    hlen = eex.header_len(d)            # just past the type-0 end marker
    end = hlen - 4
    body = b''.join(struct.pack('<4B', x, y, f, 0) for x, y, f in entries)
    chunk = struct.pack('<HH', VTYPE, len(body)) + body
    first = struct.unpack_from('<I', d, hlen)[0]
    nev = (first - hlen) // 4
    for i in range(nev):
        o = hlen + 4 * i
        struct.pack_into('<I', d, o, struct.unpack_from('<I', d, o)[0] + len(chunk))
    return bytes(d[:end] + chunk + d[end:])


def patch_scripts(files):
    """files {disc path: bytes} (built scripts) -> the 29 battle scripts with their tables"""
    out = {}
    for f in sorted(glob.glob(os.path.join(SRC, 'S_*.EEX'))):
        path = 'DATA/' + os.path.basename(f)
        orig = open(f, 'rb').read()
        out[path] = add_chunk(files.get(path, orig), places(orig))
    return out


SYMBOLS = dict(CTX=0x800C0BF0, SCRIPT_NO=0x800F45EF, MAPQ=0x800BE288, PKT=0x801436D4,
               BG_LIST=0x800112D0, VTYPE=VTYPE, PRI=PRI, NRECT=len(badge()))


def asm():
    rects = badge()
    table = '\n'.join('    .byte %d, %d, %d, %d\n    .word 0x60%02X%02X%02X' % (    # GP0 0x60 TILE, BGR
        dx, dy, w, h, c[2], c[1], c[0]) for dx, dy, w, h, c in reversed(rects))
    return r'''
; ---------------------------------------------------------------- visited places (tools/visited.py)
; 0x80010D40: jal visit_draw (was jal BG_LIST), a0 = GsOT
visit_draw:
    addiu $sp, $sp, -0x30
    sw $ra, 0x2c($sp)
    sw $s0, 0x10($sp)
    sw $s1, 0x14($sp)
    sw $s2, 0x18($sp)
    sw $s3, 0x1c($sp)
    sw $s4, 0x20($sp)
    sw $s5, 0x24($sp)
    jal BG_LIST
    move $s0, $a0
    lui $t0, %hi(SCRIPT_NO)
    lbu $t0, %lo(SCRIPT_NO)($t0)
    nop
    andi $t0, $t0, 1
    beqz $t0, @done                 ; not a battle script
    lui $t1, %hi(CTX + 0x1c)
    lw $t1, %lo(CTX + 0x1c)($t1)    ; script in the VM buffer
    nop
    addiu $t1, $t1, 6               ; header chunks: u16 type, u16 size, data
@chunk:
    lbu $t2, 0($t1)
    lbu $t3, 1($t1)
    lbu $t4, 2($t1)
    lbu $t5, 3($t1)
    sll $t3, $t3, 8
    or $t2, $t2, $t3
    sll $t5, $t5, 8
    or $t4, $t4, $t5
    beqz $t2, @done
    addiu $t1, $t1, 4
    li $t3, VTYPE
    beq $t2, $t3, @found
    nop
    b @chunk
    addu $t1, $t1, $t4
@found:
    srl $s1, $t4, 2                 ; places
    move $s2, $t1
    la $t0, MAPQ                    ; the map's top-left quad as drawn this frame
    lbu $t1, 0x25($t0)
    li $t2, 7
    bne $t1, $t2, @done             ; not a map quad
    nop
    lh $s3, 4($t0)                  ; x of cell column 0
    lh $s4, 6($t0)                  ; y of cell row 0
    lw $t0, 4($s0)                  ; OT entry PRI
    lw $t1, 8($s0)
    addiu $t0, $t0, PRI * 4
    sll $t1, $t1, 2
    subu $s0, $t0, $t1
    lui $t0, %hi(PKT)
    lw $s5, %lo(PKT)($t0)
@place:
    beqz $s1, @end
    lbu $t0, 2($s2)                 ; flag
    la $t1, CTX + 0x3c
    sll $t0, $t0, 2
    addu $t1, $t1, $t0
    lw $t0, 0($t1)
    nop
    beqz $t0, @next
    lbu $t2, 0($s2)
    lbu $t3, 1($s2)
    sll $t2, $t2, 5
    addu $t2, $t2, $s3              ; screen x
    sll $t4, $t3, 4
    sll $t3, $t3, 3
    addu $t3, $t3, $t4
    addu $t3, $t3, $s4              ; screen y
    addiu $t4, $t2, 32
    sltiu $t4, $t4, 352             ; -32 <= x < 320
    beqz $t4, @next
    addiu $t4, $t3, 24
    sltiu $t4, $t4, 264             ; -24 <= y < 240
    beqz $t4, @next
    nop
    la $t5, visit_rects
    li $t6, NRECT
@rect:
    lbu $t7, 0($t5)                 ; dx, dy, w, h, GP0 word
    lbu $t8, 1($t5)
    lbu $t9, 2($t5)
    lbu $t4, 3($t5)
    addu $t7, $t7, $t2
    addu $t8, $t8, $t3
    andi $t7, $t7, 0xffff
    sll $t8, $t8, 16
    or $t7, $t7, $t8
    sw $t7, 8($s5)                  ; xy
    sll $t4, $t4, 16
    or $t9, $t9, $t4
    sw $t9, 12($s5)                 ; wh
    lw $t7, 4($t5)
    nop
    sw $t7, 4($s5)                  ; colour + TILE
    lw $t7, 0($s0)                  ; link at the head of the OT entry
    lui $t8, 0x00ff
    ori $t8, $t8, 0xffff
    and $t9, $t7, $t8
    lui $t4, 0x0300
    or $t9, $t9, $t4
    sw $t9, 0($s5)
    and $t9, $s5, $t8
    lui $t4, 0xff00
    and $t7, $t7, $t4
    or $t7, $t7, $t9
    sw $t7, 0($s0)
    addiu $s5, $s5, 16
    addiu $t6, $t6, -1
    bnez $t6, @rect
    addiu $t5, $t5, 8
@next:
    addiu $s2, $s2, 4
    b @place
    addiu $s1, $s1, -1
@end:
    lui $t0, %hi(PKT)
    sw $s5, %lo(PKT)($t0)
@done:
    lw $ra, 0x2c($sp)
    lw $s0, 0x10($sp)
    lw $s1, 0x14($sp)
    lw $s2, 0x18($sp)
    lw $s3, 0x1c($sp)
    lw $s4, 0x20($sp)
    lw $s5, 0x24($sp)
    jr $ra
    addiu $sp, $sp, 0x30
    .align 4
; rectangles, last drawn first (each is linked at the head of the OT entry)
visit_rects:
''' + table + '\n'


def preview(path):
    from PIL import Image
    im = Image.new('RGB', (32, 24), (96, 160, 72))
    px = im.load()
    for dx, dy, w, h, c in badge():
        for y in range(h):
            for x in range(w):
                px[dx + x, dy + y] = c
    im.resize((256, 192), Image.NEAREST).save(path)


def main():
    if sys.argv[1:2] == ['preview']:
        preview(sys.argv[2])
        return
    names = sys.argv[2:] or [os.path.basename(f)[:-4] for f in sorted(glob.glob(os.path.join(SRC, 'S_*.EEX')))]
    total = 0
    for n in names:
        p = places(open(os.path.join(SRC, n + '.EEX'), 'rb').read())
        total += len(p)
        print(n, len(p), ' '.join('(%d,%d)#%d' % e for e in p))
    print('places:', total)


if __name__ == '__main__':
    main()
