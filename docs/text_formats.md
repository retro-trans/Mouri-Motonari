# Menu, item, skill and profile text — formats and insertion

Tools: `tools/extract_ui.py` (analysis + units), `tools/insert_ui.py` (check, preview,
build), called by `tools/build.py`. Addresses are MAIN.EXE RAM addresses (file offset =
addr - 0x80010000 + 0x800). Everything below was found statically with `tools/mips.py`
and checked byte by byte; the profile reader was also run in DuckStation (see the end).

| Source | Units | Keys | What | Insertion |
| --- | --- | --- | --- | --- |
| `DATA/IMSG.E3` | 599 | `I0001…` | item / skill descriptions, sortie / retreat quotes, battle names, training-ground quotes | in place, fixed 100-byte records |
| `DATA/PROFILE.E3` | 642 (652 variants) | `P0001…` | character profiles | file rebuilt, one sector per variant + loader hook |
| `DATA/DATA.E3` | 491 | `D0001…` | item names (414), castle names (12), skill names (65) | in place, fixed fields |
| `MAIN.EXE` | 791 (890 places) | `E0001…` | menus, messages, format strings, lists | in place, or moved when every reference can be patched |

Character names (DATA.E3 records 0-799) stay with `tools/names.py`.

## Translator workflow

Input: `work/source/text/ui_slices/NNN.json` (80 units each, same order as
`ui_units.json`). Output: `work/translation/en/ui/NNN.json`, a list of
`{"key", "en", "note"}` like the script. Check and look at the result:

    python tools/insert_ui.py check [work/translation/en/ui/NNN.json]
    python tools/insert_ui.py preview I0001 P0005      # lines as laid out / as the game builds a profile

Unit fields: `key`, `kind`, `src`, `first` (where), `count`, `jp`, `context` (screen,
printer, pointer table, item names using a description...), and the limits:

| field | meaning |
| --- | --- |
| `max_bytes` | bytes the English may use (no terminator) |
| `max_lines` | lines |
| `line_px` | pixel width per line with the VWF (space 3 px, letters ~6 px) |
| `line_bytes` | bytes per line (line-printer caps, message boxes, profile lines) |
| `wrap` | `auto` / `profile`: write prose, the inserter word-wraps (a `\n` forces a break); `manual`: your line breaks are kept; `none`: one line |
| `px_from: "jp"` | width limit taken from the Japanese (screen geometry unknown): format specifiers are not counted on either side |
| `relocatable` | EXE only: `true` = the string may grow up to `max_bytes` (moved to free space), `false` = it must fit its original slot |

Rules checked: printable ASCII only; format specifiers (`%s`, `%d`, `%2d`, `%u`, `%w`,
`%3u`, a lone `%` in training quotes) identical and in the same order; byte / line /
pixel limits (specifiers counted at their expanded size: `%s` = 12 bytes / 72 px, numbers
5 digits, a lone `%` 16 bytes); no backslash; profiles: no `$`, `//` or tab (parser
controls). `%w` is game-specific (not handled by the window printf 0x8001A34C, which
knows `%d %s %c %u`, `-`, `0`, width, `.prec`, `l`): keep it as it is.

## IMSG.E3 (99,400 bytes = 994 records x 100)

No index: record *n* = bytes `n*100 … n*100+99`, Shift-JIS, NUL-terminated, Japanese
lines padded with full-width spaces (20 characters per description line, 13 per
balloon line). Opened as a file handle at boot (0x8003D1C4: `0x8002250C(0x800F9BA8,
"IMSG.E3")`) and never loaded whole: `0x800192F4(dst, n)` reads 100 bytes at offset
n*100 from the CD (`0x80022670`) into the caller's buffer and stores a NUL at dst[100].
Range wrappers:

| Records | Wrapper (bound) | Caller / printer | Kind, limits |
| --- | --- | --- | --- |
| 0-229 | direct, index = item byte +0x14 (DATA.E3 item record byte 20) | item panel 0x800779BC, window printf `%s`, line start x+0xC, x max x+0xF0 | `item_desc`: 2 lines of 228 px, 99 bytes |
| 256-320 | 0x80019344 (<0x41) | skill panel 0x80077E5C, same window | `skill_desc`: same |
| 331-386 | 0x8001936C (<0x39) | 0x800427C4 → 0x8006C184 → balloon 0x800865B4 → line printer, cap 26 | `sortie`: 26 bytes / 156 px per line, 3 lines |
| 391-446 | 0x80019394 (<0x39) | 0x80042810, same balloon | `retreat`: same |
| 451-481 | 0x800193BC (<0x1F; caller <0x1E) | 0x80069AC8 copies 30 bytes into the battle struct (+6) | `battle_name`: 29 bytes, 120 px (designer note in record 450: 10 full-width chars) |
| 655-837 | 0x80019434 (<0xB7), 9 callers 0x800333F0… | training balloon 0x8003957C → line printer, cap 20; lines split by a literal `\r` | `training`: 20 bytes / 120 px per line, 3 lines; a lone `%` is replaced at runtime |
| 330, 390, 450, 490, 510, 530 | — | — | `※…` designer comments |
| 491-503, 511-523 | 0x800193E4, 0x8001940C | no caller | base-map / room descriptions: unused, not extracted |
| 531-654 | 0x80019468, loop 0x8007B7E0 (40-byte copies) | sound-test menu | debug, not extracted |
| 230-254, 838-993 | — | — | `終端` (terminator) records; 255 is a designer comment |

Item / skill panels cut the record at 80 bytes (`sb zero, 0x70(sp)` at 0x80077A58 /
0x8007806C, buffer sp+0x20…sp+0x84): with descriptions translated, `tools/vwf.py`
(`desc_cap`) moves that store to 0x84(sp) (already the reader's NUL), so the whole
record (99 bytes + NUL) is shown. Two English lines of 228 px are ~80-85 bytes.
Line breaks: `\n` (0x0A; put-char 0x8001AB40 starts a new line), `\r` literal for
training quotes. Records never grow: the file size is unchanged. The put-char also
wraps by itself (character level, when x > x max), which is why the inserter pre-wraps.

## PROFILE.E3 (197,653 bytes)

Text file: CRLF lines; `//` starts a comment anywhere in a line (`//NNN name … reading`
owner headers, `//　第一話～第三話` chapter headers, designer notes); `$` ends a
variant; tab is ignored. 652 variants (`$` count; valid index < 0x28B).

Loader 0x80080E9C(id, out): variant = 0x8007C4E4(id) (character + story progress);
reads the whole file (`jal 0x80010780`, 0x31000 bytes max — only 3 KB of headroom) to
0x801A8000, skips `variant` `$`s and the rest of that line, then copies text into
`out`, padding every CRLF line with ASCII spaces to 24 bytes. The profile screen
0x8008158C passes `out` = sp+0x20 (1,256 bytes), cuts it into 24-byte lines (array of
50 x 25 bytes at sp+0x508) and shows 9 at a time (16 px font, x 0x5C…0x11C = 192 px,
y 0x38 + 18n), with scrolling. Original limits: 24 bytes and 192 px per line, 50 lines;
24-byte lines held only ~130 px of English. Since 0.2.13 (`tools/vwf.py` `profile`) lines
are 48 bytes: the loader pads to 48, the screen prints straight from `out` (up to 2,512
bytes, sp+0x20..sp+0x9F0), so English wraps at 192 px; limit 50 lines (the longest English
profile, Oda Nobunaga, has 36). Keep chapter tags short, e.g. `(Ep. 20)` at the end of a
sentence.

Characters 48 and 49 (ids 0x30 / 0x31, variants 88, 89, 649, 650): the text is a
sprintf format (`%s` twice = the officer who won six training bouts, 0x800F45F4/F6),
then re-padded at each `。` (SJIS 0x8142): up to the first, to the second padded to 24,
then each further one right-aligns to 12 / 36. Those loops stop only at a marker, so
English without it would overrun. Inserter: `%s` → `%-12s` (names are 12 bytes max, so
every name expands to exactly 12), lines pre-padded to 48 bytes, markers SJIS 0x8140
(blank) around the first line (44 bytes, 160 px: marker + line + marker = 48, which the
game's padding to multiples of 24 leaves as it is); `tools/vwf.py` (`profile_fmt`) changes the
six `addiu …, 0x42` compares (0x800810DC, 0x80081154, 0x80081204, 0x80081374,
0x800813EC, 0x8008149C) to 0x40. All four must be translated together (the check says so).

Insertion (any profile translated): PROFILE.E3 is rebuilt as 652 sectors, variant k =
`//\r\n` + body + `$\r\n` padded to 2,048 bytes (untranslated variants keep their
Japanese lines; comments dropped) — 1.3 MB, placed in OUTMOST.DAT padding by the
build. `tools/vwf.py` (`profile`) replaces the `jal 0x80010780` at 0x80080EF0 with
`prof_load` (kernel RAM): file index 0x80010938, LBA from the RAM file table
0x800AB36C (+0x10), read one sector at LBA + s0 with 0x800109C0, s0 = 0 so the `$`
skip does nothing. No size limit any more, and the loader touches 2 KB at 0x801A8000
instead of 193 KB. Verified in DuckStation on the test build: at a game load breakpoint,
prof_load returned the right sector for variants 0, 5, 88, 650, and the full loader
produced the Japanese profile of id 0 and the English test profile of id 187.

## DATA.E3 (64,213 bytes)

Loaded whole to 0x801A8000 at boot (0x80022944); section offsets in MAIN.EXE
0x800DC1E4: 0, 0xA8C0, 0xDEC3, 0xE50B, 0xE8A7, 0xED6F (end 0xFAD5).

| Offset | Records | Parser → RAM | Text |
| --- | --- | --- | --- |
| 0x0000 | 800 x 54 | 0x80018B30 → 0x800E43C8 (0x50 each) | name 13 (12 used), half-width kana reading 15 (14 used, sort key; not displayed as far as found): `names.py` |
| 0xA8C0 | 419 x 33 | 0x8001913C → 0x800F47B0 (0x22) | **item name** 17 (16 copied + NUL); byte 20 = IMSG description record |
| 0xDEC3 | 12 x 134 | 0x80019D6C → 0x800F7F58 (0xEC) | **castle / base name** 9 (8 copied) |
| 0xE50B | 32 x 28 | 0x80019074 → 0x800F3DC8 | numbers only |
| 0xE8A7 | 16 x 72 | 0x8001902C → 0x800F4148 | numbers only |
| 0xED6F | 65 x 49 | 0x80019E60 → 0x800F8A68 (0x31) | **skill name** 11 (10 copied) |

Fields are fixed (record sizes are hard-coded in the parsers and structs): item names
16 bytes, castle names 8, skill names 10. Pixel limits: longest Japanese name (items
72 px = the item panel field x+0x18…x+0x62; castles 48 px), skill panel field 64 px.
The inserter writes the field (NUL-padded) on top of the names.py result.

## MAIN.EXE strings

Region 0x800AC000-0x80125210 (BSS starts at 0x80125210: crt0 zeroes 0x80125210-
0x80145CF8, so the area after the original image — where the VWF entry stub is
appended — cannot hold strings). 908 Shift-JIS strings found (NUL-preceded or
4-aligned starts, valid SJIS/ASCII/`\n`), 11,282 bytes in the first 787 units. A second
pass also accepts half-width kana / punctuation (0xA1-0xDF: `｡` `｢` `｣`) and adds the
referenced strings the first pass missed as E0788-E0791 (keys after all other units, so
the existing keys did not move): `特技｢%s｣を覚えた` (2 places), a second inventory-full
question, the Workshop buy-and-make question and a `………｡`.

References: pointer words in data (tables such as 0x800BE760 save titles, 0x800DC200
settings, 0x80124A70 battle errors, 0x80101A80 attack quotes) and `lui`/`addiu`
pairs (no `$gp`-relative string references exist). A string is **relocatable** when
every reference is a pointer word or a `lui`/`addiu` pair that can be retargeted
alone (nothing between them touches the register, no branch lands between them, the
register is dead after the `addiu`); 608 units are, 179 must stay in place.

Slot (in place): string + NUL + the padding up to the next object (4-byte
alignment), so a 4-character label (8 bytes + NUL) has 11 bytes. Japanese is 2 bytes
per character, so most English menu text fits in place.

Free space for moved strings (`tools/insert_ui.py`): first the slots of other moved
strings and the unused tails of strings translated in place (neighbouring free slots
merged into one region; best fit, longest strings first), then a pool after the VWF
font, 0x801FA780-0x801FAAC0 (832 bytes since 0.2.12, the save-list code follows; in
kernel RAM 0x8000DB80-0x8000DF00 before 0.2.11, docs/VWF.md), copied there by the VWF entry
stub with the font. The build fails with a clear message if the pool is full. Every
move is printed (`ui: moved …`). Nothing points inside a slot: strings referenced
inside are skipped by the extractor.

Hand-checked lui/addiu pairs that the extractor's safety test rejects are listed in
`SAFE_PAIRS` (`tools/extract_ui.py`); limits measured in game or in the code replace
the Japanese-width estimate in `LIMIT_OVERRIDES`. The save title (E0065 + E0481/E0482 +
episode + E0066/E0067/E0483) is built in a 72-byte stack buffer; `insert_ui.py check`
checks the longest combination. The 57 world-map town labels (E0128-E0134,
E0499-E0548, pointer table 0x800DDD40) have 120 px / 16 bytes: with any of them
translated, `insert_ui.py` turns on the `town_label` patch (`docs/VWF.md`), which centres
the label on the town by its VWF width and keeps it on screen. The town positions are a
table at 0x800DDE24 (3 map variants, selected by the byte at 0x800F45EE, of 26 x
{col, row, town} in 8 px cells).

Printers (recognised from the call after the reference, used for the limits):

| Printer | Behaviour | Limits given |
| --- | --- | --- |
| window printf 0x8001BC3C / puts 0x8001BB74 | fixed position, no byte cap, wraps by itself at the window's x max | `label`: Japanese width |
| message box 0x8003F828 | splits at `\n`, box width = 8 px x bytes of the longest line + 32, centred | `msgbox`: 36 bytes per line (the box then fills the screen), lines +1 |
| balloons 0x800397CC / 0x8003957C, 0x8006FE74 / 0x800865B4 | line printer 0x8003DE8C: breaks at `\n`, literal `\r`, or the byte cap (20 / 26) | `balloon20` / `balloon26`: 20 / 26 bytes and 120 / 156 px per line |
| sprintf 0x800A9DFC | standard PsyQ (flags, width, `%-12s` work) | `format`: Japanese width |
| pointer-table entries | lists, menus, names | `table`: width of the widest entry of the table |

Line-printer caps were **not** raised: untranslated Japanese (sortie quotes, padded to
26 bytes) relies on the cap to wrap, and English lines fit 20 / 26 bytes. If longer
lines are wanted later, the caps are the immediates at 0x8003973C, 0x80039930 (20) and
0x8006FFC0, 0x80086748 (26); the line buffer is 88 bytes.

Width-based layout and full-width characters:
- ASCII is drawn by the VWF: space 3 px, digits tabular (~6 px). Strings centred with
  ASCII spaces (`        ゲームスタート`, `  聴く  `) counted 8 px per space before;
  in English pad with 3 px spaces or not at all.
- `%2d`, `%4u/%3u` pad with spaces (3 px) while digits are ~6 px: right-aligned numbers
  shift by 3 px per missing digit (cosmetic).
- Message boxes are sized by bytes at 8 px each, so English boxes come out wider than
  the text (left-aligned inside); the line printer's optional centring (x += (cap -
  strlen) x 4) also counts bytes.
- Japanese full-width digits/symbols in the formats (`１上がった`, `５０音順`, `￡`) become
  ASCII in English. The full-width digit table 0x800BE87C (`０`…`９`) is skipped data used
  for numbers; the save-screen strings may also feed the memory card title (not traced).

Skipped (left Japanese, listed in `work/source/text/ui_skipped.json`):
- developer / debug: `BUTAI::SetButaiColor()…`, `BUTAI::GetButaiColor()…`,
  `GetMoveType::…`, `GetMoveUsePts::…`, `地形効果を取得する部隊の種類がおかしいです…`,
  `敵武将設定ERROR…` (2), `戦闘部隊番号不正(%u)`, `攻撃キャラ番号不正(%u)`,
  `メッセージ "%s" の読み込みに失敗しました`, `メモリもしくはHDの空き容量が足りません` (2),
  `アニメ領域が足りなくなりました`, `移動範囲ではありません…ワープします。びゅーん`,
  `部隊がいるからいけへんでー！`, `０人プレイを抜けます`;
- debug menu tables 0x800FF810-0x800FF8E0 (movie / face / sound test: 22 strings);
- not referenced: `その部隊は実行できません`, `を覚えた` (2) and `庫に入れますか？` (tails of
  E0788 / E0789, whose real starts the second pass found),
  `毛利元就 誓いの三矢` and a few binary false positives;
- IMSG: sound-test names (123), unused base-map (12) and room (13) descriptions, the
  designer comment in record 255.
Library ASCII messages (CD/GPU/memory card libraries, `Memory Alloc Error`…) are not
Japanese and are not extracted.

## Engine patches (tools/vwf.py, only when the matching text is translated)

| Option | Words | Why |
| --- | --- | --- |
| `desc_cap` | 0x80077A58, 0x8007806C: `sb zero,0x70(sp)` → `0x84(sp)` | item / skill descriptions up to 99 bytes |
| `profile` | 0x80080EF0: `jal 0x80010780` → `jal prof_load` (+ prof_load in kernel RAM) | sector-per-variant PROFILE.E3 |
| `profile_fmt` | 6 x `addiu rX, zero, 0x42` → `0x40` at 0x800810DC… | 0x8140 markers in the 4 format profiles |
| `pool` | strings appended to the font blob (0x801FA780 since 0.2.11) | moved EXE strings |

Each patch asserts the original instruction words. With no file in
`work/translation/en/ui/` the build is byte-identical to the build without these
tools (checked: same .bin MD5).

## Test (v0.2.4 work in progress)

`work/source/ui_test.json` (12 units: 2 DATA names, 2 EXE strings — one in place, one
moved to the pool —, 3 IMSG records, 5 profiles including the 4 format ones): checker
clean; build OK; files read back from the .bin parse (IMSG records, DATA fields, 652
profile sectors through a Python model of the game's parser, EXE: `lui a0,0x8001 /
addiu a0,a0,-0x2480` → 0x8000DB80, pool text present in RAM after boot, prof_load
disassembled and run in DuckStation). To use it again copy it to
`work/translation/en/ui/` and build.

Needs an in-game check once real text exists: item / skill panels (2 lines, 99 bytes),
balloons (sortie / retreat / training), battle name banner, profile screen scrolling
and the format profiles (48 / 49, only after they join), message boxes sized by bytes,
lists using item / skill / castle names, the save screen and the memory card title.

## Changelog summary

- UI text tooling: `tools/extract_ui.py` (2,523 units: IMSG 599, PROFILE 642, DATA 491,
  EXE 791; 80-unit slices in `work/source/text/ui_slices/`, per-unit limits and context;
  debug strings listed, not extracted), `tools/insert_ui.py` (check / preview / build;
  IMSG and DATA in place, EXE strings in place or moved with all references patched to
  freed slots and an 896-byte kernel-RAM pool, PROFILE rebuilt one sector per variant),
  integrated in `tools/build.py`; no translations = identical build.
- `tools/vwf.py`: optional patches `desc_cap` (descriptions 80 → 99 bytes), `profile`
  (sector reader `prof_load`, removes the 0x31000-byte PROFILE.E3 limit; verified in
  DuckStation), `profile_fmt` (format profiles 48 / 49), `pool` (moved strings).
- `docs/text_formats.md`: formats, loaders, printers, limits, free space, skipped strings.
