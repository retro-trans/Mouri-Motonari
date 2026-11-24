"""VWF + 2x-density ("4x") text font for MAIN.EXE — see docs/VWF.md.

How the game draws text: put-char 0x8001AB40 renders 12x12 / 16x16 1bpp KFONT
glyphs into a 320x240 4bpp RAM canvas (0x8019A000) with the blitter 0x8001031C;
the canvas is uploaded to VRAM (384,0) and shown by two GsSPRITEs (tpage 6/7,
CLUT 320,240) through GsSortFastSprite 0x800A2D0C, only when the screen changes.

Hooks:
  0x8001AE90 jal -> vwf_draw   ASCII 0x20-0x7F: hidden 1x underlay in the canvas
                                (pixels fully inked at 2x, plus one marker pixel),
                                a glyph record (x, y, code, colour), advance fixed
                                to the glyph's width; other codes -> original.
  0x800A2D0C GsSortFastSprite  canvas sprites: before the sprite, one POLY_FT4 per
           -> s_hook            live record inside its rect, texture = the Skies
                                glyph at 2x density from the atlas (home P 960,72 or
                                S 576,98, see HOMES), CLUT = 2-colour copy of canvas
                                colour c (x+16(c&3), y+88+c/4). A record is live while the canvas still
                                holds its exact underlay (survives window save /
                                restore); validity (one bit per record) is computed
                                when the canvas is uploaded, not in the sort, which
                                often runs in the VSync interrupt.
  LoadImage / MoveImage / ClearImage entries: a game write over the atlas or
                                CLUT area marks it dirty -> re-uploaded on next draw;
                                a LoadImage over the canvas recomputes record validity.
Code lives in kernel RAM (CODE_ADDR), the font at FONT_ADDR, records at RECS;
an appended entry stub copies them there before crt0 runs.

    python tools/vwf.py <in MAIN.EXE> <out MAIN.EXE>
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from masm import assemble      # noqa: E402

from PIL import Image          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIES = os.path.join(ROOT, 'work', 'source', 'skies_font.png')

ORIG_ENTRY = 0x800AB1CC
ORIG_TSIZE = 0x115800
STUB_ADDR = 0x80010000 + ORIG_TSIZE
# Memory: records and font live at the bottom of the game's stack area (STACK = 801fff00
# in SYSTEM.CNF; the game never went below 0x801FEC00 in 15 RAM samples: castle, town,
# battle, save prompt, intro and opening films), not in kernel RAM 0x8000B000-0x8000BF00,
# which some BIOS versions use (SCPH-1001 keeps the boot path and the memory card directory
# there: the records over it crashed the game at boot, fixed in 0.2.11). Code and upload
# strip stay in the kernel heap 0x8000E600-0x80010000, past the TCBs / EvCBs this game's
# SYSTEM.CNF makes every BIOS allocate from 0xA000E000.
# 0x801F8000-0x801FB000 is the battle-animation overlay (OVL/BA_OVL.BIN, 0x3000 bytes read
# by 0x80086340): the records and font were there in 0.2.11-0.2.12 and the overlay wiped them
# (the training duel and battle attacks crashed in revalidate). The stack reached 0x801FE850.
RECS = 0x8000C000              # 512 records x 8 bytes; kernel RAM, unused by the BIOS (0.2.13)
NRECS = 512
FONT_ADDR = 0x801FB000         # 96 x 4 metrics + 96 x 48 rows, then the UI string pool
FONT_END = FONT_ADDR + 0x1800
SAVE_ADDR = FONT_END - 0x140   # save-list line code (SAVE_ASM), end of the copied block
DESC_BUF = FONT_END            # 128-byte save-list line buffer (overwritten by the boot copy, unused then)
NAMES_ADDR = FONT_END + 0x80   # full-name hook + table (NAMES_ASM), copied with the font
NAMES_END = 0x801FE000         # 2 KB below the deepest stack seen (0x801FE850)
NUM_END = 30                   # workshop bonus column: value ends at x 128 + 30
PROF_LINE = 48                 # profile screen: bytes per line (game: 24)
PROF_BUFLEN = 0x9D0            # profile text buffer sp+0x20 .. sp+0x9F0 of 0x8008158C
CODE_ADDR = 0x8000EB80         # up to 0x80010000 (0x8000EF00 until 0.2.16)
STRIP = 0x8000E600             # upload buffer: 1408 bytes (64 x 11 halfwords; 0.2.16: 2304)
STRIP_END = 0x8000EB80
# VRAM x 960..1023 (texture page 15), y 48..255: empty in every scene dumped (101 VRAM
# dumps: castle, town, menus, profiles, Ep. 1 map battle, battle animation, duel, title,
# movies), but inside the picture of battle maps 41+ tiles wide (see HOMES below);
# the game's effect sheet (CHR_MARK.E3) ends at y 32 there. Earlier spots: (972,360), under
# the battle background loaded at (640,272), until 0.2.7; (576,128), over the officer
# screen's unit sprite at (576,192), until 0.2.13; (576,72) until 0.2.15: duel effect
# sprites sample texture page 9 below y 48 (empty in the original), so they showed pieces
# of the font.
# 0.2.17: the battle map picture (GRAPHIC/HMxx.E3, 768x480 8bpp) is uploaded to (640,32)
# as two 384x240 halves; maps 41+ tiles wide (Ep. 4-8, 10-17, 19-29) have pixels at x 960+, so
# the atlas there covered the right part of the map. The atlas now has two homes:
#   P (960,72), texture page 15: default; free outside battles;
#   S (576,98), texture page 9: while the battle map picture is in VRAM. The overview
#     (Select, picture at (520,0) up to 120x200) covers it, so while the overview runs
#     no quads are drawn and new text goes into the canvas as plain 1x glyphs.
# P -> S when a game write covers P (the map loader 0x8005622C uploads the picture as two
# 384x240 halves at (640,32) and (640,272)); S -> P when the battle-animation overlay
# (run at 0x8008636C, also the training duel) writes into the map area: the game reloads
# the map afterwards (0x80086440). S is then cleared: duel effects sample texture page 9,
# empty in the original.
# Atlas: 25 x 4 cells of 10x22 texels (glyph rows 2-23; all glyphs are at most 10 wide)
# = 64 halfwords x 88 rows, then 16 CLUTs (64 x 4) at y + 88.
HOMES = ((960, 72, 15), (576, 98, 9))     # x, y, texture page
CELL_W, CELL_H, CELLS = 10, 22, 25
ATLAS_H = 4 * CELL_H + 4                   # atlas + CLUT rows
MAP_AREA = (640, 32)                       # battle map picture: x 640-1023, y 32-511
BA_CALL = 0x80086364                       # lui at / ori at / jalr at -> overlay 0x801F8000
BA_OVL = 0x801F8000
OVERVIEW = 0x800665C4                      # battle overview (Select): HMS upload + loop
OVERVIEW_CALLS = (0x80068904, 0x80077284)
CODE2_ADDR = 0x8000D980                    # 0x8000D000-0x8000DF00: zero in a player's
CODE2_END = 0x8000DF00                     # SCPH-1001 session; tools/gdbdbg.py scratch below
MAXQ = 400                     # quads per sprite sort
SPACE_ADV = 3
INK = 128

GAME = dict(
    BLIT=0x8001031C, ORIG_DRAW=0x8001B9B8, CANVAS=0x8019A000, PAL=0x800ACB80,
    PKT=0x801436D4, OFSX=0x80143892, OFSY=0x80143894,
    LOADIMAGE=0x800A5774, MOVEIMAGE=0x800A5834, CLEARIMAGE=0x800A564C, DRAWSYNC=0x800A54C8,
    TOWN_NAMES=0x800DDD40, FILE_INDEX=0x80010938, READ_SECTORS=0x800109C0, FAT_TABLE=0x800AB36C,
    SORT_RESUME=0x800A2D14, COPY_LOOP=0x800207C0, LI_RESUME=0x800A577C, MI_RESUME=0x800A583C, CI_RESUME=0x800A5654,
)


# Skies rows (2x texels): cap height 2, x-height 7, baseline 20, descender 22. Skies' digits,
# 'f', 'J', '!', '?' run one or two rows above / below that (1..21), 'a', 'p', 'q' start on
# row 6 and '.' sits on row 21; upscaled, they stood taller or lower than their neighbours.
# These are shortened by dropping repeated rows of their straight parts (normalize).
CAP_TOP, X_TOP, BASE, DESC = 2, 7, 20, 22
NORM = {c: (CAP_TOP, BASE) for c in '0123456789fJ!?'}
NORM.update({'a': (X_TOP, BASE), 'p': (X_TOP, DESC), 'q': (X_TOP, DESC), '5': (CAP_TOP, BASE)})


def normalize(ch, ink):
    """ink: 24 rows x 12 -> rows with the glyph's top / bottom moved to NORM[ch] by
    deleting repeated rows (the row equal to the one above it, nearest the glyph's middle);
    '.' moves up onto the baseline."""
    rows = [list(r) for r in ink]

    def extent():
        ys = [y for y in range(24) if any(rows[y])]
        return ys[0], ys[-1]
    if ch == '.':
        top, bot = extent()
        if bot > BASE:
            rows = rows[bot - BASE:] + [[0] * 12 for _ in range(bot - BASE)]
        return rows
    if ch not in NORM:
        return rows
    want_top, want_bot = NORM[ch]

    def drop(lo, hi):
        """index of a row to delete in [lo, hi): equal to the row above, nearest the middle"""
        mid = (lo + hi) / 2.0
        cand = [y for y in range(max(lo, 1), hi) if rows[y] == rows[y - 1] and any(rows[y])]
        if not cand:
            cand = [y for y in range(max(lo, 1), hi) if any(rows[y])]
        return min(cand, key=lambda y: (abs(y - mid), y))
    top, bot = extent()
    lim = min(bot, BASE)                            # straight parts above the baseline
    while bot > want_bot:                           # rows below move up
        y = drop(top + 3, lim - 2)
        rows = rows[:y] + rows[y + 1:] + [[0] * 12]
        top, bot = extent()
        lim = min(bot, BASE)
    while top < want_top:                           # rows above move down
        y = drop(top + 3, lim - 2)
        rows = [[0] * 12] + rows[:y] + rows[y + 1:]
        top, bot = extent()
        lim = min(bot, BASE)
    return rows


def build_font():
    """-> (met bytes 96x4: w2, adv, mx, my; rows bytes 96x24 u16)"""
    im = Image.open(SKIES).convert('L')
    px = im.load()
    met, rows = bytearray(), bytearray()
    glyphs = {}
    for i in range(96):
        ink = [[1 if px[i * 12 + x, y] >= INK else 0 for x in range(12)] for y in range(24)]
        ink = normalize(chr(32 + i), ink)
        cols = [x for x in range(12) if any(r[x] for r in ink)]
        glyphs[32 + i] = (ink, cols)
    dig = max(len(glyphs[c][1]) for c in range(0x30, 0x3A))
    dig_qw = (dig + 1) // 2
    for code in range(0x20, 0x80):
        ink, cols = glyphs[code]
        if code == 0x20 or not cols:
            met += bytes((0, SPACE_ADV, 0, 0))
            rows += bytes(48)
            continue
        x0, x1 = cols[0], cols[-1]
        w2 = x1 - x0 + 1
        shift = 0
        if 0x30 <= code <= 0x39:                   # tabular digits, centred
            shift = (dig_qw * 2 - w2) // 2
            w2 = dig_qw * 2
        words = []
        for r in ink:
            v = 0
            for x in range(x0, x1 + 1):
                if r[x]:
                    v |= 0x8000 >> (x - x0 + shift)
            words.append(v)
        qw = (w2 + 1) // 2
        # every glyph moves one texel down (see native_texels): baseline on row 21
        dy = 1
        words = native_texels(ink, x0 - shift, qw, ([0] * dy + words)[:24], dy)
        # marker: first fully inked 1x pixel, else the best covered one
        best = None
        for y in range(12):
            for x in range(qw):
                m = 0x8000 >> (2 * x)
                n = sum(1 for yy in (2 * y, 2 * y + 1) for mm in (m, m >> 1) if words[yy] & mm)
                if best is None or n > best[0]:
                    best = (n, x, y)
        met += bytes((w2, qw + 1, best[1], best[2]))
        rows += struct.pack('>24H', *words)[::1] if False else b''.join(struct.pack('<H', w) for w in words)
    return bytes(met), bytes(rows)


def native_texels(glyph, sx, qw, words, dy=1):
    """At native resolution the GPU shows only texel (2a, 2j) of each glyph (the quads
    are drawn at half size), and Skies' pixels there gave letters of uneven height (tops
    on row 7, but 'a' on 6 and capitals on 2). The glyph is moved one texel down, so the
    shown texels sample Skies' odd rows, where every top, stroke and baseline of this
    two-texel-thick font has ink; a shown texel is also inked when 3 of its 2x2 block
    are (keeps comma tails, hyphens and diagonals). Thin glyphs that keep less than 60 %
    of their pixels that way, like the parentheses, take 2 of 4. The other texels keep
    the Skies shape for upscaled rendering.
    glyph: the normalized Skies glyph (24 rows x 12); words: its 24 rows already shifted
    down dy texels; sx: Skies column of texel 0."""
    def ink(x, y):
        x += sx
        y -= dy
        return glyph[y][x] if 0 <= x < 12 and 0 <= y < 24 else 0

    def plane(rule):
        return [[rule(a, j) for a in range(qw)] for j in range(12)]

    def count(a, j):
        return ink(2 * a, 2 * j) + ink(2 * a + 1, 2 * j) + ink(2 * a, 2 * j + 1) + ink(2 * a + 1, 2 * j + 1)
    main = plane(lambda a, j: 1 if ink(2 * a, 2 * j) or count(a, j) >= 3 else 0)
    loose = plane(lambda a, j: 1 if count(a, j) >= 2 else 0)
    if sum(map(sum, main)) < 0.6 * sum(map(sum, loose)):
        main = loose
    out = list(words)
    for j in range(12):
        for a in range(qw):
            bit = 0x8000 >> (2 * a)
            if main[j][a]:
                out[2 * j] |= bit
            else:
                out[2 * j] &= ~bit & 0xffff
    return out


def advances():
    met, _ = build_font()
    return {0x20 + i: met[4 * i + 1] for i in range(96)}


ASM = r'''
; ---------------------------------------------------------------- put-char
; replaces jal ORIG_DRAW in put-char: a0 win, a1 x, a2 y, a3 code, 0x10(sp) mode
vwf_draw:
    sltiu $t0, $a3, 0x20
    bnez $t0, @orig
    sltiu $t0, $a3, 0x80
    beqz $t0, @orig
    nop
    addiu $sp, $sp, -0x48
    sw $ra, 0x44($sp)
    sw $s0, 0x30($sp)
    sw $s1, 0x34($sp)
    sw $s2, 0x38($sp)
    sw $s3, 0x3c($sp)
    sw $s4, 0x40($sp)
    move $s0, $a0
    move $s1, $a1
    move $s2, $a2
    addiu $s3, $a3, -0x20
    lbu $t0, 0($s0)
    nop
    andi $t1, $t0, 0x80
    bnez $t1, @y12
    nop
    addiu $s2, $s2, 2
@y12:
    la $t2, FONT_MET
    sll $t3, $s3, 2
    addu $t2, $t2, $t3
    lbu $t4, 1($t2)
    andi $t1, $t0, 0x20
    bnez $t1, @noadv
    nop
    lw $t5, 4($s0)
    nop
    addiu $t5, $t5, -8
    addu $t5, $t5, $t4
    sw $t5, 4($s0)
@noadv:
    ; opaque draw (blit mode gp+0x168 & 15 == 0, as in 0x8001B2F4): the original glyph
    ; blit painted its whole cell (unset pixels in the background colour gp+0x16A), so
    ; numbers re-printed in place (HP counters) left nothing behind; paint the
    ; advance x 12 cell first
    lbu $t0, 0x168($gp)
    nop
    andi $t0, $t0, 15
    bnez $t0, @nocl
    nop
    lbu $t0, 0x16a($gp)
    li $t1, 0x11111111
    multu $t0, $t1
    la $t3, ZBUF
    addiu $t5, $t3, 48
    mflo $t0
@zf:
    sw $t0, 0($t3)
    addiu $t3, $t3, 4
    bne $t3, $t5, @zf
    nop
    lbu $t4, 1($t2)
    li $a0, 0x140
    li $a1, 0xf0
    la $a2, CANVAS
    move $a3, $s1
    sw $s2, 0x10($sp)
    sw $t4, 0x14($sp)
    li $t0, 12
    sw $t0, 0x18($sp)
    sw $zero, 0x1c($sp)
    la $t0, ZBUF
    jal BLIT
    sw $t0, 0x20($sp)
    la $t2, FONT_MET
    sll $t3, $s3, 2
    addu $t2, $t2, $t3
@nocl:
    lbu $t4, 0($t2)
    nop
    beqz $t4, @done
    nop
    lbu $s4, 0x169($gp)
    move $a0, $s3
    move $a1, $s4
    la $a2, UBUF
    lui $a3, %hi(OVL)
    jal underlay                    ; overview running (no atlas): plain 1x glyph
    lw $a3, %lo(OVL)($a3)
    li $a0, 0x140
    li $a1, 0xf0
    la $a2, CANVAS
    move $a3, $s1
    sw $s2, 0x10($sp)
    li $t0, 8
    sw $t0, 0x14($sp)
    li $t0, 12
    sw $t0, 0x18($sp)
    li $t0, 4
    sw $t0, 0x1c($sp)
    la $t0, UBUF
    jal BLIT
    sw $t0, 0x20($sp)
    li $t0, 1
    sw $t0, 0x170($gp)
    sw $zero, 0x174($gp)
    lui $t0, %hi(OVL)
    lw $t0, %lo(OVL)($t0)
    nop
    bnez $t0, @done                 ; plain glyph: no record
    nop
    move $a0, $s1
    move $a1, $s2
    move $a2, $s3
    jal rec_insert
    move $a3, $s4
@done:
    lw $ra, 0x44($sp)
    lw $s0, 0x30($sp)
    lw $s1, 0x34($sp)
    lw $s2, 0x38($sp)
    lw $s3, 0x3c($sp)
    lw $s4, 0x40($sp)
    addiu $sp, $sp, 0x48
    jr $ra
    move $v0, $zero
@orig:
    j ORIG_DRAW
    nop

; underlay(a0 glyph, a1 colour, a2 out 12 words, a3 plain): 1x pixels inked in all four
; 2x texels (plus the marker pixel) = colour, others 0; nibble 0 = left pixel. a3 != 0:
; the plain 1x glyph instead (texel (2x, 2y), what the quad shows at 1x), no marker
underlay:
    la $t0, FONT_ROWS
    sll $t1, $a0, 4
    sll $t2, $a0, 5
    addu $t1, $t1, $t2
    addu $t0, $t0, $t1
    la $t1, FONT_MET
    sll $t2, $a0, 2
    addu $t1, $t1, $t2
    lbu $t8, 2($t1)
    lbu $t9, 3($t1)
    move $t3, $zero
@row:
    lhu $t4, 0($t0)
    lhu $t5, 2($t0)
    bnez $a3, @plain
    nop
    and $t4, $t4, $t5
    sll $t5, $t4, 1
    and $t4, $t4, $t5
@plain:
    move $t6, $zero
    move $t7, $zero
    li $v0, 0x8000
    move $v1, $a1
@px:
    and $t5, $t4, $v0
    beqz $t5, @skip
    nop
    or $t6, $t6, $v1
@skip:
    srl $v0, $v0, 2
    addiu $t7, $t7, 1
    sltiu $t5, $t7, 6
    bnez $t5, @px
    sll $v1, $v1, 4
    bnez $a3, @nom
    nop
    bne $t3, $t9, @nom
    sll $t5, $t8, 2
    sllv $t5, $a1, $t5
    or $t6, $t6, $t5
@nom:
    sw $t6, 0($a2)
    addiu $a2, $a2, 4
    addiu $t0, $t0, 4
    addiu $t3, $t3, 1
    sltiu $t5, $t3, 12
    bnez $t5, @row
    nop
    jr $ra
    nop

; rec_valid(a0 record) -> v0 = 1 if the canvas still holds the record's underlay
; exactly (underlay pixels = colour, the other pixels of its cell != colour); records
; outside the canvas or with a bad glyph are invalid (a record overwritten by something
; else must not make the check read outside RAM)
rec_valid:
    lhu $t0, 0($a0)
    lhu $t1, 2($a0)
    lbu $t2, 4($a0)
    sltiu $t0, $t0, 320
    sltiu $t1, $t1, 229
    and $t0, $t0, $t1
    sltiu $t2, $t2, 96
    and $t0, $t0, $t2
    bnez $t0, @rvok
    nop
    jr $ra
    move $v0, $zero
@rvok:
    addiu $sp, $sp, -0x20
    sw $ra, 0x1c($sp)
    sw $s0, 0x18($sp)
    move $s0, $a0
    lbu $a0, 4($s0)
    lbu $a1, 5($s0)
    la $a2, VBUF
    jal underlay
    move $a3, $zero
    lbu $t0, 4($s0)
    la $t1, FONT_MET
    sll $t0, $t0, 2
    addu $t1, $t1, $t0
    lbu $t0, 0($t1)
    nop
    addiu $t0, $t0, 1
    srl $t9, $t0, 1                 ; qw
    lhu $t0, 0($s0)                 ; x
    lhu $t1, 2($s0)                 ; y
    lbu $t8, 5($s0)                 ; colour
    move $a2, $zero                 ; hole pixels
    move $a3, $zero                 ; hole pixels in the text colour
    la $t2, VBUF
    li $t3, 12
@vrow:
    sll $t4, $t1, 7
    sll $t5, $t1, 5
    addu $t4, $t4, $t5              ; y * 160
    la $t5, CANVAS
    addu $t4, $t4, $t5
    lw $t6, 0($t2)                  ; expected nibbles
    move $t7, $t0
    move $v1, $t9
@vpx:
    srl $t5, $t7, 1
    addu $t5, $t4, $t5
    lbu $t5, 0($t5)
    andi $v0, $t7, 1
    beqz $v0, @lo
    nop
    srl $t5, $t5, 4
@lo:
    andi $t5, $t5, 15
    andi $v0, $t6, 15
    beqz $v0, @hole
    nop
    bne $t5, $t8, @bad
    nop
    b @nx
    nop
@hole:
    addiu $a2, $a2, 1
    bne $t5, $t8, @nx
    nop
    addiu $a3, $a3, 1
@nx:
    srl $t6, $t6, 4
    addiu $t7, $t7, 1
    addiu $v1, $v1, -1
    bnez $v1, @vpx
    nop
    addiu $t2, $t2, 4
    addiu $t1, $t1, 1
    addiu $t3, $t3, -1
    bnez $t3, @vrow
    nop
    ; a few background pixels of the cell may share the text colour (dithered or gradient
    ; boxes, e.g. the highlighted save slot); the cell counts as overwritten only when more
    ; than half of them do
    sll $t0, $a3, 1
    sltu $t0, $a2, $t0
    bnez $t0, @bad
    nop
    b @vret
    li $v0, 1
@bad:
    move $v0, $zero
@vret:
    lw $ra, 0x1c($sp)
    lw $s0, 0x18($sp)
    jr $ra
    addiu $sp, $sp, 0x20

; rec_insert(a0 x, a1 y, a2 glyph, a3 colour): slot by (x, y) hash, linear probe;
; reuse an empty slot, the same position or a dead record
rec_insert:
    addiu $sp, $sp, -0x30
    sw $ra, 0x2c($sp)
    sw $s0, 0x10($sp)
    sw $s1, 0x14($sp)
    sw $s2, 0x18($sp)
    sw $s3, 0x1c($sp)
    sw $s4, 0x20($sp)
    sw $s5, 0x24($sp)
    move $s0, $a0
    move $s1, $a1
    move $s2, $a2
    move $s3, $a3
    ; text drawn over older text: drop every record whose cell this glyph's cell overlaps
    ; (also the same position), or an old record whose underlay pixels happen to be
    ; covered by the new glyphs stays live and shows a stray letter
    la $t0, FONT_MET
    sll $t1, $s2, 2
    addu $t0, $t0, $t1
    lbu $t1, 0($t0)
    nop
    addiu $t1, $t1, 1
    srl $t1, $t1, 1
    addu $t9, $s0, $t1              ; new x1
    addiu $t8, $s1, 12              ; new y1
    la $t0, RECS
    li $t7, NRECS
@kill:
    lhu $t2, 0($t0)                 ; old x
    li $t3, 0xffff
    beq $t2, $t3, @knext
    lhu $t3, 2($t0)                 ; old y
    nop
    sltu $t4, $t2, $t9
    beqz $t4, @knext
    sltu $t4, $t3, $t8
    beqz $t4, @knext
    addiu $t5, $t3, 12
    sltu $t4, $s1, $t5
    beqz $t4, @knext
    lbu $t5, 4($t0)                 ; old glyph
    la $t6, FONT_MET
    sll $t5, $t5, 2
    addu $t6, $t6, $t5
    lbu $t5, 0($t6)
    nop
    addiu $t5, $t5, 1
    srl $t5, $t5, 1
    addu $t5, $t2, $t5              ; old x1
    sltu $t4, $s0, $t5
    beqz $t4, @knext
    nop
    li $t4, 0xffff
    sh $t4, 0($t0)
@knext:
    addiu $t7, $t7, -1
    bnez $t7, @kill
    addiu $t0, $t0, 8
    sll $t0, $s1, 4
    addu $t0, $t0, $s0
    srl $t1, $s1, 2
    addu $s4, $t0, $t1              ; hash
    li $s5, 16
@probe:
    andi $t0, $s4, NRECS_MASK
    sll $t0, $t0, 3
    la $a0, RECS
    addu $a0, $a0, $t0
    lhu $t1, 0($a0)
    li $t2, 0xffff
    beq $t1, $t2, @put
    nop
    bne $t1, $s0, @other
    nop
    lhu $t1, 2($a0)
    nop
    beq $t1, $s1, @put
    nop
@other:
    sw $a0, 0x28($sp)
    jal rec_valid
    nop
    beqz $v0, @put
    lw $a0, 0x28($sp)
    addiu $s4, $s4, 1
    addiu $s5, $s5, -1
    bnez $s5, @probe
    nop
    addiu $s4, $s4, -16
    andi $t0, $s4, NRECS_MASK
    sll $t0, $t0, 3
    la $a0, RECS
    addu $a0, $a0, $t0
@put:
    nop
    sh $s0, 0($a0)
    sh $s1, 2($a0)
    sb $s2, 4($a0)
    sb $s3, 5($a0)
    lw $ra, 0x2c($sp)
    lw $s0, 0x10($sp)
    lw $s1, 0x14($sp)
    lw $s2, 0x18($sp)
    lw $s3, 0x1c($sp)
    lw $s4, 0x20($sp)
    lw $s5, 0x24($sp)
    jr $ra
    addiu $sp, $sp, 0x30

; ---------------------------------------------------------------- sprite sort
; GsSortFastSprite entry (a0 sprite, a1 OT, a2 pri)
s_hook:
    lhu $t0, 0xc($a0)
    nop
    andi $t0, $t0, 0x1f
    addiu $t1, $t0, -6
    sltiu $t1, $t1, 2
    beqz $t1, @sorig
    nop
    lh $t1, 0x10($a0)
    li $t2, 320
    bne $t1, $t2, @sorig
    nop
    lh $t1, 0x12($a0)
    li $t2, 240
    bne $t1, $t2, @sorig
    nop
    lui $t0, %hi(OVL)               ; overview: its picture is over home S, no atlas
    lw $t0, %lo(OVL)($t0)
    nop
    bnez $t0, @sorig
    nop
    addiu $sp, $sp, -0x50
    sw $ra, 0x4c($sp)
    sw $s0, 0x20($sp)
    sw $s1, 0x24($sp)
    sw $s2, 0x28($sp)
    sw $s3, 0x2c($sp)
    sw $s4, 0x30($sp)
    sw $s5, 0x34($sp)
    sw $s6, 0x38($sp)
    sw $s7, 0x3c($sp)
    sw $a0, 0x40($sp)
    sw $a1, 0x44($sp)
    sw $a2, 0x48($sp)
    move $s0, $a0
    la $t0, DIRTY
    lw $t1, 0($t0)
    nop
    beqz $t1, @noup
    nop
    jal upload2
    nop
@noup:
    lhu $t0, 0xc($s0)
    nop
    andi $t0, $t0, 0x1f
    addiu $t0, $t0, -6
    sll $t0, $t0, 8
    lbu $t1, 0xe($s0)
    nop
    addu $s1, $t0, $t1              ; canvas x0
    lbu $s2, 0xf($s0)               ; canvas y0
    lhu $t0, 8($s0)
    nop
    addu $s3, $s1, $t0              ; x1
    lhu $t0, 0xa($s0)
    nop
    addu $s4, $s2, $t0              ; y1
    lh $t0, 4($s0)
    lui $t2, %hi(OFSX)
    lh $t1, %lo(OFSX)($t2)
    nop
    addu $t0, $t0, $t1
    subu $s5, $t0, $s1              ; screen x = s5 + rec x
    lh $t0, 6($s0)
    lui $t2, %hi(OFSY)
    lh $t1, %lo(OFSY)($t2)
    nop
    addu $t0, $t0, $t1
    subu $s6, $t0, $s2              ; screen y = s6 + rec y
    addiu $s6, $s6, 1               ; quads start at glyph row 2 (rows 0-1 are empty)
    lw $a1, 0x44($sp)
    lw $a2, 0x48($sp)
    andi $t0, $a2, 0xffff
    sll $t0, $t0, 2
    lw $t1, 4($a1)
    lw $t2, 8($a1)
    addu $t1, $t1, $t0
    sll $t2, $t2, 2
    subu $s7, $t1, $t2              ; OT entry
    ; validity: one bit per record in VBITS, recomputed in the main thread when the game
    ; uploads the canvas (li_hook -> revalidate). Here (often the VSync callback, with
    ; interrupts off) only the set bits are visited: checking records against the canvas
    ; here cost several ms every few frames, which made memory card writes fail (saving
    ; broke off after the 512-byte header, fixed in 0.2.12) and starved the CD interrupt
    ; in rain (0.2.7)
    li $t0, MAXQ
    sw $t0, 0x14($sp)               ; quads left
    sw $zero, 0x10($sp)             ; bitmap word
@wloop:
    lw $t0, 0x10($sp)
    la $t1, VBITS
    sll $t2, $t0, 2
    addu $t1, $t1, $t2
    lw $t1, 0($t1)
    sll $t2, $t0, 8                 ; 32 records x 8 bytes per word
    la $s0, RECS
    addu $s0, $s0, $t2
    sw $t1, 0x18($sp)               ; bits left in this word
@bloop:
    lw $t1, 0x18($sp)
    nop
    beqz $t1, @wnext
    andi $t2, $t1, 1
    srl $t1, $t1, 1
    beqz $t2, @rnext
    sw $t1, 0x18($sp)
    lhu $t0, 0($s0)                 ; x (0xffff: dropped since)
    lhu $t1, 2($s0)
    sltu $t2, $t0, $s1
    bnez $t2, @rnext
    sltu $t2, $t0, $s3
    beqz $t2, @rnext
    sltu $t2, $t1, $s2
    bnez $t2, @rnext
    sltu $t2, $t1, $s4
    beqz $t2, @rnext
    nop
@emit:
    ; emit POLY_FT4
    lui $t9, %hi(PKT)
    lw $t9, %lo(PKT)($t9)
    lbu $t0, 4($s0)                 ; glyph
    lbu $t1, 5($s0)                 ; colour
    la $t2, FONT_MET
    sll $t3, $t0, 2
    addu $t2, $t2, $t3
    lbu $t3, 0($t2)
    nop
    addiu $t3, $t3, 1
    srl $t3, $t3, 1                 ; qw
    li $t6, CELLS                   ; 25 cells of 10x22 per atlas row
    divu $t0, $t6
    mfhi $t4                        ; column
    mflo $t5                        ; row
    sll $t6, $t4, 3
    sll $t4, $t4, 1
    addu $t4, $t4, $t6              ; u = 10 * column
    sll $t6, $t5, 4
    sll $t2, $t5, 2
    addu $t6, $t6, $t2
    sll $t5, $t5, 1
    addu $t5, $t5, $t6
    lui $t2, %hi(QV0)
    lw $t2, %lo(QV0)($t2)
    nop
    addu $t5, $t5, $t2              ; v = home y + 22 * row
    lhu $t6, 0($s0)
    addu $t6, $t6, $s5              ; sx
    lhu $t7, 2($s0)
    addu $t7, $t7, $s6              ; sy
    li $t8, 0x2D808080
    sw $t8, 4($t9)
    andi $t6, $t6, 0xffff
    sll $t8, $t7, 16
    or $t8, $t8, $t6
    sw $t8, 8($t9)                  ; xy0
    srl $t2, $t1, 2                 ; CLUT of colour c: (x + 16 * (c & 3), y + 88 + c / 4)
    sll $t2, $t2, 6
    andi $t6, $t1, 3
    or $t2, $t2, $t6
    lui $t6, %hi(QCLUT)
    lw $t6, %lo(QCLUT)($t6)
    nop
    addu $t2, $t2, $t6
    sll $t2, $t2, 16
    sll $t0, $t5, 8
    or $t0, $t0, $t4
    or $t2, $t2, $t0
    sw $t2, 12($t9)                 ; uv0 + clut
    addu $t2, $t8, $t3
    sw $t2, 16($t9)                 ; xy1
    sll $t2, $t3, 1
    addu $t2, $t0, $t2
    lui $t1, %hi(QTP)
    lw $t1, %lo(QTP)($t1)           ; texture page << 16
    nop
    or $t1, $t1, $t2
    sw $t1, 20($t9)                 ; uv1 + tpage
    lui $t1, CELL_H / 2
    addu $t8, $t8, $t1
    sw $t8, 24($t9)                 ; xy2
    addu $t1, $t8, $t3
    sw $t1, 32($t9)                 ; xy3
    addiu $t0, $t0, CELL_H << 8
    sw $t0, 28($t9)                 ; uv2
    addu $t0, $t0, $t3
    addu $t0, $t0, $t3
    sw $t0, 36($t9)                 ; uv3
    lw $t0, 0($s7)
    lui $t1, 0x00ff
    ori $t1, $t1, 0xffff
    and $t0, $t0, $t1
    lui $t2, 0x0900
    or $t0, $t0, $t2
    sw $t0, 0($t9)
    and $t2, $t9, $t1
    sw $t2, 0($s7)
    addiu $t9, $t9, 40
    lui $t0, %hi(PKT)
    sw $t9, %lo(PKT)($t0)
    lw $t0, 0x14($sp)
    nop
    addiu $t0, $t0, -1
    beqz $t0, @rdone
    sw $t0, 0x14($sp)
@rnext:
    b @bloop
    addiu $s0, $s0, 8
@wnext:
    lw $t0, 0x10($sp)
    nop
    addiu $t0, $t0, 1
    sltiu $t1, $t0, NRECS / 32
    bnez $t1, @wloop
    sw $t0, 0x10($sp)
@rdone:
    lw $ra, 0x4c($sp)
    lw $s0, 0x20($sp)
    lw $s1, 0x24($sp)
    lw $s2, 0x28($sp)
    lw $s3, 0x2c($sp)
    lw $s4, 0x30($sp)
    lw $s5, 0x34($sp)
    lw $s6, 0x38($sp)
    lw $s7, 0x3c($sp)
    lw $a0, 0x40($sp)
    lw $a1, 0x44($sp)
    lw $a2, 0x48($sp)
    addiu $sp, $sp, 0x50
@sorig:
    move $t3, $a0
    j SORT_RESUME
    move $t5, $a1

; ---------------------------------------------------------------- VRAM writes
; game LoadImage / MoveImage / ClearImage rect -> dirty2 (CODE2_ASM): atlas home and re-upload

li_hook:
    lh $t0, 0($a0)
    lh $t1, 2($a0)
    lh $t2, 4($a0)
    lh $t3, 6($a0)
    move $t9, $ra
    jal dirty2
    nop
    move $ra, $t9
    ; an upload over the text canvas (x 384..463, y 0..239) = the canvas changed:
    ; recompute which records it still holds (main thread, interrupts on)
    slti $v0, $t0, 464
    beqz $v0, @lnc
    addu $v0, $t0, $t2
    slti $v0, $v0, 385
    bnez $v0, @lnc
    slti $v0, $t1, 240
    beqz $v0, @lnc
    nop
    addiu $sp, $sp, -0x10
    sw $ra, 0xc($sp)
    sw $a0, 8($sp)
    jal revalidate
    sw $a1, 4($sp)
    lw $ra, 0xc($sp)
    lw $a0, 8($sp)
    lw $a1, 4($sp)
    addiu $sp, $sp, 0x10
@lnc:
    addiu $sp, $sp, -0x20
    j LI_RESUME
    sw $s0, 0x10($sp)

; revalidate: VBITS bit i = record i is live (its underlay is still in the canvas), one
; 32-bit word at a time, so a sort in between sees each word either old or new
revalidate:
    addiu $sp, $sp, -0x28
    sw $ra, 0x24($sp)
    sw $s0, 0x10($sp)
    sw $s1, 0x14($sp)
    sw $s2, 0x18($sp)
    sw $s3, 0x1c($sp)
    la $s0, RECS
    la $s3, VBITS
@vw:
    move $s1, $zero                 ; bits of this word
    li $s2, 1                       ; current bit
@vb:
    lhu $t0, 0($s0)
    li $t1, 0xffff
    beq $t0, $t1, @vnext
    nop
    jal rec_valid
    move $a0, $s0
    beqz $v0, @vnext
    nop
    or $s1, $s1, $s2
@vnext:
    sll $s2, $s2, 1
    bnez $s2, @vb
    addiu $s0, $s0, 8
    sw $s1, 0($s3)
    la $t0, VBITS + NRECS / 8
    addiu $s3, $s3, 4
    bne $s3, $t0, @vw
    nop
    lw $ra, 0x24($sp)
    lw $s0, 0x10($sp)
    lw $s1, 0x14($sp)
    lw $s2, 0x18($sp)
    lw $s3, 0x1c($sp)
    jr $ra
    addiu $sp, $sp, 0x28

mi_hook:
    move $t0, $a1
    move $t1, $a2
    lh $t2, 4($a0)
    lh $t3, 6($a0)
    move $t9, $ra
    jal dirty2
    nop
    move $ra, $t9
    addiu $sp, $sp, -0x20
    j MI_RESUME
    sw $s0, 0x10($sp)

ci_hook:
    lh $t0, 0($a0)
    lh $t1, 2($a0)
    lh $t2, 4($a0)
    lh $t3, 6($a0)
    move $t9, $ra
    jal dirty2
    nop
    move $ra, $t9
    addiu $sp, $sp, -0x28
    j CI_RESUME
    sw $s3, 0x1c($sp)

; ---------------------------------------------------------------- dictionary
; script text copier, path for bytes >= 0x80 (0x800208EC): 0xA0-0xDF = dictionary
; string (tools/dte.py), others = SJIS pair as before. a0 byte, a1 out, a2 in.
; ---------------------------------------------------------------- caption box
; cap_width(a0 line buffer, a1 lines) -> v0 widest line in px (caption box 0x8003F4E4;
; lines are 0x40 bytes apart, NUL-terminated). ASCII = VWF advance, other bytes 8 px
; (the game's own measure). The game sized the box at 8 px per byte, so English captions
; were limited to 36 characters; clamped to 288 px (box + frame = 320).
cap_width:
    move $v0, $zero
    la $t3, FONT_MET
@kl:
    beqz $a1, @kdone
    move $t0, $a0
    move $t2, $zero
@kc:
    lbu $t1, 0($t0)
    addiu $t0, $t0, 1
    beqz $t1, @keol
    addiu $t1, $t1, -0x20
    sltiu $t4, $t1, 96
    bnez $t4, @kasc
    sll $t1, $t1, 2
    b @kc
    addiu $t2, $t2, 8
@kasc:
    addu $t1, $t1, $t3
    lbu $t1, 1($t1)
    b @kc
    addu $t2, $t2, $t1
@keol:
    sltu $t4, $v0, $t2
    beqz $t4, @knext
    nop
    move $v0, $t2
@knext:
    addiu $a1, $a1, -1
    b @kl
    addiu $a0, $a0, 0x40
@kdone:
    sltiu $t4, $v0, 289
    bnez $t4, @kret
    nop
    li $v0, 288
@kret:
    jr $ra
    nop

dict_hook:
    sltiu $v0, $a0, 0xA0
    bnez $v0, @sj
    sltiu $v0, $a0, 0xE0
    beqz $v0, @sj
    nop
    addiu $v0, $a0, -0xA0
    sll $v0, $v0, 1
    la $v1, DICT
    addu $v0, $v1, $v0
    lhu $v0, 0($v0)
    nop
    addu $v1, $v1, $v0
@dcp:
    lbu $v0, 0($v1)
    addiu $v1, $v1, 1
    beqz $v0, @dend
    nop
    sb $v0, 0($a1)
    b @dcp
    addiu $a1, $a1, 1
@dend:
    j COPY_LOOP
    addiu $a2, $a2, 1
@sj:
    addiu $a2, $a2, 1
    sb $a3, 0($a1)
    addiu $a1, $a1, 1
    lbu $v0, 0($a2)
    addiu $a2, $a2, 1
    sb $v0, 0($a1)
    j COPY_LOOP
    addiu $a1, $a1, 1

; ---------------------------------------------------------------- unit bars (0.2.17)
; 0x80010D38 jal hp_frame (was jal DISPLAY_LIST, a0 = GsOT): after the display list, while
; HPON (L2 on the battle map, l2_key in CODE2_ASM), two bars at the bottom of every unit's
; cell on screen: Endurance (green / yellow / red) and SP (blue), current / max as the unit
; window shows them (max: 0x80017DE4 / 0x80017E24 on the officer record). Units: UNITS,
; 90 x 36 bytes (+0 officer, +5 x, +6 y (0xFF: not on the map), +0xB 2 = in the battle,
; +0x10 Endurance, +0x14 SP). Slots 0-29 are Motonari's side (allied armies too), 30-89 the
; enemy: a second colour set (HPCOL). Flat rectangles in OT entry HPPRI = 8, one over the
; units (9), under the command icons and windows.
hp_frame:
    addiu $sp, $sp, -0x38
    sw $ra, 0x34($sp)
    sw $s0, 0x10($sp)
    sw $s1, 0x14($sp)
    sw $s2, 0x18($sp)
    sw $s3, 0x1c($sp)
    sw $s4, 0x20($sp)
    sw $s5, 0x24($sp)
    sw $s6, 0x28($sp)
    sw $s7, 0x2c($sp)
    jal DISPLAY_LIST
    move $s0, $a0
    lui $t0, %hi(L2HELD)            ; L2 released for 2 frames: the next press toggles
    lw $t1, %lo(L2HELD)($t0)
    nop
    beqz $t1, @held
    addiu $t1, $t1, -1
    sw $t1, %lo(L2HELD)($t0)
@held:
    lui $t0, %hi(OVL)               ; not over the battle overview
    lw $t0, %lo(OVL)($t0)
    nop
    bnez $t0, @done
    lui $t0, %hi(HPON)
    lw $t0, %lo(HPON)($t0)
    lui $t1, %hi(SCRIPT_NO)
    beqz $t0, @done
    lbu $t1, %lo(SCRIPT_NO)($t1)
    la $t0, MAPQ                    ; battle script and the map drawn this frame
    andi $t1, $t1, 1
    beqz $t1, @done
    lbu $t1, 0x25($t0)
    li $t2, 7
    bne $t1, $t2, @done
    lh $s3, 4($t0)                  ; x of cell column 0
    lh $s4, 6($t0)                  ; y of cell row 0
    lw $t0, 4($s0)                  ; OT entry HPPRI
    lw $t1, 8($s0)
    addiu $t0, $t0, HPPRI * 4
    sll $t1, $t1, 2
    subu $s0, $t0, $t1
    la $s1, UNITS
    li $s2, 90
@unit:
    lbu $t0, 0xb($s1)
    li $t1, 2
    bne $t0, $t1, @next
    lbu $t2, 5($s1)
    li $t1, 0xff
    beq $t2, $t1, @next
    lbu $t3, 6($s1)
    sll $t2, $t2, 5
    addu $s5, $t2, $s3              ; cell x
    sll $t4, $t3, 4
    sll $t3, $t3, 3
    addu $t3, $t3, $t4
    addu $s6, $t3, $s4              ; cell y
    addiu $t4, $s5, 32
    sltiu $t4, $t4, 352
    beqz $t4, @next
    addiu $t4, $s6, 24
    sltiu $t4, $t4, 264
    beqz $t4, @next
    la $t9, HPCOL                   ; colours: units 0-29 Mouri side, 30-89 enemies
    sltiu $t8, $s2, 61
    beqz $t8, @side
    lw $t0, 0($s1)
    addiu $t9, $t9, 20
@side:
    sw $t9, 0x30($sp)
    la $s7, OFFICERS
    sll $t1, $t0, 2
    addu $t1, $t1, $t0
    sll $t1, $t1, 4
    addu $s7, $s7, $t1              ; officer record
    jal MAXSP
    move $a0, $s7
    lw $a0, 0x14($s1)
    jal bar_w
    move $a1, $v0
    lw $t9, 0x30($sp)
    addiu $a0, $s5, 3               ; SP bar
    addiu $a1, $s6, 21
    lui $a2, 2
    or $a2, $a2, $v0
    jal tile
    lw $a3, 0($t9)
    jal MAXEND
    move $a0, $s7
    lw $a0, 0x10($s1)
    jal bar_w
    move $a1, $v0
    lw $t9, 0x30($sp)
    sltiu $t0, $v0, 14
    beqz $t0, @col
    lw $a3, 4($t9)                  ; more than half
    sltiu $t0, $v0, 7
    beqz $t0, @col
    lw $a3, 8($t9)
    lw $a3, 12($t9)
@col:
    addiu $a0, $s5, 3               ; Endurance bar
    addiu $a1, $s6, 18
    lui $a2, 2
    jal tile
    or $a2, $a2, $v0
    lw $t9, 0x30($sp)
    addiu $a0, $s5, 2               ; frame (linked last = drawn first)
    addiu $a1, $s6, 17
    lui $a2, 6
    ori $a2, $a2, 28
    jal tile
    lw $a3, 16($t9)
@next:
    addiu $s2, $s2, -1
    bnez $s2, @unit
    addiu $s1, $s1, 36
@done:
    lw $ra, 0x34($sp)
    lw $s0, 0x10($sp)
    lw $s1, 0x14($sp)
    lw $s2, 0x18($sp)
    lw $s3, 0x1c($sp)
    lw $s4, 0x20($sp)
    lw $s5, 0x24($sp)
    lw $s6, 0x28($sp)
    lw $s7, 0x2c($sp)
    jr $ra
    addiu $sp, $sp, 0x38

; bar_w(a0 current, a1 max) -> v0 = 26 * current / max, 1..26 when current > 0
bar_w:
    beqz $a1, @z
    sll $t0, $a0, 4
    sll $t1, $a0, 3
    addu $t0, $t0, $t1
    sll $t1, $a0, 1
    addu $t0, $t0, $t1
    divu $t0, $a1
    mflo $v0
    sltiu $t1, $v0, 27
    bnez $t1, @c
    nop
    li $v0, 26
@c:
    bnez $v0, @r
    nop
    sltu $v0, $zero, $a0
@r:
    jr $ra
    nop
@z:
    jr $ra
    move $v0, $zero

; bar colours (GP0 0x60 TILE + BGR): SP, Endurance > 1/2, > 1/4, low, frame; Mouri side, enemies
HPCOL:
    .word HP_SP, HP_HI, HP_MID, HP_LO, HP_BG
    .word EN_SP, EN_HI, EN_MID, EN_LO, EN_BG

; tile(a0 x, a1 y, a2 h << 16 | w, a3 GP0 0x60 TILE + colour): link a flat rectangle at the
; head of OT entry s0
tile:
    lui $t0, %hi(PKT)
    lw $t1, %lo(PKT)($t0)
    andi $a0, $a0, 0xffff
    sw $a3, 4($t1)
    sll $a1, $a1, 16
    or $a0, $a0, $a1
    sw $a0, 8($t1)
    sw $a2, 12($t1)
    lw $t2, 0($s0)
    lui $t3, 0x00ff
    ori $t3, $t3, 0xffff
    and $t4, $t2, $t3
    lui $t5, 0x0300
    or $t4, $t4, $t5
    sw $t4, 0($t1)
    and $t4, $t1, $t3
    lui $t5, 0xff00
    and $t2, $t2, $t5
    or $t2, $t2, $t4
    sw $t2, 0($s0)
    addiu $t1, $t1, 16
    jr $ra
    sw $t1, %lo(PKT)($t0)

    .align 4
DICT:
    .incbin dict
    .align 4
VBITS:
    .space NRECS / 8
UBUF:
    .space 48
ZBUF:
    .space 48
VBUF:
    .space 48
'''

# Atlas homes, upload and the overview flag: kernel RAM CODE2_ADDR (the main hook block
# is full). Data first, at fixed offsets (the main block refers to them).
CODE2_ASM = r'''
DIRTY:
    .word 1                         ; atlas must be (re)uploaded at the current home
HOME:
    .word 0                         ; 0 = P, 1 = S
PBUSY:
    .word 0                         ; the game has data over home P (battle map picture)
OVL:
    .word 0                         ; battle overview running
CLRS:
    .word 0                         ; home S must be cleared at the next upload
INUP:
    .word 0                         ; inside upload2: own VRAM writes do not count
QV0:
    .word {P_Y}                     ; atlas y of the current home
QCLUT:
    .word {P_CLUT}                  ; CLUT id of colour 0 at the current home
QTP:
    .word {P_TP}                    ; texture page << 16
SAVRA:
    .word 0
INBA:
    .word 0                         ; battle-animation overlay running
SAVRA2:
    .word 0
HPON:
    .word 0                         ; unit bars on the battle map (L2)
L2HELD:
    .word 0                         ; L2 seen in the last frames (hp_frame counts it down)
HOMETAB:
    .word {P_X}, {P_Y}, {P_TP}, {S_X}, {S_Y}, {S_TP}
RECT2:
    .space 8

; dirty2(t0 x, t1 y, t2 w, t3 h): a game VRAM write. Keeps a0-a3, t0-t3, t9.
dirty2:
    lui $v1, %hi(INUP)
    lw $v0, %lo(INUP)($v1)
    nop
    bnez $v0, @ret
    addu $t4, $t0, $t2              ; x1
    slti $v0, $t4, {P_X} + 1        ; over home P (x {P_X}.., y {P_Y}..{P_Y1})?
    bnez $v0, @notp
    slti $v0, $t1, {P_Y1}
    beqz $v0, @notp
    addu $t5, $t1, $t3
    slti $v0, $t5, {P_Y} + 1
    bnez $v0, @notp
    li $v0, 1
    lui $v1, %hi(PBUSY)
    b @want
    sw $v0, %lo(PBUSY)($v1)
@notp:
    lui $v1, %hi(INBA)              ; the animation overlay writes into the map area: the
    lw $v0, %lo(INBA)($v1)          ; map is gone (reloaded after the animation)
    nop
    beqz $v0, @want
    slti $v0, $t4, {MAP_X} + 1      ; x1 > 640
    bnez $v0, @want
    addu $t5, $t1, $t3
    slti $v0, $t5, {MAP_Y} + 1      ; y1 > 32
    bnez $v0, @want
    lui $v1, %hi(PBUSY)
    sw $zero, %lo(PBUSY)($v1)
@want:
    lui $v1, %hi(PBUSY)
    lw $t6, %lo(PBUSY)($v1)         ; wanted home: S while P is busy
    lui $v1, %hi(HOME)
    lw $t7, %lo(HOME)($v1)
    nop
    beq $t6, $t7, @gen
    nop
    sw $t6, %lo(HOME)($v1)
    beqz $t7, @dset                 ; leaving S: clear it at the upload
    li $v0, 1
    lui $v1, %hi(CLRS)
    sw $v0, %lo(CLRS)($v1)
@dset:
    lui $v1, %hi(DIRTY)
    jr $ra
    sw $v0, %lo(DIRTY)($v1)
@gen:
    ; a write over the current home: re-upload there (next canvas sprite sort)
    la $t8, HOMETAB
    sll $v0, $t7, 3
    sll $t7, $t7, 2
    addu $v0, $v0, $t7
    addu $t8, $t8, $v0
    lw $t6, 0($t8)                  ; home x
    lw $t7, 4($t8)                  ; home y
    addiu $t5, $t6, 64              ; x < hx + 64
    slt $v0, $t0, $t5
    beqz $v0, @ret
    addiu $t5, $t6, 1
    slt $v0, $t4, $t5               ; x1 > hx
    bnez $v0, @ret
    addiu $t5, $t7, {ATLAS_H}
    slt $v0, $t1, $t5               ; y < hy + h
    beqz $v0, @ret
    addu $t5, $t1, $t3
    addiu $t4, $t7, 1
    slt $v0, $t5, $t4               ; y1 > hy
    bnez $v0, @ret
    li $v0, 1
    lui $v1, %hi(DIRTY)
    sw $v0, %lo(DIRTY)($v1)
@ret:
    jr $ra
    nop

; upload2: atlas (4 cell rows x 2 pieces of 11 rows, 64 x 11 halfwords each) and the
; 16 CLUTs at the current home, synchronously; clears home S first when it was left
upload2:
    addiu $sp, $sp, -0x30
    sw $ra, 0x2c($sp)
    sw $s0, 0x20($sp)
    sw $s1, 0x24($sp)
    sw $s2, 0x28($sp)
    li $t0, 1
    lui $t1, %hi(INUP)
    sw $t0, %lo(INUP)($t1)
    lui $t1, %hi(CLRS)
    lw $t0, %lo(CLRS)($t1)
    nop
    beqz $t0, @noclr
    nop
    sw $zero, %lo(CLRS)($t1)
    la $a0, RECT2
    li $t0, {S_X}
    sh $t0, 0($a0)
    li $t0, {S_Y}
    sh $t0, 2($a0)
    li $t0, 64
    sh $t0, 4($a0)
    li $t0, {ATLAS_H}
    sh $t0, 6($a0)
    move $a1, $zero
    move $a2, $zero
    jal CLEARIMAGE
    move $a3, $zero
    jal DRAWSYNC
    move $a0, $zero
@noclr:
    lui $t1, %hi(HOME)
    lw $t0, %lo(HOME)($t1)
    la $t8, HOMETAB
    sll $t1, $t0, 3
    sll $t0, $t0, 2
    addu $t0, $t0, $t1
    addu $t8, $t8, $t0
    lw $s1, 0($t8)                  ; home x
    lw $s2, 4($t8)                  ; home y
    lw $t0, 8($t8)
    lui $t1, %hi(QTP)
    sw $t0, %lo(QTP)($t1)
    lui $t1, %hi(QV0)
    sw $s2, %lo(QV0)($t1)
    addiu $t0, $s2, {ATLAS_H} - 4   ; CLUT id: (y + 88) << 6 | x >> 4
    sll $t0, $t0, 6
    srl $t1, $s1, 4
    or $t0, $t0, $t1
    lui $t1, %hi(QCLUT)
    sw $t0, %lo(QCLUT)($t1)
    move $s0, $zero                 ; piece: cell row s0 >> 1, half s0 & 1
@piece:
    la $t0, STRIP                   ; 128 bytes x 11 rows, zeroed
    li $t1, 352
@z:
    sw $zero, 0($t0)
    addiu $t1, $t1, -1
    bnez $t1, @z
    addiu $t0, $t0, 4
    srl $t1, $s0, 1
    sll $t2, $t1, 4
    sll $t3, $t1, 3
    addu $t2, $t2, $t3
    addu $t1, $t2, $t1              ; first glyph = 25 * cell row
    la $t0, STRIP                   ; dest: cell column
    li $t2, {CELLS}
@gl:
    sltiu $t3, $t1, 96
    beqz $t3, @gdone
    andi $t3, $s0, 1                ; first font row: 2 or 13
    sll $t4, $t3, 3
    sll $t5, $t3, 1
    addu $t3, $t4, $t3
    addu $t3, $t3, $t5              ; 11 * half
    addiu $t3, $t3, 2
    sll $t3, $t3, 1
    la $t4, FONT_ROWS
    addu $t3, $t3, $t4
    sll $t4, $t1, 4
    sll $t5, $t1, 5
    addu $t4, $t4, $t5
    addu $t3, $t3, $t4              ; rows of glyph t1
    move $t4, $t0
    li $t5, 11
@grow:
    lhu $t6, 0($t3)
    addiu $t3, $t3, 2
    li $t7, 5
    move $t8, $t4
@gbyte:
    srl $t9, $t6, 15
    srl $v0, $t6, 14
    andi $v0, $v0, 1
    sll $v0, $v0, 4
    or $t9, $t9, $v0
    sll $t6, $t6, 2
    andi $t6, $t6, 0xffff
    sb $t9, 0($t8)
    addiu $t7, $t7, -1
    bnez $t7, @gbyte
    addiu $t8, $t8, 1
    addiu $t5, $t5, -1
    bnez $t5, @grow
    addiu $t4, $t4, 128
    addiu $t0, $t0, 5
    addiu $t2, $t2, -1
    bnez $t2, @gl
    addiu $t1, $t1, 1
@gdone:
    la $a0, RECT2
    sh $s1, 0($a0)
    srl $t1, $s0, 1                 ; y = home y + 22 * cell row + 11 * half
    sll $t2, $t1, 4
    sll $t3, $t1, 2
    addu $t2, $t2, $t3
    sll $t1, $t1, 1
    addu $t1, $t1, $t2
    andi $t2, $s0, 1
    sll $t3, $t2, 3
    sll $t4, $t2, 1
    addu $t3, $t3, $t4
    addu $t2, $t3, $t2
    addu $t1, $t1, $t2
    addu $t1, $t1, $s2
    sh $t1, 2($a0)
    li $t0, 64
    sh $t0, 4($a0)
    li $t0, 11
    sh $t0, 6($a0)
    la $a1, STRIP
    jal LOADIMAGE
    nop
    jal DRAWSYNC
    move $a0, $zero
    addiu $s0, $s0, 1
    sltiu $t0, $s0, 8
    bnez $t0, @piece
    nop
    ; CLUTs: c = {{0, canvas colour c, 0...}}, 4 per 64-halfword row (offset c * 32 bytes)
    la $t0, STRIP
    li $t1, 128
@cz:
    sw $zero, 0($t0)
    addiu $t1, $t1, -1
    bnez $t1, @cz
    addiu $t0, $t0, 4
    la $t0, STRIP
    la $t1, PAL
    li $t2, 16
@cc:
    lhu $t3, 0($t1)
    addiu $t1, $t1, 2
    sh $t3, 2($t0)
    addiu $t2, $t2, -1
    bnez $t2, @cc
    addiu $t0, $t0, 32
    la $a0, RECT2
    sh $s1, 0($a0)
    addiu $t0, $s2, {ATLAS_H} - 4
    sh $t0, 2($a0)
    li $t0, 64
    sh $t0, 4($a0)
    li $t0, 4
    sh $t0, 6($a0)
    la $a1, STRIP
    jal LOADIMAGE
    nop
    jal DRAWSYNC
    move $a0, $zero
    lui $t0, %hi(DIRTY)
    sw $zero, %lo(DIRTY)($t0)
    lui $t0, %hi(INUP)
    sw $zero, %lo(INUP)($t0)
    lw $ra, 0x2c($sp)
    lw $s0, 0x20($sp)
    lw $s1, 0x24($sp)
    lw $s2, 0x28($sp)
    jr $ra
    addiu $sp, $sp, 0x30

; l2_key: battle-map button handler 0x80068840 (a1 = buttons held: it runs every frame
; while one is down), its exit for buttons it ignores (0x80068864 j 0x80068948, v0 = 0
; already): L2 toggles the unit bars once per press
l2_key:
    li $t0, 1
    bne $a1, $t0, @out
    lui $t1, %hi(L2HELD)
    lw $t2, %lo(L2HELD)($t1)
    li $t0, 2
    bnez $t2, @out
    sw $t0, %lo(L2HELD)($t1)
    lui $t1, %hi(HPON)
    lw $t2, %lo(HPON)($t1)
    nop
    xori $t2, $t2, 1
    sw $t2, %lo(HPON)($t1)
@out:
    j KEY_EXIT
    nop

; ba_wrap: replaces the overlay call (lui/ori/jalr at) in the battle-animation runner;
; a0-a2 pass through, no stack frame
ba_wrap:
    li $t1, 1
    lui $t0, %hi(INBA)
    sw $t1, %lo(INBA)($t0)
    lui $t0, %hi(SAVRA2)
    sw $ra, %lo(SAVRA2)($t0)
    lui $t0, %hi(BA_OVL)
    addiu $t0, $t0, %lo(BA_OVL)
    jalr $t0
    nop
    lui $t0, %hi(INBA)
    sw $zero, %lo(INBA)($t0)
    lui $t0, %hi(SAVRA2)
    lw $ra, %lo(SAVRA2)($t0)
    nop
    jr $ra
    nop

; ovl_wrap: replaces jal OVERVIEW at its two call sites. No stack frame (the callee's
; arguments stay where they are); not re-entrant.
ovl_wrap:
    li $t1, 1
    lui $t0, %hi(OVL)
    sw $t1, %lo(OVL)($t0)
    lui $t0, %hi(SAVRA)
    sw $ra, %lo(SAVRA)($t0)         ; before the jal (its delay slot already sees the new ra)
    jal OVERVIEW
    nop
    lui $t0, %hi(OVL)
    sw $zero, %lo(OVL)($t0)
    li $t1, 1                       ; its picture covered home S
    lui $t0, %hi(DIRTY)
    sw $t1, %lo(DIRTY)($t0)
    lui $t0, %hi(SAVRA)
    lw $ra, %lo(SAVRA)($t0)
    nop
    jr $ra
    nop
'''


def code2_src():
    (px, py, ptp), (sx, sy, stp) = HOMES
    return CODE2_ASM.format(
        P_X=px, P_Y=py, P_Y1=py + ATLAS_H, P_TP=ptp << 16, P_CLUT=((py + ATLAS_H - 4) << 6) | (px >> 4),
        S_X=sx, S_Y=sy, S_TP=stp << 16, MAP_X=MAP_AREA[0], MAP_Y=MAP_AREA[1],
        ATLAS_H=ATLAS_H, CELLS=CELLS)


PROF_ASM = r'''
; ---------------------------------------------------------------- profiles
; replaces 'jal 0x80010780' (load the whole PROFILE.E3) at 0x80080EF0 in the profile
; loader 0x80080E9C: a0 name, a1 0x801A8000, a2 0x31000, s0 = variant index. The
; rebuilt PROFILE.E3 (tools/insert_ui.py) holds one 2048-byte sector per variant:
; read sector s0 only, then clear s0 so the '$' skip loop does nothing.
prof_load:
    addiu $sp, $sp, -0x20
    sw $ra, 0x1c($sp)
    sw $a1, 0x18($sp)
    jal FILE_INDEX
    nop
    bltz $v0, @pdone
    sll $t0, $v0, 1
    addu $t0, $t0, $v0
    sll $t0, $t0, 3
    la $t1, FAT_TABLE
    addu $t0, $t0, $t1
    lw $a1, 0x10($t0)
    lw $a0, 0x18($sp)
    addu $a1, $a1, $s0
    jal READ_SECTORS
    li $a2, 0x800
@pdone:
    move $s0, $zero
    lw $ra, 0x1c($sp)
    nop
    jr $ra
    addiu $sp, $sp, 0x20
'''

TOWN_ASM = r'''
; ---------------------------------------------------------------- world-map town label
; replaces the x of the town label in 0x80024BDC (s1 = cursor column, s2 = town index):
; the game centred by strlen in 8 px cells (x = (col - len/2) * 8 + 4, 16 / 252 at the
; edges); centre on the VWF width instead and keep the label on screen (8 .. 312)
town_x:
    la $t0, TOWN_NAMES
    sll $t1, $s2, 2
    addu $t0, $t0, $t1
    lw $t0, 0($t0)
    move $t2, $zero
    la $t3, FONT_MET
@tw:
    lbu $t1, 0($t0)
    addiu $t0, $t0, 1
    beqz $t1, @tdone
    addiu $t1, $t1, -0x20
    sltiu $t4, $t1, 96
    bnez $t4, @tasc
    sll $t1, $t1, 2
    b @tw
    addiu $t2, $t2, 6         ; SJIS byte: half of a 12 px glyph
@tasc:
    addu $t1, $t1, $t3
    lbu $t1, 1($t1)
    b @tw
    addu $t2, $t2, $t1
@tdone:
    sll $v0, $s1, 3
    addiu $v0, $v0, 4
    srl $t4, $t2, 1
    subu $v0, $v0, $t4
    slti $t4, $v0, 8
    beqz $t4, @tright
    nop
    li $v0, 8
@tright:
    addu $t4, $v0, $t2
    slti $t4, $t4, 313
    bnez $t4, @tret
    nop
    li $v0, 312
    subu $v0, $v0, $t2
@tret:
    jr $ra
    nop
'''

SAVE_ASM = r'''
; ---------------------------------------------------------------- save list lines
; The save list (0x80015AE0, one call per slot) splits a save title (<= 64 bytes) at
; the marker E0474 (0x8012410C): line 1 = up to and including the marker, line 2 = the
; rest, each copied by strncpy into a 40-byte stack buffer (sp+0x38; saved s0.. at
; sp+0x60). English line 1 ('Motonari 1:Ep. 8: A Million Hearts as One, ') is up to
; 45 bytes: the copy overwrote the saved registers of the slot loop, which then drew
; the list forever ('Now checking the Memory Card' froze) or broke off saving.
;
; desc_find replaces strstr(title, marker) at 0x80015C14: finds ', ' (English titles)
; or 』 (SJIS 0x8178, titles saved by the Japanese game); both are 2 bytes, as the
; caller adds strlen(marker) to the line length.
desc_find:
    move $v0, $a0
@ff:
    lbu $t0, 0($v0)
    nop
    beqz $t0, @fnone
    lbu $t1, 1($v0)
    sltiu $t2, $t0, 0x81      ; SJIS lead byte 0x81-0x9F / 0xE0-0xFC: skip the pair
    bnez $t2, @fasc
    sltiu $t2, $t0, 0xA0
    bnez $t2, @flead
    sltiu $t2, $t0, 0xE0
    beqz $t2, @flead
    nop
@fasc:
    li $t2, 0x2C              ; ', '
    bne $t0, $t2, @fnext
    li $t2, 0x20
    beq $t1, $t2, @fret
    nop
@fnext:
    b @ff
    addiu $v0, $v0, 1
@flead:
    li $t2, 0x81              ; 』
    bne $t0, $t2, @fskip
    li $t2, 0x78
    beq $t1, $t2, @fret
    nop
@fskip:
    beqz $t1, @fnone
    nop
    b @ff
    addiu $v0, $v0, 2
@fnone:
    move $v0, $zero
@fret:
    jr $ra
    nop

; desc_copy replaces strncpy(sp+0x38, src, n) at 0x80015C3C: copies at most 64 bytes
; to DESC_BUF instead and points s6 (the function's buffer register, restored by its
; epilogue) there, so the caller's NUL store (s6 + n) and the print (patched to use
; s6) go to DESC_BUF. A trailing ', ' (the English marker) is left out of line 1.
desc_copy:
    la $s6, DESC_BUF
    sltiu $t0, $a2, 65
    bnez $t0, @cok
    nop
    li $a2, 64
@cok:
    move $t1, $s6
    move $t2, $a2
@cc:
    beqz $t2, @cend
    nop
    lbu $t0, 0($a1)
    addiu $a1, $a1, 1
    sb $t0, 0($t1)
    addiu $t1, $t1, 1
    b @cc
    addiu $t2, $t2, -1
@cend:
    sltiu $t0, $a2, 2
    bnez $t0, @cnul
    addu $t1, $s6, $a2
    lbu $t0, -2($t1)
    lbu $t2, -1($t1)
    xori $t0, $t0, 0x2C
    xori $t2, $t2, 0x20
    or $t0, $t0, $t2
    bnez $t0, @cnul
    nop
    addiu $t1, $t1, -2
@cnul:
    jr $ra
    sb $zero, 0($t1)

; title_copy replaces strcpy(0x800FD108, title) when an episode starts (0x800240EC) and
; when a save is loaded (0x800165C0, from the save's 30-byte field, which has no NUL
; when the title fills it). The field is 30 bytes; 0x800FD128 starts a 0x960-byte data
; block. English captions ('Episode 21: Oath of the Three Arrows', 36 bytes) ran into
; it. Copies at most 29 bytes + NUL. The field is not displayed (only saved).
title_copy:
    li $t1, 29
@tc:
    lbu $t0, 0($a1)
    addiu $a1, $a1, 1
    beqz $t0, @tend
    nop
    sb $t0, 0($a0)
    addiu $t1, $t1, -1
    bnez $t1, @tc
    addiu $a0, $a0, 1
@tend:
    jr $ra
    sb $zero, 0($a0)
'''

PROFV_ASM = r'''
; ---------------------------------------------------------------- profile screen lines
; The profile screen 0x8008158C cut the loader's text (sp+0x20, lines padded to 24
; bytes) into 50 x 25-byte strings at sp+0x508. With 48-byte lines (loader patched) it
; prints straight from the loader buffer, which may then use sp+0x20 .. sp+0x9F0.
; prof_count(a0 text) -> v0 = number of lines - 1; clears the rest of the buffer, so
; lines past the end print nothing.
prof_count:
    move $v0, $a0
@pc:
    lbu $t0, 0($v0)
    nop
    bnez $t0, @pc
    addiu $v0, $v0, 1
    addiu $t2, $a0, PROF_BUFLEN
    addiu $t1, $v0, -1
@pz:
    sltu $t0, $t1, $t2
    beqz $t0, @pzd
    nop
    sb $zero, 0($t1)
    b @pz
    addiu $t1, $t1, 1
@pzd:
    subu $v0, $v0, $a0
    addiu $v0, $v0, -2
    bgez $v0, @pc2
    li $t1, PROF_LINE
    move $v0, $zero
@pc2:
    divu $v0, $t1
    mflo $v0
    jr $ra
    nop

; prof_line(a0 win, a1 line): print the line up to its last visible byte (spaces and
; the SJIS blank 0x8140 do not count; SJIS pairs stay whole), then paint spaces to the
; window's right edge: the opaque spaces erase a longer line drawn there before
; (scrolling), which 3 px VWF spaces in the padding did not.
prof_line:
    addiu $sp, $sp, -0x20
    sw $ra, 0x1c($sp)
    sw $s0, 0x10($sp)
    sw $s1, 0x14($sp)
    sw $s2, 0x18($sp)
    move $s0, $a0
    move $s1, $a1
    move $s2, $zero
    move $t0, $zero
@pf:
    sltiu $t1, $t0, PROF_LINE
    beqz $t1, @pp
    addu $t1, $s1, $t0
    lbu $t2, 0($t1)
    lbu $t3, 1($t1)
    beqz $t2, @pp
    li $t4, 0x20
    beq $t2, $t4, @pf
    addiu $t0, $t0, 1
    sltiu $t4, $t2, 0x80
    bnez $t4, @pv
    nop
    addiu $t0, $t0, 1
    li $t4, 0x81
    bne $t2, $t4, @pv
    li $t4, 0x40
    beq $t3, $t4, @pf
    nop
@pv:
    b @pf
    move $s2, $t0
@pp:
    beqz $s2, @pcl
    nop
    lbu $a1, 0($s1)
    move $a0, $s0
    jal PUTCHAR
    move $a2, $zero
    addiu $s1, $s1, 1
    b @pp
    addiu $s2, $s2, -1
@pcl:
    lw $t0, 4($s0)
    lw $t1, 0x10($s0)
    nop
    sltu $t0, $t0, $t1
    beqz $t0, @pe
    move $a0, $s0
    li $a1, 0x20
    jal PUTCHAR
    move $a2, $zero
    b @pcl
    nop
@pe:
    lw $ra, 0x1c($sp)
    lw $s0, 0x10($sp)
    lw $s1, 0x14($sp)
    lw $s2, 0x18($sp)
    jr $ra
    addiu $sp, $sp, 0x20
'''

CMP_ASM = r'''
; ---------------------------------------------------------------- stat comparison panel
; Item transfer / equip panel (0x80027B60, 0x80027DD4): for ATK, ACC, SPD at x = 48, 144, 240
; (or one stat at 48) the game
; prints printf(win, "%3u %3u", old, new) and draws an arrow sprite (0xB0 = / 0xB1 up /
; 0xB2 down, 0x80023B50) at x + 24..x + 32: the gap between two 3-digit numbers of 8 px
; cells. VWF digits are 6 px and spaces 3 px, so the new value slid under the arrow.
; cmp_nums replaces those printf calls: old value right-aligned to end at x + CMP_OLD_END,
; new value from x + CMP_NEW, the rest of the field (to x + CMP_END) blanked with opaque
; spaces (the panel is redrawn in place every frame).
cmp_nums:
    addiu $sp, $sp, -0x28
    sw $ra, 0x24($sp)
    sw $s0, 0x10($sp)
    sw $s1, 0x14($sp)
    sw $s2, 0x18($sp)
    sw $s3, 0x1c($sp)
    move $s0, $a0
    move $s1, $a2
    move $s2, $a3
    lw $s3, 4($s0)                  ; field x
    move $t0, $s1
    li $t1, 10
    move $t2, $zero
@cd:
    divu $t0, $t1
    mflo $t0
    bnez $t0, @cd
    addiu $t2, $t2, DIGADV          ; width of the old value
    addiu $a1, $s3, CMP_OLD_END
    subu $a1, $a1, $t2
    jal cmp_pad
    move $a0, $s0
    move $a0, $s0
    la $a1, CMP_FMT
    jal PRINTF
    move $a2, $s1
    move $a0, $s0
    jal cmp_pad
    addiu $a1, $s3, CMP_NEW
    move $a0, $s0
    la $a1, CMP_FMT
    jal PRINTF
    move $a2, $s2
    move $a0, $s0
    jal cmp_pad
    addiu $a1, $s3, CMP_END
    lw $ra, 0x24($sp)
    lw $s0, 0x10($sp)
    lw $s1, 0x14($sp)
    lw $s2, 0x18($sp)
    lw $s3, 0x1c($sp)
    jr $ra
    addiu $sp, $sp, 0x28

; Workshop item list (0x8006EE84): the bonus column prints printf(win, " %3u", v) at
; x = 128, then a '+' at 128 / 136 / 144 for 3 / 2 / 1 digits (the 8 px cell before the
; first digit); with 6 px digits the '+' covered them. num_r prints the value right-aligned
; to end at x + NUM_END and blanks the field up to x + 32; the '+' positions are patched to
; sit just before the first digit (vwf.patch_exe).
num_r:
    addiu $sp, $sp, -0x28
    sw $ra, 0x24($sp)
    sw $s0, 0x10($sp)
    sw $s1, 0x14($sp)
    sw $s3, 0x1c($sp)
    move $s0, $a0
    move $s1, $a2
    lw $s3, 4($s0)
    move $t0, $s1
    li $t1, 10
    move $t2, $zero
@nd:
    divu $t0, $t1
    mflo $t0
    bnez $t0, @nd
    addiu $t2, $t2, DIGADV
    addiu $a1, $s3, NUM_END
    subu $a1, $a1, $t2
    jal cmp_pad
    move $a0, $s0
    move $a0, $s0
    la $a1, CMP_FMT
    jal PRINTF
    move $a2, $s1
    move $a0, $s0
    jal cmp_pad
    addiu $a1, $s3, 32
    lw $ra, 0x24($sp)
    lw $s0, 0x10($sp)
    lw $s1, 0x14($sp)
    lw $s3, 0x1c($sp)
    jr $ra
    addiu $sp, $sp, 0x28

; Text box 0x8003F828 (script ops 0x28 narration / battle conditions, 0x2C scene goals; not
; mode 3, the caption box): the game sized it at 8 px per byte of the longest line and
; printed lines in 8 px columns. box_w(a0 text, lines split at LF) -> v0 = widest line in VWF
; pixels (bytes outside the font count 8), at most 288; the box is that + 32, centred, and
; lines start 16 px in (vwf.patch_exe).
box_w:
    move $v0, $zero
    la $t3, FONT_MET
@bl:
    move $t2, $zero
@bc:
    lbu $t1, 0($a0)
    addiu $a0, $a0, 1
    beqz $t1, @beol
    li $t4, 10
    beq $t1, $t4, @beol
    addiu $t1, $t1, -0x20
    sltiu $t4, $t1, 96
    bnez $t4, @basc
    sll $t1, $t1, 2
    b @bc
    addiu $t2, $t2, 8
@basc:
    addu $t1, $t1, $t3
    lbu $t1, 1($t1)
    b @bc
    addu $t2, $t2, $t1
@beol:
    sltu $t4, $v0, $t2
    beqz $t4, @bn
    nop
    move $v0, $t2
@bn:
    lbu $t1, -1($a0)
    nop
    bnez $t1, @bl
    nop
    sltiu $t4, $v0, 289
    bnez $t4, @br
    nop
    li $v0, 288
@br:
    jr $ra
    nop

; cmp_pad(a0 win, a1 x): opaque spaces from the window's x while it is below a1, then x = a1
cmp_pad:
    addiu $sp, $sp, -0x20
    sw $ra, 0x1c($sp)
    sw $s0, 0x10($sp)
    sw $s1, 0x14($sp)
    move $s0, $a0
    move $s1, $a1
@pl:
    lw $t0, 4($s0)
    nop
    slt $t0, $t0, $s1
    beqz $t0, @pe
    move $a0, $s0
    li $a1, 0x20
    jal PUTCHAR
    move $a2, $zero
    b @pl
    nop
@pe:
    sw $s1, 4($s0)
    lw $ra, 0x1c($sp)
    lw $s0, 0x10($sp)
    lw $s1, 0x14($sp)
    jr $ra
    addiu $sp, $sp, 0x20
CMP_FMT:
    .byte 0x25, 0x75, 0, 0
'''

NAMES_ASM = r'''
; ---------------------------------------------------------------- full names
; The profile header (0x800817CC) and the officer screen (0x80078868) print the name
; reading (half-width katakana, 15 bytes at +0x19 of the 80-byte character record,
; table 0x800E43C8) with printf(win, "%s", reading). full_name prints the English full
; name of that record instead: NAME_TAB = u16 n, n u16 record indices, n u16 offsets (from
; NAME_TAB) of their strings, an empty string, the strings (vwf.names_blob); records not
; listed print nothing.
full_name:
    la $t0, CHAR_TABLE + 0x19
    subu $t0, $a2, $t0
    li $t1, 0x50
    divu $t0, $t1
    mflo $t0                        ; record index
    la $t1, NAME_TAB
    lhu $t2, 0($t1)                 ; n
    addiu $t3, $t1, 2
    sll $t5, $t2, 1                 ; 2n: index entry -> its offset entry
@fl:
    beqz $t2, @none
    nop
    lhu $t4, 0($t3)
    addiu $t2, $t2, -1
    beq $t4, $t0, @found
    nop
    b @fl
    addiu $t3, $t3, 2
@found:
    addu $t3, $t3, $t5
    lhu $t4, 0($t3)
    la $a2, NAME_TAB
    j PRINTF
    addu $a2, $a2, $t4
@none:
    sll $t5, $t5, 1                 ; 4n
    addiu $t5, $t5, 2
    j PRINTF
    addu $a2, $t1, $t5              ; the empty string after the arrays
    .align 4
NAME_TAB:
    .incbin names
'''

STUB = r'''
; new entry point: copy code to kernel RAM and the font to the stack area, clear the
; records, flush I-cache
stub:
    la $t0, SRC_A
    la $t1, CODE_ADDR
    li $t2, WORDS_A
@ca:
    lw $t3, 0($t0)
    addiu $t0, $t0, 4
    addiu $t2, $t2, -1
    sw $t3, 0($t1)
    bnez $t2, @ca
    addiu $t1, $t1, 4
    la $t0, SRC_B
    la $t1, FONT_ADDR
    li $t2, WORDS_B
@cb:
    lw $t3, 0($t0)
    addiu $t0, $t0, 4
    addiu $t2, $t2, -1
    sw $t3, 0($t1)
    bnez $t2, @cb
    addiu $t1, $t1, 4
    la $t0, SRC_C
    la $t1, CODE2_ADDR
    li $t2, WORDS_C
@cc:
    lw $t3, 0($t0)
    addiu $t0, $t0, 4
    addiu $t2, $t2, -1
    sw $t3, 0($t1)
    bnez $t2, @cc
    addiu $t1, $t1, 4
    la $t1, RECS
    li $t2, NRECS * 2
    li $t3, -1
@cl:
    sw $t3, 0($t1)
    addiu $t2, $t2, -1
    bnez $t2, @cl
    addiu $t1, $t1, 4
    li $t2, 0xA0              ; FlushCache()
    jalr $t2
    li $t1, 0x44
    j ORIG_ENTRY
    nop
    .align 16
SRC_A:
    .incbin a
SRC_B:
    .incbin b
SRC_C:
    .incbin c
'''


def symbols():
    s = dict(GAME)
    s.update(RECS=RECS, NRECS=NRECS, NRECS_MASK=NRECS - 1, FONT_MET=FONT_ADDR, FONT_ROWS=FONT_ADDR + 96 * 4,
             STRIP=STRIP, CELLS=CELLS, CELL_H=CELL_H, MAXQ=MAXQ, OVERVIEW=OVERVIEW, BA_OVL=BA_OVL,
             KEY_EXIT=0x80068948, DISPLAY_LIST=0x80010F78, SCRIPT_NO=0x800F45EF, MAPQ=0x800BE288,
             UNITS=0x800FE068, OFFICERS=0x800E43C8, MAXEND=0x80017DE4, MAXSP=0x80017E24, HPPRI=8,
             HP_BG=0x60181010, HP_HI=0x6040D040, HP_MID=0x6030C8E8, HP_LO=0x603040E8, HP_SP=0x60F09040,
             EN_BG=0x60101048, EN_HI=0x60289828, EN_MID=0x602090C0, EN_LO=0x602020A8, EN_SP=0x60D058A0)
    return s


def build_code2():
    """-> (code, labels) of CODE2_ASM at CODE2_ADDR"""
    code, labels = assemble(code2_src(), CODE2_ADDR, symbols())
    assert CODE2_ADDR + len(code) <= CODE2_END, 'CODE2 too large: %d bytes' % len(code)
    return code, labels


def build_code(dict_blob=b'', profile=False, town=False):
    import dte
    src = ASM + (PROF_ASM if profile else '') + (TOWN_ASM if town else '')
    syms = symbols()
    _, labels2 = build_code2()
    syms.update({k: labels2[k] for k in ('DIRTY', 'OVL', 'QV0', 'QCLUT', 'QTP', 'HPON', 'L2HELD', 'dirty2', 'upload2')})
    code, labels = assemble(src, CODE_ADDR, syms, {'dict': dict_blob or dte.blob([])})
    assert CODE_ADDR + len(code) <= 0x80010000, 'hook code too large: %d bytes' % len(code)
    return code, labels


def ui_pool_addr():
    """After the font: relocated UI strings (tools/insert_ui.py)."""
    return FONT_ADDR + ((96 * 4 + 96 * 48 + 3) & ~3)


def ui_pool_capacity():
    return SAVE_ADDR - ui_pool_addr()


def names_blob(names):
    """names: 800 x (str or None) -> NAMES_ASM table: u16 n, n u16 record indices, n u16
    string offsets (from the table start), an empty string, the NUL-terminated strings"""
    used = [(i, n) for i, n in enumerate(names) if n]
    head = 2 + 4 * len(used)
    strs, data = {}, bytearray(1)           # the empty string first
    for i, n in used:
        if n not in strs:
            strs[n] = head + len(data)
            data += n.encode('ascii') + bytes(1)
    return (struct.pack('<H', len(used)) + struct.pack('<%dH' % len(used), *[i for i, n in used])
            + struct.pack('<%dH' % len(used), *[strs[n] for i, n in used]) + bytes(data))


def patch_exe(exe, dict_blob=b'', ui=None):
    """ui (tools/insert_ui.py Build.engine): 'desc_cap' raise the item / skill description
    cut from 80 to 100 bytes; 'profile' sector-per-variant PROFILE.E3 reader; 'profile_fmt'
    0x8140 markers in the format profiles; 'pool' relocated strings (copied after the font);
    'town_label' world-map town labels centred by their VWF width; 'save_desc' save-list
    lines split at ', ' or 』 and copied without the 40-byte stack buffer, episode title
    field copies bounded to its 30 bytes (SAVE_ASM).
    Without ui the output is exactly the plain VWF build."""
    ui = ui or {}
    exe = bytearray(exe)
    pc, gp, taddr, tsize = struct.unpack_from('<4I', exe, 0x10)
    assert (pc, taddr, tsize) == (ORIG_ENTRY, 0x80010000, ORIG_TSIZE), 'unexpected MAIN.EXE'
    code, labels = build_code(dict_blob, profile=bool(ui.get('profile')), town=bool(ui.get('town_label')))
    met, rows = build_font()
    font = met + rows
    font += bytes((-len(font)) % 4)
    assert FONT_ADDR + len(font) == ui_pool_addr()
    if ui.get('pool'):
        font += ui['pool'] + bytes((-len(ui['pool'])) % 4)
    assert FONT_ADDR + len(font) <= SAVE_ADDR, 'font + UI string pool too large'
    save_labels = {}
    if ui.get('save_desc'):
        scode, save_labels = assemble(SAVE_ASM, SAVE_ADDR, {'DESC_BUF': DESC_BUF})
        font += bytes(SAVE_ADDR - FONT_ADDR - len(font)) + scode
        assert FONT_ADDR + len(font) <= FONT_END, 'save-list code too large'
    names_labels = {}
    bsrc = CMP_ASM + (PROFV_ASM if ui.get('profile') else '') + (NAMES_ASM if ui.get('full_names') else '')
    if bsrc:
        blob = names_blob(ui['full_names']) if ui.get('full_names') else b''
        ncode, names_labels = assemble(bsrc, NAMES_ADDR, {
            'CHAR_TABLE': 0x800E43C8, 'PRINTF': 0x8001BC3C, 'PUTCHAR': 0x8001AB40,
            'PROF_LINE': PROF_LINE, 'PROF_BUFLEN': PROF_BUFLEN, 'DIGADV': advances()[0x30],
            'FONT_MET': FONT_ADDR, 'CMP_OLD_END': 22, 'CMP_NEW': 34, 'CMP_END': 56, 'NUM_END': NUM_END}, {'names': blob})
        font += bytes(NAMES_ADDR - FONT_ADDR - len(font)) + ncode
        assert FONT_ADDR + len(font) <= NAMES_END, 'full-name table / profile code too large'
    import visited                      # battle map: ticked box on visited places
    font += bytes((-len(font)) % 4)
    vcode, visit_labels = assemble(visited.asm(), FONT_ADDR + len(font), visited.SYMBOLS)
    font += vcode
    assert FONT_ADDR + len(font) <= NAMES_END, 'visited-place code too large'
    code += bytes((-len(code)) % 4)
    syms = symbols()
    code2, labels2 = build_code2()
    code2 += bytes((-len(code2)) % 4)
    syms.update(CODE_ADDR=CODE_ADDR, FONT_ADDR=FONT_ADDR, WORDS_A=len(code) // 4, WORDS_B=len(font) // 4,
                CODE2_ADDR=CODE2_ADDR, WORDS_C=len(code2) // 4, ORIG_ENTRY=ORIG_ENTRY)
    body, _ = assemble(STUB, STUB_ADDR, syms, {'a': code, 'b': font, 'c': code2})
    body += bytes((-len(body)) % 0x800)

    def put(addr, words):
        o = 0x800 + addr - 0x80010000
        for i, w in enumerate(words):
            struct.pack_into('<I', exe, o + i * 4, w)

    def word(addr):
        return struct.unpack_from('<I', exe, 0x800 + addr - 0x80010000)[0]

    def jal(t):
        return 0x0C000000 | ((t >> 2) & 0x3FFFFFF)

    def j(t):
        return 0x08000000 | ((t >> 2) & 0x3FFFFFF)
    assert word(0x8001AE90) == jal(GAME['ORIG_DRAW'])
    put(0x8001AE90, [jal(labels['vwf_draw'])])
    assert (word(0x800A2D0C), word(0x800A2D10)) == (0x00805821, 0x00A06821)
    put(0x800A2D0C, [j(labels['s_hook']), 0])
    for addr in OVERVIEW_CALLS:                 # battle overview: no atlas while it runs
        assert word(addr) == jal(OVERVIEW), hex(addr)
        put(addr, [jal(labels2['ovl_wrap'])])
    # battle-animation overlay call: lui at, 0x801f / ori at, at, 0x8000 / jalr at (delay:
    # move a2, s4) -> nop / nop / jal ba_wrap (same delay slot)
    assert [word(BA_CALL + 4 * i) for i in range(4)] == [0x3C01801F, 0x34218000, 0x0020F809, 0x02803021]
    put(BA_CALL, [0, 0, jal(labels2['ba_wrap'])])
    assert word(0x80010D38) == jal(0x80010F78)                    # per-frame draw: display list
    put(0x80010D38, [jal(labels['hp_frame'])])                      # + unit bars (L2)
    assert (word(0x80068864), word(0x80068868)) == (j(0x80068948), 0)
    put(0x80068864, [j(labels2['l2_key'])])                         # battle map: L2 toggles them
    assert word(0x80010D40) == jal(visited.SYMBOLS['BG_LIST'])     # per-frame draw: BG list
    put(0x80010D40, [jal(visit_labels['visit_draw'])])
    for addr, lab, first in ((GAME['LOADIMAGE'], 'li_hook', (0x27BDFFE0, 0xAFB00010)),
                             (GAME['MOVEIMAGE'], 'mi_hook', (0x27BDFFE0, 0xAFB00010)),
                             (GAME['CLEARIMAGE'], 'ci_hook', (0x27BDFFD8, 0xAFB3001C))):
        assert (word(addr), word(addr + 4)) == first, hex(addr)
        put(addr, [j(labels[lab]), 0])
    # script text copier: bytes 0x20-0x7F were packed hiragana / punctuation; make them
    # plain ASCII (single byte copy at 0x8002081C); SJIS pairs and controls unchanged
    assert word(0x800207DC) == 0x2C820073 and word(0x80020834) == 0x90C30000
    put(0x800207DC, [0x2C820080])                   # sltiu v0, a0, 0x80
    put(0x80020834, [j(0x8002081C), 0])
    # dialogue window (0x8003E470): its line printer 0x8003DE8C cut lines after 26 / 28
    # bytes; English lines are broken by the inserter, so allow 80 (88-byte buffer)
    for addr, old in ((0x8003E984, 0x2407001A), (0x8003E9A4, 0x2407001C)):
        assert word(addr) == old, hex(addr)
        put(addr, [0x24070050])                     # addiu a3, zero, 80
    # bytes >= 0x80 in the copier -> dictionary hook (0xA0-0xDF) / SJIS pair
    assert word(0x800208EC) == 0x24C60001 and word(0x800208F0) == 0xA0A70000
    put(0x800208EC, [j(labels['dict_hook']), 0])
    if ui.get('desc_cap'):
        # item / skill info panels (0x800779BC, 0x80077E5C) read a 100-byte IMSG record
        # into sp+0x20 (the reader puts the NUL at sp+0x84) and cut it at 80 bytes with
        # 'sb zero, 0x70(sp)'; English needs the whole record: store at 0x84 instead
        for addr in (0x80077A58, 0x8007806C):
            assert word(addr) == 0xA3A00070, hex(addr)
            put(addr, [0xA3A00084])
    if ui.get('profile'):
        # profile loader 0x80080E9C: 'jal 0x80010780' read all of PROFILE.E3 (0x31000
        # bytes max) and skipped s0 '$' separators; the rebuilt file has one sector per
        # variant, prof_load reads sector s0 only and clears s0
        assert word(0x80080EF0) == jal(0x80010780)
        put(0x80080EF0, [jal(labels['prof_load'])])
        # lines of 48 bytes instead of 24 (192 px of English instead of ~130): the loader
        # pads each CRLF line to PROF_LINE bytes; the screen prints from the loader buffer
        # (PROFV_ASM) instead of copying 50 x 25-byte strings to sp+0x508
        for addr, old_w in ((0x80080FC8, 0x24060018),       # '//' line: a2 = 24
                            (0x80080FDC, 0x2CC20018),       # CRLF: pad while a2 < 24
                            (0x80080FF0, 0x2CC20018)):
            assert word(addr) == old_w, hex(addr)
            put(addr, [(old_w & 0xFFFF0000) | PROF_LINE])
        assert [word(a) for a in range(0x800815F8, 0x80081614, 4)] == [
            0x27A40508, 0x00002821, jal(0x800A903C), 0x240604E2, 0x27A40020, 0xAFA00A00, 0x00802821]
        put(0x800815F8, [0x27A40020, 0x00002821, jal(names_labels['prof_count']), 0,
                         0xAFA20A00, j(0x80081670), 0])     # sw v0, 0xa00(sp) = lines - 1
        assert word(0x800818DC) == 0x27B30508                # addiu s3, sp, 0x508
        put(0x800818DC, [0x27B30020])                        # addiu s3, sp, 0x20
        assert [word(a) for a in range(0x800818FC, 0x80081910, 4)] == [
            0x00022840, 0x00A22821, 0x000528C0, 0x00A22821, jal(0x8001BB74)]
        assert PROF_LINE == 48
        put(0x800818FC, [0x00022840, 0x00A22821, 0x00052900, 0,      # a1 = line * 48
                         jal(names_labels['prof_line'])])
    if ui.get('profile_fmt'):
        # format profiles (characters 48 / 49): after sprintf the text is re-padded at
        # SJIS 0x8142 (the Japanese full stop); English uses 0x8140 (blank) as the marker
        for addr, reg in ((0x800810DC, 3), (0x80081154, 10), (0x80081204, 10),
                          (0x80081374, 3), (0x800813EC, 10), (0x8008149C, 10)):
            assert word(addr) == 0x24000042 | (reg << 16), hex(addr)
            put(addr, [0x24000040 | (reg << 16)])
    if ui.get('town_label'):
        # world-map town label 0x80024BDC: the x computation (strlen in 8 px cells,
        # 0x80024CF4-0x80024D28) -> town_x (VWF width, clamped to the screen)
        assert (word(0x80024CF4), word(0x80024D28)) == (0x10400003, 0x24510004)
        put(0x80024CF4, [jal(labels['town_x']), 0, j(0x80024D2C), 0x00408821])   # delay: move s1, v0
    if ui.get('save_desc'):
        # save list 0x80015AE0: split at ', ' or 』 and copy lines into DESC_BUF (SAVE_ASM)
        assert word(0x80015C14) == jal(0x800A938C)          # strstr(title, marker)
        assert word(0x80015C3C) == jal(0x800A931C)          # strncpy(sp+0x38, title, n)
        assert word(0x80015C9C) == 0x27A50038               # addiu a1, sp, 0x38 (print)
        put(0x80015C14, [jal(save_labels['desc_find'])])
        put(0x80015C3C, [jal(save_labels['desc_copy'])])
        put(0x80015C9C, [0x02C02821])                       # move a1, s6
        # episode title field 0x800FD108 (30 bytes): bounded copies (SAVE_ASM title_copy)
        for addr in (0x800240EC, 0x800165C0):
            assert word(addr) == jal(0x800A920C), hex(addr)   # strcpy
            put(addr, [jal(save_labels['title_copy'])])
    if ui.get('full_names'):
        # name reading in the profile header / officer screen -> English full name
        for addr in (0x800817CC, 0x80078868):
            assert word(addr) == jal(0x8001BC3C) and word(addr + 4) == 0x26660019, hex(addr)
            put(addr, [jal(names_labels['full_name'])])
    # stat comparison panel (item transfer / equip): old and new value on either side of the
    # game's arrow sprite (CMP_ASM cmp_nums)
    # (0x80027BA4: one stat, e.g. DEF for armour; 0x80027DFC.. / 0x80027EF8..: ATK ACC SPD,
    # the two variants of the weapon panel)
    for addr in (0x80027BA4, 0x80027DFC, 0x80027E20, 0x80027E44, 0x80027EF8, 0x80027F1C, 0x80027F40):
        assert word(addr) == jal(0x8001BC3C), hex(addr)
        put(addr, [jal(names_labels['cmp_nums'])])
    # text box 0x8003F828 (ops 0x28 / 0x2C): width = VWF width of the widest line + 32,
    # centred, lines printed in pixels 16 px inside (CMP_ASM box_w)
    assert [word(a) for a in (0x8003F978, 0x8003F9A0, 0x8003F9A4, 0x8003F9C0)] == [
        0x32420001, 0x001210C0, 0x245E0020, 0xAFA20168]
    box, _ = assemble('''
    lui $a0, 0x8010
    jal BOXW
    addiu $a0, $a0, -0x2398
    addiu $fp, $v0, 0x20
    addiu $s5, $zero, 0x78
    andi $a0, $s3, 0xff
    addiu $v0, $a0, 1
    sll $v1, $v0, 4
    srl $v0, $fp, 1
    addiu $t1, $zero, 0xa0
    subu $v0, $t1, $v0
''', 0x8003F97C, {'BOXW': names_labels['box_w']})
    box += bytes(0x8003F9C0 - 0x8003F97C - len(box))
    put(0x8003F97C, list(struct.unpack('<%dI' % (len(box) // 4), box)))
    assert [word(a) for a in (0x8003FAC4, 0x8003FAD0, 0x8003FAD4, 0x8003FAE0, 0x8003FAE8, 0x8003FAEC)] == [
        0x240900A0, 0x00121042, 0x00A22823, 0x8FA90160, jal(0x8001A99C), 0x00A92821]
    put(0x8003FAC4, [0x8FA50168, 0])                       # lw a1, 0x168(sp) (box x)
    put(0x8003FAD0, [0x24A50010, 0])                       # addiu a1, a1, 16
    put(0x8003FAE0, [0])
    put(0x8003FAE8, [jal(0x8001A95C), 0])                  # x in pixels
    # workshop item list bonus column: value right-aligned (CMP_ASM num_r), '+' before it
    assert word(0x8006EE84) == jal(0x8001BC3C)
    put(0x8006EE84, [jal(names_labels['num_r'])])
    plus = advances()[0x2B]
    for addr, n in ((0x8006EEA0, 3), (0x8006EEB0, 2), (0x8006EEB4, 1)):
        assert word(addr) == 0x24050000 | (0x80 + 8 * (3 - n)), hex(addr)    # addiu a1, zero, x
        put(addr, [0x24050000 | (0x80 + NUM_END - advances()[0x30] * n - plus)])
    # caption box 0x8003F4E4 (script ops 0x29 / 0x2B): width and centring from the VWF
    # text width (cap_width) instead of 8 px per byte; lines up to 63 bytes (stride 0x40,
    # 9 lines in the 592-byte stack buffer; captions have 1-2); x in pixels
    for addr, old_w, new_w in ((0x8003F54C, 0x2C620026, 0x2C62003F),    # wrap after 63
                               (0x8003F574, 0x24C60027, 0x24C60040),    # line stride
                               (0x8003F664, 0x26520027, 0x26520040),
                               (0x8003F5E4, 0x001528C0, 0x02A02821),    # box x = s5 - 16
                               (0x8003F650, jal(0x8001A99C), jal(0x8001A95C))):  # x in px
        assert word(addr) == old_w, hex(addr)
        put(addr, [new_w])
    cap, _ = assemble('''
    nop
    addiu $s3, $s3, 1
    addiu $a0, $sp, 0x20
    jal CAPW
    move $a1, $s3
    srl $v1, $v0, 1
    addiu $s5, $zero, 160
    subu $s5, $s5, $v1
    sll $v1, $s3, 3
    addiu $s6, $zero, 0x78
    subu $s6, $s6, $v1
    addiu $s1, $v0, 0x20
''', 0x8003F5A0, {'CAPW': labels['cap_width']})
    assert len(cap) == 48 and word(0x8003F5D0) == 0x00138100       # sll s0, s3, 4
    put(0x8003F5A0, list(struct.unpack('<12I', cap)))
    exe = exe[:0x800 + ORIG_TSIZE] + body
    struct.pack_into('<I', exe, 0x10, STUB_ADDR)
    struct.pack_into('<I', exe, 0x1C, ORIG_TSIZE + len(body))
    return bytes(exe), {'code': len(code), 'font': len(font), 'code2': len(code2), 'labels': labels}


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    out, info = patch_exe(open(src, 'rb').read())
    open(dst, 'wb').write(out)
    print('code %d bytes, code2 %d bytes, font %d bytes ->' % (info['code'], info['code2'], info['font']), dst)
