# VWF and 2x-density ("4x") text font — MAIN.EXE

Generator: `tools/vwf.py` (called by `tools/build.py`). Same approach as the
Riot Stars translation: Skies of Arcadia's Latin font (12x24 glyphs, decoded
from the user's own Skies disc by `tools/skies_font.py` into
`work/source/skies_font.png`, never committed), drawn as POLY_FT4 quads at
half size, so upscaling emulators show the full 2x detail and 1x looks like a
crisp 6x12 proportional font.

## How the game draws text

* `0x8001AB40` put-char(win, byte, mode): SJIS lead bytes, ESC sequences, `\n`;
  draws via `0x8001B9B8` → `0x8001B5C8` (KFONT.BIN 16x16 at offset 0, 12x12 at
  0x10140, 2058 glyphs, table of SJIS codes at 0x800DC27C, binary search) →
  `0x8001B2F4` → blitter `0x8001031C` into the **320x240 4bpp RAM canvas**
  at `0x8019A000` (blit mode 0 opaque / 4 transparent, any x). Advance: 12/16 px
  full width, 8 px single byte. Window struct: +0 flags (0x80 12 px font,
  0x40 double, 0x20 vertical, low nibble blit mode), +4 x, +8 y, +0x10 x max,
  +0x1C line start x, +0x24 line gap. Text colour = `gp+0x169`.
* The canvas is uploaded to VRAM (384,0) by `0x8001B1BC` and shown by two
  GsSPRITEs (tpage 6 and 7, CLUT 320,240; RAM 0x800BE238 / 0x800BE260) through
  GsSortFastSprite `0x800A2D0C`. The game redraws only when the screen changes.
* Script text (EEX op 0x27 dialogue etc.) goes through the copier `0x800207B4`,
  where bytes 0x20–0x72 were packed hiragana and 0x73–0x76 punctuation.
  **Patched**: 0x20–0x7F are now copied as plain ASCII.

## Hooks (kernel RAM, copied by the entry stub appended to MAIN.EXE)

| Where | What |
| --- | --- |
| `0x8001AE90` jal → `vwf_draw` | bytes 0x20–0x7F: in opaque blit mode (`gp+0x168 & 15 == 0`, as the original glyph blit 0x8001B2F4) first paint the advance × 12 cell in the background colour `gp+0x16A`, so numbers re-printed in place (battle HP counters) leave nothing behind; then write a hidden 1x *underlay* into the canvas (the 1x pixels whose four 2x texels are all ink, plus one marker pixel — always covered by the quad), add a record {x, y, glyph, colour} to the hash table `RECS` (512 x 8 bytes at 0x8000B800) after dropping every record whose cell the new glyph's cell overlaps (text drawn over older text; an old record whose underlay happened to be covered by the new glyphs stayed live and showed a stray letter, fixed in 0.2.10), and correct the window's x advance to the glyph's width. Other codes → original. |
| `0x800A2D0C` GsSortFastSprite → `s_hook` | for the canvas sprites: before the sprite is linked, one POLY_FT4 per *live* record in the sprite's canvas rect (quads linked first are drawn after the sprite = on top). A record is live while the canvas still holds its underlay (all underlay pixels = colour, and at most half of the other pixels of the cell = colour: gradient or dithered boxes such as the highlighted save slot share the text colour in a few pixels, which killed letters before 0.2.10), so text survives window save/restore and disappears when cleared. Validity is one bit per record (`VBITS`), computed by `revalidate` when the game uploads the canvas (`li_hook`, main thread); the sort only visits the set bits. The game sorts these sprites from its VSync callback (interrupts off): checking records there starved the CD interrupt in rain (the battle animation hung loading BA_BACK.BIN, 0.2.7) and, after each canvas upload (about every 4 frames), made the memory card's 8 KB writes fail (saving broke off after the header, fixed in 0.2.12). |
| LoadImage / MoveImage / ClearImage entries → `li_hook` / `mi_hook` / `ci_hook` → `dirty2` | picks the atlas home (see VRAM below) and marks the atlas dirty when the home changes or a game write covers it; the next canvas sprite sort re-uploads atlas + CLUTs (`upload2`, synchronously, LoadImage + DrawSync). A LoadImage over the canvas (384,0) recomputes `VBITS` (`revalidate`). |
| `0x80068904`, `0x80077284` jal 0x800665C4 → `ovl_wrap` | the battle overview (Select): `OVL` is set while it runs. Then `s_hook` draws no quads and uploads nothing, and `vwf_draw` writes plain 1x glyphs (texel (2x, 2y) of each 2x2 block, what a quad shows at 1x) into the canvas with no record, so the overview title is plain text even in upscaled rendering. On return the atlas is re-uploaded. |
| `0x80086364` lui/ori/jalr at (overlay 0x801F8000) → `ba_wrap` | battle animations and training duels: `INBA` is set while the overlay runs. |

Memory (since 0.2.13): records 0x8000C000–0x8000D000 (kernel RAM, cleared by the entry
stub; zero under SCPH-1001 and SCPH-10000 in every sample), font (96 x {w2, adv, marker x,
y} + 96 x 24 u16 rows) from 0x801FB000, then the UI string pool, save-list code (`SAVE_ASM`)
at FONT_END − 0x140, save-list line buffer at FONT_END (= 0x801FC800), profile-screen and
full-name code + table (`PROFV_ASM`, `NAMES_ASM`) from 0x801FC880, then the battle-map
visited-place code (`tools/visited.py`, 588 bytes, 0x801FDDA0 in 0.2.16) up to 0x801FE000
(16 bytes left), all copied with the font. 0x801F8000–0x801FB000 belongs to the battle-animation overlay
(OVL/BA_OVL.BIN, 0x3000-byte pieces read by 0x80086340 and run there; training duels and
battle attacks). The records and font were there in 0.2.11–0.2.12: the overlay wiped them
and `rec_valid` crashed on a garbage record. `rec_valid` now treats a record outside the
canvas or with a glyph ≥ 96 as dead. The stack (STACK = 801fff00) reached 0x801FE850 in a
player's session, so keep 2 KB above the data. Code 0x8000EB80–0x80010000 (0x8000EF00 until
0.2.16) and the upload strip 0x8000E600–0x8000EB80 (1408 bytes since 0.2.17) stay in the kernel heap, after the TCBs / EvCBs (0xA000E000–0xA000E59C
with this game's SYSTEM.CNF on every BIOS). Kernel RAM 0x8000B000–0x8000BF00 holds BIOS
data on some BIOS versions (SCPH-1001: boot path, memory card directory; the PS3 ps1_rom:
0x8000B000–0x8000B800); the records were there until 0.2.10 and crashed SCPH-1001 at boot.
0x8000DF00–0x8000E600 belongs to the BIOS. Since 0.2.17 a second code block (`CODE2_ASM`:
atlas state words, `dirty2`, `upload2`, `ovl_wrap`, `ba_wrap`; 1288 bytes) is copied to
0x8000D980–0x8000DF00 (the main block had 32 bytes left; 0x8000D000–0x8000DF00 was still all
zero in a player's savestate after hours of play, SCPH-1001). `tools/gdbdbg.py` uses
0x8000D000–0x8000D980 as scratch (StoreImage stub at 0x8000D960). Test with SCPH-1001 (ps-22a.bin), the BIOS players most often use; the project
emulator now boots with it.

VRAM (0.2.17): atlas 25 x 4 cells of 10x22 texels (glyph rows 2–23; rows 0–1 are empty
and no glyph is wider than 10), 64 x 88 halfwords, then 16 CLUTs (64 x 4; colour c at
x+16·(c mod 4), y+88+c div 4 = {0, canvas colour c}). Glyph i at u 10·(i mod 25),
v y+22·(i div 25); quads start one line lower (y+1, 11 lines high), so the result is the
same as the 12x24 cells before. Two homes:

* **P (960,72)**, texture page 15, y 72–163: free outside battles.
* **S (576,98)**, texture page 9, y 98–189 (the 0.2.15 spot, ending above the officer
  screen's unit sprites at (576,192)): used while the battle map picture is in VRAM.

The battle map picture (GRAPHIC/HMxx.E3: 768x480 8bpp + 512-byte palette, padded with zeros
outside the map) is uploaded by the map loader 0x8005622C as two halves, (640,32) and
(640,272), each 384x240 halfwords. It fills x 640–1023, so on maps 41+ tiles wide (16 px
tiles; Ep. 4–8, 10–17, 19–29; Ep. 1 is 36 wide, so its zeros hid the problem in every test) the
0.2.16 atlas at (960,72) was inside the map: the upload marked it dirty, the atlas went
back over the map, and the right part of the battle map showed the font sheet as a black
block with brown letters (a player's Ep. 8 savestate, 0.2.16). `dirty2` rules:

* a game write over P → `PBUSY` (the map loader, or any other owner of P) → home S;
* while `INBA`, a write into the map area (x+w > 640, y+h > 32) → P is free again → home P,
  and S is cleared to zero at the next upload (duel effects sample texture page 9, empty
  in the original). The game reloads the whole map after the animation (0x80086440 →
  0x8005622C), which moves the atlas back to S;
* while `OVL`, nothing is drawn from the atlas (the overview picture covers S).

The battle-animation background uses the same rect as the lower map half, so it cannot
be told apart by rect, hence the `INBA` wrapper. Checked on the player's Ep. 8 state
(`work/emulator/states/user_v0216_ep8_map.sav`, DuckStation 0.1-12777): after a replayed
map upload the map is clean, the atlas is at S, terrain boxes draw from it; the overview
picture is clean with a plain title, and text draws again after it closes. The animation
path was simulated (`INBA` set by hand + a write at (640,272)); a real battle animation was
not run. A cold boot (SCPH-1001) leaves the atlas at S: the title sequence writes over P.

x 960–1023, y 48–255 was empty in 101 saved VRAM dumps (castle, town, menus, profiles,
Ep. 1 map battle, battle animation, duel, title, movies); the game's effect sheet
(CHR_MARK.E3, loaded to (880,0) 140 x 32) ends at y 32 there. Earlier spots:
(972,360) until 0.2.7, under the battle background the game loads at (640,272) 384x240
(the re-uploaded atlas showed as font glyphs in the battle effects); (576,128) until
0.2.13, over the officer screen's unit sprite (20 x 52 at (576,192)); (576,72) until
0.2.15: duel effect sprites read texture page 9 below row 48, empty in the original
game, and showed pieces of the font (orange "d'ia", a large "456") after a skill hit.
The same spot was also inside the battle overview map (Select on the battle map): the game
uploads GRAPHIC/HMSxx.E3 (8bpp, map size × 5 px, 184x110 up to 240x200) to (520,0), i.e.
x 520–639, y 0–199, so the upload marked the atlas dirty, the atlas went back over the map
picture, and the overview showed the font sheet from map pixel (112, 72) to the corner (a
player's photo of the Koriyama overview, 0.2.15). Other overview sprites: unit markers 8x8
at (1018, 8·type), type 0–3 (`0x800400A0`), so y < 32; checked with 0.2.16, the Arita
overview draws cleanly and the atlas at (960,72) stays intact. (960,72) in turn was inside
the larger battle maps: fixed in 0.2.17 by the two homes above.

## Unit bars on the battle map (0.2.17)

L2 on the battle map shows or hides two bars at the bottom of every unit's cell:
Endurance (green above half, yellow above a quarter, red below) and SP (blue), current /
maximum as the unit window shows them. Off at power-on; the setting lasts until reset.

* `hp_frame` (main block) replaces `jal 0x80010F78` (display list) at 0x80010D38 in the
  per-frame draw. After the display list, if `HPON` is set, the overview is not running and
  the map is drawn this frame (battle script, display-list entry 1017 is a map quad, as
  `tools/visited.py`), it walks the unit array 0x800FE068 (90 x 36 bytes; +0 officer index
  into the records at 0x800E43C8, stride 0x50; +5 / +6 map x / y, 0xFF = not on the map;
  +0xB 2 = in the battle, 4 = defeated; +0x10 Endurance, +0x14 SP; +0x1C army number).
  Slots 0–29 are Motonari's side, allied armies included (Ep. 1 and Ep. 8 states); slots
  30–89 are the enemy and get a second colour set (0.2.18, table `HPCOL`: darker green /
  amber / red Endurance, violet SP, dark red frame). Maximum Endurance / SP: 0x80017DE4 / 0x80017E24 (officer record; base +
  item bonuses, capped at 999), the functions the unit window (0x80042D34, "End%4u/%3u",
  "SP %4u/%3u") uses. Three flat rectangles per unit on screen (frame 28x6 at cell (2, 17),
  bars 26 px wide, 2 high, at (3, 18) and (3, 21)), OT entry 8 (0.2.18; 0.2.17 used 6): one
  over the units (9), under the command icons (Attack / Skill / Items / Wait) and the windows (2).
* `l2_key` (CODE2) sits at the exit of the battle-map button handler 0x80068840 for
  buttons it ignores (0x80068864). The handler runs every frame while a button is held
  (a1 = buttons), so `L2HELD` (set by `l2_key`, counted down by `hp_frame`) lets a press
  toggle `HPON` once. L2 is free on the battle map (the handler uses L1, R1, Triangle,
  Triangle+R2, Square, Cross, Select, Start).
* Checked on the player's Ep. 8 state: bars on all units in view, partial bars and colours
  after lowering three units' values by hand, none over the overview, L2 again hides them.
  Not checked: hidden or ambushing enemy units (if the game keeps such units in the array
  with +0xB = 2, their bars would show). 0.2.18: the command icons and the "end all units'
  commands?" window cover the bars.

## Text encoding (scripts)

ASCII 0x20–0x7E with the VWF. Digits are tabular (same width) so game-made
numbers keep their columns. Space = 3 px. `&Name` speaker lines are looked up
in the character table (`0x80023AE0` → DATA.E3 records, strcmp on +0xC) for
the portrait, and shown in the name box without trailing digits. Translators
keep the Japanese `&` lines; the inserter replaces them with the English names
that `tools/names.py` also writes into DATA.E3 (max 12 bytes).

## Other patches (tools/vwf.py)

* `0x80010D40` (per-frame draw, `jal 0x800112D0`) → `visit_draw` (`tools/visited.py`):
  ticked boxes on visited places of the battle map, from a table chunk in each
  DATA/S_xx.EEX; see the module docstring.

* `0x8003E984` / `0x8003E9A4`: dialogue line cap 26 / 28 bytes → 80 (line printer
  `0x8003DE8C` copies one line into an 88-byte buffer). Other callers of the line
  printer (0x8003973C, 0x80039930: 20 bytes; 0x8006FFC0, 0x80086748: 26 bytes)
  are unchanged until their text is translated.
* `0x800208EC` (copier, bytes >= 0x80) → `dict_hook`: 0xA0–0xDF expand to the
  dictionary strings (`tools/dte.py`), other bytes copy an SJIS pair as before.
* UI text options (`patch_exe(..., ui=...)`, only with translations from
  `tools/insert_ui.py`; see `docs/text_formats.md`): `desc_cap` (0x80077A58 /
  0x8007806C item / skill description cut 80 → 100 bytes), `profile` (0x80080EF0 →
  `prof_load`: one PROFILE.E3 sector per variant; since 0.2.13 also 48-byte lines: the
  loader pads CRLF lines to 48 (0x80080FC8, 0x80080FDC, 0x80080FF0), the screen 0x8008158C counts
  lines with `prof_count` instead of copying 50 x 25-byte strings to sp+0x508, prints
  line n from sp+0x20 + 48n with `prof_line`, which stops at the last visible byte and then
  prints opaque spaces up to the window's right edge, so scrolling leaves nothing behind), `profile_fmt` (format-profile
  markers 0x8142 → 0x8140), `pool` (moved MAIN.EXE strings at 0x801FA780–0x801FAAC0,
  copied with the font), `town_label` (world-map town label 0x80024BDC: the x computation
  0x80024CF4–0x80024D28 → `town_x`, which centres the name on the town by its VWF width,
  x = col·8 + 4 − width/2, clamped to 8..312; the game used strlen in 8 px cells),
  `save_desc` (always with translated MAIN.EXE strings; code `SAVE_ASM` at 0x801FAAC0, copied
  with the font):
  * save list 0x80015AE0: each save title (≤ 64 bytes) is drawn as line 1 = up to and
    including the split marker (x 0x32) and line 2 = the rest (x 0x7A, 14 px lower), each
    copied into a 40-byte stack buffer. `desc_find` (replaces strstr at 0x80015C14) finds
    ", " (E0474, English titles) or 』 (saves made by the Japanese game); `desc_copy`
    (replaces strncpy at 0x80015C3C) copies ≤ 64 bytes to the 128-byte buffer 0x801FAC00,
    drops a trailing ", " and points s6 there; the print (0x80015C9C) uses s6. English
    line 1 is up to 45 bytes: before 0.2.12 it overflowed the stack buffer and the list
    redrew forever ("Now checking the Memory Card" froze).
  * episode title field 0x800FD108 (30 bytes, saved at offset 0x205 of the save; nothing
    displays it): `title_copy` (≤ 29 bytes + NUL) replaces strcpy when an episode starts
    (0x800240EC) and when a save is loaded (0x800165C0). English captions (up to 36
    bytes) ran into the 0x960-byte block at 0x800FD128.

## Known gaps

* Menus, item/skill names, profiles (MAIN.EXE, IMSG.E3, PROFILE.E3, DATA.E3) are in
  English (`docs/text_formats.md`); checked in the castle menus and the Ep. 1 battle.
  Stat labels and column headers are image tiles in GRAPHIC/MARK.E3, redrawn in English by
  `tools/mark_labels.py` (0.2.12; END, SP, ATK, DEF, INT, LUK, ACC, SPD, ...). The
  half-width katakana reading beside names (DATA.E3 +13, 15 bytes) stays in the data: the
  profile index groups characters by its first kana (A-O, Ka-Ko, ...). Where the game
  prints it (profile header 0x800817CC, officer screen 0x80078868, printf(win, "%s",
  record + 0x19)) the `full_names` option prints the English full name instead
  (`NAMES_ASM` `full_name`: record index = (a2 - 0x800E43E1) / 0x50, u16 offsets + strings
  from `tools/names.py full_names()`, 0x801FAC80-0x801FD000, copied with the font;
  nothing when the full name equals the name already shown).
* World-map province names are painted into the map images (GRAPHIC/MMAP.E3 images 0-2);
  since 0.2.15 they are redrawn in English by `tools/map_labels.py` (not VWF text).
* Native resolution (1x) shows only texel (2a, 2j) of each 2x glyph. Since 0.2.10 those
  texels hold a 1x font built from Skies (`native_texels` in `tools/vwf.py`): glyphs move
  one texel down so every top, stroke and baseline is sampled, a shown texel is also
  inked when 3 of its 2x2 block are, and thin glyphs ("(", ")") take 2 of 4. Before, letters
  had uneven heights at 1x ('a' and capitals one row taller, '.' like ','). Upscaled
  rendering keeps the Skies shapes (the other texels).
* Common heights (0.2.14, `normalize` in `tools/vwf.py`): Skies' digits, 'f', 'J', '!', '?'
  ran one or two 2x rows above the capitals and / or below the baseline, 'a', 'p', 'q'
  one row above the other short letters, '.' one row low. Those glyphs lose repeated
  rows of their straight parts (shape kept) and '.' moves up, so in 2x rows (after the
  one-texel shift) capitals, ascenders and digits span 3-21, short letters 8-21 and
  descenders end on 23. All glyphs now take the same shift. Advances are unchanged.
* Stat comparison panel (item transfer / equip, 0x80027B60 and 0x80027DD4): the game prints
  printf(win, "%3u %3u", old, new) at x = 48 / 144 / 240 and puts its arrow sprite (0xB0 =,
  0xB1 up, 0xB2 down, 0x80023B50) at x + 24, the gap in 8 px cells. Since 0.2.14 the seven
  printf calls (0x80027BA4, 0x80027DFC, 0x80027E20, 0x80027E44, 0x80027EF8, 0x80027F1C,
  0x80027F40) go to `cmp_nums` (`CMP_ASM`, copied with the font): old value right-aligned
  to end at x + 22, new value from x + 34, opaque spaces up to x + 56.
* Text box 0x8003F828 (every mode but 3, the caption box; seen with the Story goal
  text, op 0x2C, mode 4): sized at 8 px per byte of the longest line and printed in 8 px
  columns. Since 0.2.14 0x8003F97C–0x8003F9BC call `box_w` (`CMP_ASM`: widest line in
  VWF pixels, at most 288) and set width = that + 32, x = 160 − width / 2; lines are
  printed in pixels 16 px inside (0x8003FAC4–0x8003FAEC, 0x8001A95C).
* Op 0x28 text (narration, battle names, conditions) shows in the dialogue window
  0x8003E470 without a portrait: fixed box (32,64) 256 x 112, text area x 40..280,
  6 lines per page, lines via the line printer (80-byte cap). `tools/insert_text.py`
  re-wraps narration to 240 px and pads its parts to whole pages.
* Workshop item lists (0x8006EE84): the bonus column printed printf(win, " %3u", v) at
  x 128 and then '+' at x 128 / 136 / 144 (3 / 2 / 1 digits). Since 0.2.14 `num_r`
  (`CMP_ASM`) right-aligns the value to end at x 158 and blanks the field to x 160; the
  '+' x (0x8006EEA0, 0x8006EEB0, 0x8006EEB4) is 158 − 6·digits − 6.
* Caption box (script ops 0x29 / 0x2B, 0x8003F4E4): since 0.2.12 sized and centred by
  the VWF width of the widest line (`cap_width`) + 32 px, x in pixels (0x8001A95C); lines
  up to 63 bytes (buffer stride 0x40). The game used 8 px per byte, which limited English
  captions to 36 characters; now 288 px (`tools/insert_text.py` TITLE_PX).
* The outline style (window flag at 0x800C0A10 == 2, 16 px windows) draws
  English without the outline.
* Script buffer is 0x18000 bytes at 0x801A8000: the inserter warns when an
  English EEX grows beyond it (dictionary compression keeps them below).
