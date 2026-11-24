# Text inventory

Disc: `Mouri Motonari - Chikai no Sanshi (Japan)` (SLPS-01285, Koei 1998).
Boot `SLPS_012.85` loads `cdrom:\MAIN.EXE;1`; data files are loaded by name
through `FAT_DATA.BIN` (245 x {name[16], LBA, size}). Extract with
`python tools/extract_iso.py "<bin>" work/source/disc`.

| File | Japanese (approx.) | Content | Tool / status |
| --- | --- | --- | --- |
| `DATA/R_00..29.EEX` | ~395k chars | story event scripts (town/castle scenes), per chapter part | `tools/eex.py`, `tools/extract_text.py` |
| `DATA/S_00..28.EEX` | ~45k chars | battle-map event scripts | same |
| `DATA/PROFILE.E3` | ~56k chars | character profiles (`//` comments, `$` variants, CRLF text) | `tools/extract_ui.py` / `insert_ui.py` (docs/text_formats.md) |
| `DATA/IMSG.E3` | ~13k chars | 994 x 100-byte records: item / skill descriptions, sortie / retreat / training quotes, battle names | same |
| `DATA/DATA.E3` | names | characters (`tools/names.py`), items (16 B), castles (8 B), skills (10 B) | same |
| `MAIN.EXE` | ~5.6k chars | menus, messages, format strings, lists, settings screen | same |
| `DATA/KFONT.BIN` | — | 2058 glyphs: 16x16 (32 B each) then 12x12 (18 B each) 1bpp; SJIS table at MAIN.EXE 0x800DC27C | replaced by the VWF for ASCII |
| `GRAPHIC/*.E3` | — | images (title logo, map labels may contain text graphics) | MARK.E3 label tiles (stats, columns) in English: `tools/mark_labels.py`; world-map province names (MMAP.E3 images 0-2, 33 labels) in English: `tools/map_labels.py`; MARK.E3 status icons 集 禁 深 不 混 凶 in English (RLY SEL WND BND CNF UNL, `tools/mark_labels.py`); duel panel icons 耐 / 技 (BA_BACK.BIN) as En / SP: `tools/duel_icons.py`; sortie screen buttons 出陣 / 選択終了 (MARK.E3) as "GO!" / "DONE" (0.2.19, `tools/mark_labels.py`); the title picture (LOGO.E3 at 0x13000, raw 320x240 16-bit) gets the version and github.com/retro-trans in its bottom-right corner: `tools/title_label.py` (0.2.20); the 船 label on a battle-animation unit (BA_UNIT.BIN graphics 30-32) as SHIP: `tools/unit_labels.py`; still Japanese: the 英傑伝シリーズ logo, the title logo; others not surveyed |
| `MOVIE/*.STR` | speech + burned-in labels | FMV (MDEC 320x240 15 fps + XA); MOVIE01 = opening film after New Game | MOVIE01 subtitled, labels replaced: `docs/movies.md` |

Script text: 12,403 strings, 7,289 unique (`work/source/text/units.json`):
6,499 dialogue (op 0x27), 517 titles/captions (op 0x29/0x2A/0x2B),
184 labels (op 0x2C/0x28: scene menus, battle conditions, narration),
84 choice lists (op 0x12).

## EEX format (`tools/eex.py`)

`"EEX\0"`, version 1.2, chunk list (type 0 ends), u32 event offsets; event =
u16 block count, blocks of `u16 size, condition ops … op 0000, u16 size2,
action ops`. Ops: u16 opcode + tagged args (u16 tag; tag 4 → u32, tag 5 →
NUL-terminated string, else u16; reader type 1 = raw u16). No absolute jumps,
but nested IFs: op 0001, a condition op, a raw u16 body length, the body (ending
with op 0000); the VM skips the body by that length when the condition fails.
Strings can change length when the event table, block size, size2 and every IF
length around them are fixed: `tools/eex_ops.py` parses all 5,996 blocks op by op
(signatures of the 79 ops from the VM handlers) and the rebuilder fixes all of
them (before 0.2.6 only size and size2 were fixed). All 59 files round-trip
byte-identically.

Dialogue window: 14 full-width characters (168 px) per line, 3 lines per page
(auto paging; Japanese pads pages with blank lines). Speaker sections start
with `&Name` (character table lookup → portrait + blue name box).
