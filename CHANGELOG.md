# Changelog

## 0.8.0 — first public release

First public release, same content as 0.2.20 (the title screen shows "v0.8.0").
- Release packaging: VCDIFF patch for the Japanese disc image (SLPS-01285), CUE sheet,
  checksums, build manifest and instructions (`tools/package_release.py`, VCDIFF encoder
  `tools/vcdiff.py`). GitHub social preview made with `tools/social_preview.py` from the
  Japanese box art (libretro-thumbnails, kept in the ignored `incoming/boxart/`).
- Repository: https://github.com/retro-trans/Mouri-Motonari. The translation files are
  committed as Japanese-free `.en.json` copies (`tools/strip_jp.py`); the working files,
  review reports, game data and builds stay out of git (`.gitignore`).

## 0.2.20 — project URL and version on the title screen

- **New:** the title screen shows the build version ("v0.2.20") and
  "github.com/retro-trans" in its bottom-right corner, in a small light-grey pixel font
  with a dark outline, under the right end of the copyright line. They are drawn into the
  title picture (GRAPHIC/LOGO.E3, raw 320x240 16-bit image at offset 0x13000) by
  `tools/title_label.py`; `tools/build.py` passes its `VERSION`, so every build shows its
  own number.
- Checked on a cold boot: `work/ui/shots/v0220_title_version.png`.
- Build: `work/output/test/MouriMotonari_0220.cue` (full translation; same program as
  0.2.18–0.2.19).

## 0.2.19 — sortie screen buttons

- **Translated:** the two buttons of the sortie screen (officer selection before a battle),
  which are pictures in GRAPHIC/MARK.E3: 選択終了 is now "DONE" and 出陣 "GO!" (as the
  pre-battle menu, E0701). The kanji filled the button, so the English uses 10-pixel bold
  capitals drawn in the kanji's style (white strokes, dark navy shadow, dark green outline
  on the green fill), `tools/mark_labels.py` (`BUTTONS`, `BIG`). Preview in the colours seen
  in the game: `work/ui/shots/sortie_buttons_preview.png`
  (`python tools/mark_labels.py buttons <out.png>`).
- Checked: after a cold boot of this build the sheet in VRAM (320,32) holds the new
  buttons. The sortie screen itself was not reached (no savestate before a battle's
  officer selection).
- Build: `work/output/test/MouriMotonari_0219.cue` (full translation; the program is the
  same as 0.2.18).

## 0.2.18 — enemy unit bars, bars under the command menu

- **Changed:** enemy units' bars (L2 on the battle map) use their own shades: darker green /
  amber / red Endurance, violet SP, on a dark red frame. Motonari's side, allied armies
  included, keeps green / yellow / red and blue on a dark frame.
- **Fixed:** the bars drew over the command icons (Attack / Skill / Items / Wait) when a
  unit's menu opened next to other units (player report, 0.2.17). They are now one layer
  above the units, under the command icons and every window.
- Checked in DuckStation on the Ep. 8 savestate (code loaded into it): both colour sets,
  the command menu and the "end all units' commands?" window over the bars.
  Comparison: `work/ui/shots/hpbars_0217_enemy_shade.png` (the font sheet at the right of
  the middle panel is from loading new code into an old savestate, not the build).
- Build: `work/output/test/MouriMotonari_0218.cue`. The first 0.2.18 image was built with
  `build.py --test`, which leaves out the translated menus and scripts: the title screen's
  load prompt and other menus were back in Japanese (player report). Rebuilt without
  `--test`; MAIN.EXE now differs from 0.2.17 only in the bar code. Checked on a cold boot:
  title, Continue, the load prompt ("Which one do you want to load?", Slot 1 / Temporary
  Memory) in English.

## 0.2.17 — font sheet over the larger battle maps, unit bars

- **New:** press L2 on the battle map to show or hide two bars under every unit:
  Endurance (green, turning yellow below half and red below a quarter) and SP (blue), as
  current / maximum like the unit window. Off when the game starts; stays as set until
  reset. Not drawn over the battle overview. Checked on the Ep. 8 savestate (values of
  three units lowered by hand to see partial bars and colours).
- **Fixed:** in the battles of Ep. 4–8, 10–17 and 19–29, the right part of the battle map showed the
  font sheet ("456789:;<=>?@ABCDEFG", "HIJKLMNOPQRSTUVWXYZ", ...) as a black block with brown
  letters (player report, Ep. 8, 0.2.16). 0.2.16 had moved the font into VRAM (960,72),
  which looked empty in every test, but each battle map's picture is loaded to x 640–1023:
  Ep. 1's map is narrow, so that spot only held zeros there, while maps 41 tiles wide or
  more (25 of the 29 battles; not Ep. 1–3, 9, 18) have terrain there. The font now has two spots: (960,72) outside battles, and the
  0.2.15 spot (576,98) while a battle map is loaded. While a battle animation or duel runs
  it goes back to (960,72), and the (576,98) spot is cleared, so the duel effects that
  showed stray letters before 0.2.16 still see an empty area. The font itself takes less
  room (10x22 cells instead of 12x24, same letters).
- **Changed:** while the battle overview (Select) is open, its title ("Interception in Bingo
  Turn 5/50") is plain text without the sharper upscaled letters: the overview picture
  covers the battle-map font spot. At native resolution it looks the same.
- Checked in DuckStation on the player's Ep. 8 savestate (0.2.17 code loaded into it, map
  picture uploaded again): the map is clean, the terrain box and the overview title draw
  correctly, and text draws again after the overview closes. The battle-animation switch
  was simulated, not seen in a real attack or duel. A cold boot (SCPH-1001) reaches the
  title menu; castle dialogue checked at the training ground.
- A savestate made with 0.2.16 keeps the 0.2.16 program: boot the 0.2.17 disc and load a
  memory card save to get the fix.
- Tools: a second hook block in kernel RAM (0x8000D980–0x8000DF00, `CODE2_ASM` in
  `tools/vwf.py`; the first was full) and the first block now starts at 0x8000EB80 (the
  upload buffer before it needs 1408 bytes, not 2304), copied by the entry stub and by `tools/hotload.py`;
  `tools/gdbdbg.py` scratch moved below it; `tools/emu.ps1` `MOURI_EMU=12777` selects a copy
  of DuckStation 0.1-12777, which reads newer savestates.

## 0.2.16 — kanji in battle graphics, stray letters in duel effects

- **Translated:** the 船 ("ship") label stamped over a mounted general in the battle and
  skill animations (GRAPHIC/BA_UNIT.BIN, unit graphics 30-32, all 10 frames). The game
  uses it to mark a unit fighting from a boat. `tools/unit_labels.py` restores the rider
  from the same sprite without the label (graphic 33) and draws "SHIP" in the label's
  colour. Preview: `work/ui/shots/skill_fx/v0216_ship_label_preview.png` (stand-in colours).
- **Translated:** the duel status panel's 耐 and 技 icons (GRAPHIC/BA_BACK.BIN) are now
  "En" (Endurance) and "SP" (Skill Points), drawn in the style of the game's own Lv / Ex
  icons (`tools/duel_icons.py`). Checked in DuckStation in a new training duel:
  `work/ui/shots/skill_fx/v0216_duel_icons.png`.
- **Translated:** the six status icons shown over units on the battle map (GRAPHIC/MARK.E3):
  集 RLY (Rally), 禁 SEL (Sealed), 深 WND (Wounded), 不 BND (Bound), 混 CNF (Confused),
  凶 UNL (Unlucky). They appear after skills such as Seal Art, Binding Art or the poison
  and fire arrows. 3 letters in a 4x7 font (`tools/mark_labels.py`). Preview only:
  `work/ui/shots/skill_fx/v0216_mark_status_preview.png`; not yet seen in a battle.
- **Fixed:** a duel skill hit could show pieces of the English font (orange "d'ia",
  purple "!", a large "456") around the units. Some duel effect sprites read texture
  page 9 below row 48, which is empty in the original game, and the font atlas was kept
  there (VRAM 576,72). The atlas and its colour tables moved to texture page 15
  (VRAM 960,72 and 960,248), which is empty in all 101 saved VRAM dumps (castle, town,
  menus, profiles, map battle, battle animation, duel, title, movies). Checked in
  DuckStation: town labels, the officer list and duel text draw from the new spot, and
  after a cold boot the old spot stays empty. The stray letters showed once and could not
  be reproduced, so their absence is not directly confirmed.
- **Fixed by the same move:** the battle overview map (Select on the battle map) could
  show the font sheet ("456789:;<=>?@ABCDEFG", "HIJKLMNOPQRSTUVWXYZ") as a blue block over
  its lower right part (player report, Koriyama, 0.2.15). The overview picture is uploaded
  to VRAM (520,0), up to 240x200 pixels, which covered the old font spot; the font was then
  put back over the map. The new spot is outside it. Checked on the Ep. 1 overview with
  this build; the Koriyama overview itself was not reached.
- Still Japanese in MARK.E3: the 出陣 / 選択終了 buttons of the sortie screen.
- **New:** visited places on the battle map get a small ticked box (dark box, green
  tick, light frame) in the top-right corner of their cell. This covers villages,
  houses, towns, storehouses, mines, shrines, found treasure spots and taken forts:
  455 places in the 29 battles. A place counts as visited once the game sets its own
  "visited" flag, which is what stops a second visit from giving the reward again. The
  box sits above the map and grid, below units, the cursor and windows.
  `tools/visited.py`:
  - Each battle script (DATA/S_xx.EEX) gets a table chunk listing its places
    (x, y, flag). The script VM skips unknown chunks.
  - A hook in the per-frame draw (0x80010D40) links the boxes into the ordering table.
  - The 588 bytes of code sit after the name table (0x801FDDA0–0x801FDFEC), leaving
    16 bytes before NAMES_END.
  - Checked in DuckStation on the Ep. 1 battle (code, hook and table put in by hand
    over GDB, on the 0.2.6 savestates): boxes on the villages, mines and castle town
    while scrolling, during the enemy phase's camera pans, under rain and under the
    action ring. Screens: `work/ui/shots/houses/` (v5.png, m78.png, m80z.png).
  - Not yet seen: a battle loaded from the built disc (no savestate with this build
    reaches one yet), and a real visit setting the flag.

## 0.2.15 — English province names on the maps

- **Translated:** the province names on the three world maps (the Chugoku map shown before
  battles, western Japan with Kyushu and Shikoku, and the Kinai). They are painted into
  the map pictures (GRAPHIC/MMAP.E3, images 0-2: 320x240, 256 colours each), so
  `tools/map_labels.py` erases each kanji label (refilled with the surrounding terrain)
  and paints the English name in the same light cyan with a dark outline, in the dialogue
  font scaled to the kanji size. 33 labels: Izumo, Iwami, Aki, Bingo, Suo, Nagato, Buzen,
  Bungo, Iyo, Echizen, Mino, Owari, Mikawa, Tajima, Inaba, Tanba, Hoki, Harima, Settsu,
  Yamashiro, Ise, Mimasaka, Bizen, Yamato, Bitchu, Kii (spellings as in the glossary,
  no macrons). A few labels on the crowded Kinai map are nudged clear of castles and of
  each other. Before / after: `work/ui/shots/map_labels.png`.
- Checked: the map file on the built disc matches the tool's output, and only the three
  map images changed (their colours are untouched). Not yet seen in DuckStation: no
  saved state is near a map scene.

## 0.2.14 — even letter heights

- **Fixed:** uneven letters in the English font, most visible upscaled. The source font
  (Skies of Arcadia) draws the digits, 'f', 'J', '!' and '?' one or two rows taller than
  the capitals or below the baseline, 'a', 'p' and 'q' one row taller than the other short
  letters, and '.' one row low. Those glyphs are now shortened by dropping repeated rows
  of their straight parts (shapes unchanged) and '.' moved up, so all capitals, digits and
  tall letters share one top and one baseline, and all short letters one top. Letter
  widths are unchanged, so no text moves.
- Checked in DuckStation at 3x: the officer screen's numbers (85, 140 / 140, 28 / 28)
  now stand as tall as the letters beside them.
- **Fixed:** the stat comparison in the item transfer / equip panel ("ATK 97 → 77") showed
  the new value under the game's arrow sprite, which also left a blue mark in the "no
  change" case ("DEF 56 56"). The game prints both values as "%3u %3u" in 8 px cells
  and draws the arrow in the gap at x + 24. With the narrower English digits the second
  value slid under it. The old value is now right-aligned before the arrow and the new
  value starts after it (all three panel variants: weapon panel with ATK / ACC / SPD,
  both menus, and the one-stat armour panel). Checked in DuckStation at 3x: "85 ↘ 65",
  "74 ↘ 39", "7 ↗ 37", "DEF 47 ↘ 42".
- **Fixed:** the workshop item lists showed a garbled "(+)" mark in the ATK / DEF column
  instead of the bonus ("+20"). The game prints the number as " %3u" and then a '+' in
  the 8 px cell before the first digit; with the narrower English digits the '+' landed
  on the number and cancelled its letters. The value is now right-aligned to the column
  and the '+' put just before it. Checked in DuckStation: swords "+20", "+15", bows
  "+20", "+15", armour "DEF +5".
- **Changed:** narration boxes (story summaries between scenes and before battles) now use
  their full width. The translation kept the Japanese line breaks, so English lines
  filled only about 190 of the 240 px. The inserter re-wraps narration to 240 px and
  pads each part to whole 6-line pages, as the Japanese blank lines did ("Invading
  Kikkawa Mototsune's lands..." now takes 5 lines instead of 6). Battle names and
  victory conditions keep their lines.
- **Changed:** the scene-goal box (Story: "See Lady Sugi") is sized from the English
  text and centred; the game sized it at 8 px per character.
- **Translation:** the 45 scene goals that had been shortened for the old box are written
  in full ("See Lady Sugi" -> "Talk to Lady Sugi", "Visit Okimoto's Res." -> "Go to Mouri
  Okimoto's Residence", "To quarters" -> "Go to the Living Quarters", full names instead
  of family or given names alone); the longest take two lines. Battle conditions in both
  boxes use full names too ("Make Tokugawa Ieyasu retreat", "Oda Nobutada of Arita Castle
  retreats", "Battle of Yoshida-Koriyama Castle"; 20 units). Glossary entry 家臣と話す now
  "Talk to the retainers". Checked in DuckStation: the two-line goal "Go to the Living
  Quarters, Retainers' Hall / and Council Chamber" in the Story box.
- Checked in DuckStation: U00302 and the four pages of U01710 inside the narration box,
  the "See Lady Sugi" goal box.
- Internal: the full-name table is now a list of the 235 named records (was 800
  offsets), 660 bytes smaller, to make room for the new hooks.
- **Translated:** spoken lines in the story films MOVIE02-08, burned in as subtitles like
  MOVIE01: Motonari meeting Lady Myo, the Lesson of the Three Arrows, the eve of
  Itsukushima, Yamanaka Shikanosuke's farewell and prayer ("grant me seven hardships and
  eight trials"), the fall of Gassan-Toda, Motonari's deathbed, Takamatsu (56 subtitles).
  Japanese transcribed with Whisper and corrected by context and the frames; one line is
  uncertain (MOVIE04 end, heard as この戦、行くことはない; taken as 退く, "There will be no
  retreat in this battle!"). MOVIE00 and MOVIE09 have no speech. Tools:
  `tools/transcribe_movie.py --prompt`, `tools/transcribe_clip.py` (re-check one stretch).
- **Changed:** film subtitles sit on a small translucent box fitted to the text, with an
  outline and shadow, instead of a black band across the bottom of the picture (all films,
  MOVIE01 included).
- **Fixed:** film subtitles (and MOVIE01's map labels) came out grey and blurred in many
  frames. The frames were patched with jPSXdec's partial replace, which encoded the new
  blocks at a coarser quantization scale but left the frame header's scale, so they
  decoded too dark (by old / new). Films are now re-encoded frame by frame in full; every
  edited frame of MOVIE01-08 checked against its image (`tools/movie_check.py`). Checked in
  DuckStation: MOVIE05 played through New Game (`tools/play_movie.py`), subtitles crisp and
  on time.
- Tools: `tools/build.py --name N` writes `work/output/test/N.bin/.cue`, for when the
  usual image is open in an emulator.

## 0.2.13 — training duel crash, profile scrolling

- **Fixed:** the game froze (sound looping) as soon as an attack started in a
  training-ground duel. The battle-animation code is an overlay (OVL/BA_OVL.BIN) that the
  game reads to 0x801F8000–0x801FB000. Since 0.2.11 the VWF letter records, font, UI string
  pool and save-list code were there too. The overlay wiped them, and the next letter check
  read a garbage record and crashed. Battle attack animations use the same overlay, so they
  were at risk too. The records are now in unused kernel RAM (0x8000C000), the rest at
  0x801FB000–0x801FE000, and a record outside the canvas is never checked.
- **Fixed:** scrolling a profile left pieces of the previous lines on the right ("rom",
  ": m"). The game pads profile lines with spaces, which are 3 px wide in the English font,
  so a shorter line no longer covered a longer one. Each line now blanks the rest of the
  row up to the window edge.
- **Changed:** profile lines use the full 192 px width (48-byte lines instead of 24, about
  45 % fewer lines). The game prints them straight from its 2.5 KB profile buffer instead of
  a 50 x 25-byte line array. The four training-ground officer profiles (format profiles) were
  rewrapped to the wider lines.
- Checked in DuckStation, from a savestate at the training ground: a duel with Archers
  (attack, damage, EXP), then the next bout. Also checked: Tsunehisa's profile (7 lines),
  and Oda Nobunaga's long profile scrolled down and up with nothing left behind. The
  officer screen shows the English full name ("Motonari  Mouri Motonari").
- Tools: `tools/emu.ps1` runs a newer DuckStation (0.1-12640, portable copy in
  `work/emulator/duckstation-new`) with `MOURI_EMU=new`. It loads savestates made by the
  player's DuckStation, which the project copy (0.1-12070) cannot.
- **Fixed:** the officer screen showed pieces of the English font at the top right
  instead of the officer's unit sprite. The game loads that sprite into VRAM (576,192),
  which the font atlas covered (y 128–247). The atlas is now at y 72–191, between the
  game's icons (y 0–48) and the sprite; no other game upload touches it in the traced
  scenes (castle, town map, menus, profiles, item screens, duel, title, opening film).
  Checked: the officer screen shows Motonari's unit sprite; text renders as before.

## 0.2.12 — saving fixed

- **Fixed:** saving broke off after the first 512 bytes (header and icon), then went back
  to "Which one do you want to save to?". The game sorts its text sprites from the VSync
  interrupt; the VWF hook there re-checked every letter against the canvas after each
  canvas upload (about every 4 frames), several ms with interrupts off, and the memory
  card's 8 KB writes failed. Letter validity is now computed when the game uploads the
  canvas (main thread); the sort only visits the letters marked live.
- **Fixed:** the memory card check froze ("Now checking the Memory Card.") once the card
  held a save made with the translation. The save list copies each line of the save
  title into a 40-byte stack buffer; English line 1 ("Motonari 1:Ep. 8: A Million Hearts
  as One, ") is longer, and the overflow overwrote the slot loop's saved registers. The
  lines now go to their own 128-byte buffer (max 64 bytes), split at ", " or at 』, so
  saves made by the Japanese game show too. Broken saves from earlier builds show as an
  empty entry and can be overwritten.
- **Fixed:** the episode title field (30 bytes at 0x800FD108, kept in saves) took the
  whole English caption ("Episode 21: Oath of the Three Arrows", 36 bytes) and ran into
  the game data after it; loading a save copied its unterminated 30 bytes back the same
  way. Both copies now stop at 29 bytes. The field is not displayed anywhere.
- Checked in DuckStation: save into a new slot and over a broken one (complete 28 KB
  save, same layout as the Japanese game's), then from power-on with SCPH-1001: title →
  Continue → the save list shows "Motonari 2:Ep. 1: The Young Eagle's Debut / in
  Koriyama" → the save loads into the castle. New Game, castle dialogue and Ep. 1 battle
  dialogue render as before.
- The 0.2.10 note "the memory card check hangs in the test emulator, also with the
  original disc" was this: the test card held a broken save from an earlier build, and
  the original game hangs on it the same way.
- **Changed:** caption boxes (castle / room names, chapter titles) now fit the English
  text and are centred; the game sized them at 8 px per character, which limited captions
  to 36 characters. Limit now 288 px (about 50 characters). The eight residence captions
  use the full form again ("Koriyama Castle: Mouri Okimoto's Residence" instead of
  "Koriyama Castle: Okimoto's Res.").
- **Changed:** the katakana name reading in the profile header (アイオウモトツナ) now
  shows the English full name ("Aio Mototsuna"); empty when it would repeat the name
  shown. The reading stays in the data, since the profile index groups by it.
- **Translated:** the stat and column label images (GRAPHIC/MARK.E3, 24x16 tiles): 耐久 END,
  技能 SP, 攻撃 ATK, 防御 DEF, 知力 INT, 運気 LUK, 命中 ACC, 速力 SPD, 装備 EQP, 金 G,
  経験 EXP, 重さ WT, 武将 NAME, 部隊/属性 UNIT TYPE, 所有道具 ITEMS, 修得特技 SKILLS,
  効果 EFF, 回復 HEAL (`tools/mark_labels.py`, 5x7 capitals, run by the build). Checked on
  the item screen after a cold boot. Still Japanese in MARK.E3: the 出陣 / 選択終了 buttons
  and the one-kanji status icons.
- UI string pool: 832 bytes (was 1152; 320 bytes now hold the save-list code).
- Tools: `work/emulator/states/card_v0212_slot1_ch1.mcd` is a card with a good save
  (slot 1, Ep. 1).

## 0.2.11 — boots with every BIOS

- **Fixed:** black screen after the PlayStation logo with the SCPH-1001 BIOS (the one
  most players use; the test emulator had a different BIOS). The VWF glyph records sat
  in kernel RAM 0x8000B800, where SCPH-1001 keeps the boot path and the memory card
  directory; clearing them at start crashed the game. Records, font and the moved UI
  strings now live at the bottom of the game's stack area (0x801F8400-0x801FAC00, never
  used: 15 RAM samples incl. both films and battles); the code stays in the kernel heap
  past the BIOS thread / event tables. The UI string pool grew from 896 to 1152 bytes.
- Checked in DuckStation: SCPH-1001 from power-on through intro, title, New Game, chapter
  captions and the first dialogue, plus castle dialogue with hot reload; SCPH-10000 and
  the PS3 BIOS boot to the title screen.
- Test emulator now boots with SCPH-1001; `tools/hotload.py` clears the records at their
  new place; `tools/gdbdbg.py` scratch moved to 0x801FB000.

## 0.2.10 — text rendering fixes

- **Fixed:** a stray letter could show inside new text (Okimoto's "half-brother," read
  "half-brothert,"): an old letter record from earlier text whose hidden underlay pixels
  happened to be covered by the new letters stayed "live". Drawing a letter now drops every
  record whose cell it overlaps.
- **Fixed:** letters missing in the highlighted save slot ("New Cata"): a record was
  treated as erased as soon as one background pixel of its cell had the text colour, which
  gradient / dithered boxes do. Now only when more than half of them do. Not reproduced
  here (the memory card check hangs in the test emulator, also with the original disc);
  please recheck on that screen.
- **Fixed:** uneven letters at native resolution (no upscaling, as on a console): the 2x
  font was sampled at every other texel, so some letters were a row taller ('a',
  capitals) or sat lower ('.' looked like ','). The texels shown at 1x now form a proper
  1x font made from the same Skies glyphs (same top and baseline rows for all letters);
  upscaled rendering keeps the smooth shapes. Checked in DuckStation: dialogue (Ep. 1,
  Okimoto's deathbed), battle ring, Unit List.
- Found, not changed: the Unit List column headers on its second page (武将, 部隊属性,
  知力, 運気, 命中, 速力) are an image (GRAPHIC), like the other stat headers.

## 0.2.9 — opening film subtitled

- The film after New Game (MOVIE01.STR, 2:12) now has English subtitles and English map
  labels, burned into the video:
  - Speech transcribed with Whisper (large-v3, run locally) and corrected against the story
    and names; 25 subtitles (Hiromoto's deathbed, then the narration of 1506-1516) in
    `work/translation/en/movie/MOVIE01.json`. Self-reviewed for accuracy, voice and
    proofreading; not yet through separate review agents.
  - Subtitles sit on a black band over the bottom 48 px while a line is shown: text over the
    picture could only be encoded blurry in the frame's fixed 8 sectors, over a flat band it
    stays sharp (quantization scale 4-7, 10 at worst).
  - Labels replaced: 永正3年 → "Eisho 3 (1506)", 大内義興 → "Ouchi Yoshioki", 尼子経久 →
    "Amago Tsunehisa", the flying 興 → "Oki", 興元 → "Okimoto", 武田元繁 → "Takeda
    Motoshige", 松寿丸 → "Shojumaru", 毛利元就 → "Mouri Motonari"; they follow the original
    fly-ins and fades.
  - Checked in DuckStation from New Game: subtitles and labels show; the rest of the frame is
    untouched (only changed 16x16 blocks are re-encoded).
- Glossary: 幸千代丸 "Kochiyomaru" (Okimoto's childhood name).
- Tools: `tools/movie.py` (raw sectors, frames, audio, re-encode with jPSXdec, preview),
  `tools/movie_edit.py` (subtitles and label replacement), `tools/transcribe_movie.py`;
  `tools/build.py` writes re-encoded movies into the disc in place. Details in
  `docs/movies.md`. GenEi Latin font (SIL OFL) added in `tools/fonts/genei-latin`.

## 0.2.8 — UI text review (accuracy, editorial, proofreading)

- Reviewed all 2,516 UI units (menus, messages, battle speech, item / skill names and
  descriptions, character profiles) in the three BASE_RULES.md stages. Reports:
  `work/translation/en/ui/reports/` (`acc_*`, `edit_*`, `acc2_*`, `proof_*`, progress in
  `_review_progress.md`).
  - Accuracy: about 150 units corrected (dropped or misread details, wrong episode
    attributions, names).
  - Editorial: 230 units smoothed for clarity and voice; profiles in the encyclopedic
    present tense, "the Shogun" capitalised, one wording per character across variants.
  - Accuracy recheck of the editorial changes: 8 units changed back or adjusted.
  - Proofreading: punctuation ("?!", punctuation inside quotes, "After that,"), status
    and legend capitalisation, doubled phrases, about 150 stale translator notes fixed.
- Shared variant text aligned across slices: Komatsumaru Ep. 1 sentence (P0563-P0575),
  Nomi Munekatsu (P0441-P0448), Amago Katsuhisa (P0603), Kikkawa Mototsune
  (P0202-P0205), Kobayakawa Takakage (P0279-P0290), "serves with the Mouri Army"
  (P0613/P0632/P0633/P0639); episode tags never split across lines.
- Town map: 倉庫 label "Gear" → "Stores" (E0549); battle ring "Atk." → "Attack" (E0567);
  width limits for both relaxed to the space seen in game.
- Skill info column 消費量 "MP Cost" → "Skill Cost" (E0335), as in the skill panel (E0398);
  the game calls the resource Skill Points / SP everywhere else (user decision).
- **Fixed:** four messages were still in Japanese: the string scanner rejected half-width
  characters (`｡` `｢`). `tools/extract_ui.py` now runs a second pass that accepts them and adds
  the missed strings as new units E0788-E0791 (existing keys unchanged): "Learned the skill
  "%s"." (level-up and training ground), "Inventory is full. Send to the Storehouse?", the
  Workshop prompt "The missing materials cost %u gold. Buy them and make it?" and "......".
  A scan of the built disc now finds only the documented debug / unused strings in Japanese.
- Glossary fixes: Aio Mototsuna, Amago Katsuhisa, Mizawa Castle, Wada Yaichi, Masaki
  Kenichiro, Lg.Bamboo Bow.

## Tools (no disc change)

- `tools/hotload.py`: writes the current build (VWF kernel code and font / string pool,
  MAIN.EXE string and hook changes, FAT_DATA.BIN, the idle event script) into the
  running game, so savestates from older builds show the new text. Checked: a v0.2.6
  battle savestate shows the 0.2.7 "Turn  1" after hot reload.
- `tools/scene.py`: shows any script unit (or its whole event block) in the running game
  by injecting its text ops as an event block into the script VM; screenshots per page.
  Checked in a castle room (dialogue with portraits, caption, choice menu, a 40-page
  block) and on the battle map (narration and messages during the enemy phase).
- `docs/debug_tools_guide.md`: how to build this debug kit (debugger link, input and screen
  grabs, safe halt, hot reload, scene preview, coverage scan) for another game, on any
  platform or emulator.
- `tools/emulink.py`: shared GDB helpers (safe halt through the BIOS thread control
  block, input, script VM context). Details in `docs/debug_tools.md`.

## 0.2.7 — battle UI check and VWF fixes

- Played the Ep. 1 battle (Battle of Arita Castle) in DuckStation from a new game.
  Checked and fitting: unit action ring (Atk. / Skill / Items / Wait), item and skill
  lists and their info panels, Give / Drop, "No enemy units in range.", the battle ring
  (Info / End Phase / Rally / System), Unit List (3 pages), Victory Cond., Full Map
  title, Rally (Ongoing / One-time), "End commands for all units?", phase and turn
  captions ("Enemy Phase", "Turn 3 Clear", "Cavalry: Move", "Hirohide: Atk."), event
  messages, speech balloons, battle animation names and HP / skill counters.
- **Fixed:** battle HP counters smeared when the number changed (95 → 38 left both
  numbers on top of each other). The original glyph blit painted the whole cell in
  opaque mode; `vwf_draw` now paints the advance × 12 cell in the window background
  colour first when the blit mode (`gp+0x168 & 15`) is opaque. Speech balloons
  (transparent mode) are unchanged.
- **Fixed:** font glyphs ("#$%&'()345678…") showed inside battle attack effects. The atlas
  sat at VRAM (972,360), under the battle background loaded at (640,272), and the VWF
  re-uploaded it over the battle graphics. Moved to (576,128) as 20 × 5 cells with the
  16 CLUTs at (576..639, 248..251); that area is empty in the castle, map and battle
  scenes (VRAM dumps and LoadImage traces).
- **Fixed:** the game hung in battles with rain at the first attack animation (stuck
  loading BA_BACK.BIN). In rain the game sorts the text sprites from its VSync callback;
  `s_hook` re-validated every glyph record each time (~15 ms per sprite), which starved
  the CD interrupt. Record validity is now cached per sprite and re-checked only after
  the canvas is uploaded again (`li_hook` counts canvas uploads). Tested with the weather
  forced by timing: every rain run hung before (11 runs; also with the other hooks
  disabled, but not with `s_hook` disabled), and both rain runs pass now; text, HP
  counters, balloons, profiles and menus still draw correctly. Affects all builds with
  the VWF.
- Workshop list header (ring menu Info → Workshop): E0730 "%s" (was "(%s)"); "(Weapons)" ran
  into the "Make" column. Checked after hot reload: "Name  Weapons  Make  Have". The item
  detail panel (Mats / Buy, Equippable By, Owned) and Item Transfer fit.
- Still waiting for a later savestate: the Workshop building's crafting screen (type
  columns E0725-E0729 Cannon / Ninja / Armor / Shd / Med, E0598-E0601 Swd / Spr / Bow /
  Gun, E0738 Artisan, E0365 Cannonsm.) and the Storehouse building (E0350, E0150) are
  closed before the first battle in Ep. 1; E0224 Chosokabe, E0662 Both, E0713 Target and
  the town-label "Gear" vs "Storehouse" (E0549) need their screens too.
- E0397 "Turn%3u" (was "%3u turns", shown as "1 turns" above the victory conditions);
  `LIMIT_OVERRIDES` E0397 70 px (the box is about 72 px).
- Not changed: "We" reads like "Ne" in native-resolution screenshots (the W loses its left
  column at 1x, like "(" / ")"); upscaled rendering is fine.
- Not checked: duel scenes, forge / workshop columns (D-16), a full battle to the end.
  The final build was checked by loading its kernel code into battle savestates, not by a
  fresh boot through the battle.
- Savestates (work/emulator/states): `v026_ch1_arita_council.sav`,
  `v026_ch1_save_prompt.sav` (at "Do you want to save here?"), `v026_ep1_battle_start.sav`,
  `v026_ep1_battle_turn4.sav` (v0.2.6 code in RAM; load the 0.2.7 disc and the kernel code
  for testing).

## 0.2.6 — script rebuilder: IF lengths

- **Fixed (all builds up to 0.2.5):** EEX action parts contain nested IFs (op 0001, a
  condition op, a u16 body length, a body ending with op 0000). The VM skips a body by
  its length when the condition fails; the rebuilder only fixed the block size and
  size2, so every IF around a translated string kept its Japanese length (5,948 IFs in
  the 59 scripts). A failed condition then jumped into the middle of the next op. Found
  in Ep. 1: "Visit Okimoto's Res." could not be done (selecting the samurai residence
  on the town map did nothing; the original disc opens Okimoto's deathbed scene).
- **Fixed:** `eex.py`'s size2 search picked a wrong u16 (a flag-list tag) in 20 battle
  script blocks (S_02, S_03, S_06, S_08-S_10, S_12, S_16, S_18, S_19, S_22); rebuilding
  those blocks with text overwrote that tag.
- New `tools/eex_ops.py`: op-by-op parser with the signatures of all 79 ops, taken from
  the VM handlers (dispatcher 0x80020254, table 0x8011B094, argument reader 0x800212D4;
  counted lists for ops 08 / 35, 30 / 60 unit records for ops 1C / 1D). All 5,996 blocks
  parse exactly. `eex.Script` takes size2 and the IFs from it; `rebuild` recomputes
  size2 and every IF length and refuses replacements that are not string arguments;
  `insert_text.build_scripts` re-parses every rebuilt script and stops the build if one
  does not parse. Unit extraction is unchanged (12,403 strings; the 5 false hits inside
  flag lists, U01625 / U01642 / U02901 / U02907 / U04098, are empty and never written).
- Checked in DuckStation (new game on v0.2.5, then v0.2.6 with the fixed R_00):
  Okimoto's residence opens and the story continues through the council, Lady Sugi
  and the Arita council.
- Not checked yet: battle UI. The Arita council ends in a save prompt; choosing Slot 1
  after a savestate load left the save menu waiting on the memory card (the card read
  returned all 0xFF), so the run stopped there. This looks like emulator memory-card
  state after a savestate load, not text, but it is not proven.
- Savestates for testing (work/emulator/states): `v025_ch1_quarters.sav`,
  `v025_ch1_samurai.sav` (v0.2.5 disc; same file layout as v0.2.6, but R_00 in RAM is
  the old one) and `jp_ch1_town.sav` (original disc).

## 0.2.5 — UI term decisions, world-map town labels

- The 12 UI decisions (`work/translation/en/ui/reports/_ui_decisions.md`), option A for all:
  - I-01: manual tiers 秘伝書 "Secret Manual" / 奥義書 "Ultimate Manual" (menu "Sec." /
    "Ult."): D0321-D0324 "Koga Sec." / "Iga Sec." / "Koga Ult." / "Iga Ult.", E0328 "Got
    ultimate manual"; glossary split into two entries; script U06285 "Ginkgo Ult."
    (`term_fixes` `ginkgo-ult`).
  - I-05: the tutorial quotes the menu as "Store/Retr." (U00077, U00374; `store-retr`).
  - I-07 "Koyama", I-20 "Faranki" / "Furanki", I-28 "Artisan" / "Trainer": kept, glossary
    notes settled.
  - I-09: P0577-P0583 "his beloved wife Okata" (profiles follow the script: "Lady Myo" up to
    the wedding).
  - I-26: I0007, I0010, I0012, I0013, I0015 "modeled on the armsmith X".
  - I-38 / I-39: P0204, P0205 "Battle of Kanayama Castle"; P0078-P0081 "Siege of
    Kagamiyama Castle" (the glossary battle names).
  - I-43: P0545 "a local lord in Aki".
  - I-52: world-map town labels in full (below).
- World-map town labels (pointer table 0x800DDD40, label code 0x80024BDC): new `vwf.py`
  option `town_label` (routine `town_x`, set by `insert_ui.py` when a town name is
  translated) centres each label on its town by the VWF width and keeps it between x = 8
  and 312. The game centred by strlen in 8 px cells, which put long English names off
  centre and "Nagato-Katsuyama" at x = -4. The 57 labels now have a 120 px / 16-byte
  limit (`LIMIT_OVERRIDES`). Full names: E0129 Iyo-Yuzuki, E0130 Nagato-Katsuyama,
  E0131 Gassan-Toda, E0133 Aki-Takamatsu, E0134 Bitchu-Takamatsu, E0499 Ogurayama,
  E0512 Hatagaeshi, E0514 Kashirazaki, E0515 Kagamiyama, E0517 Tokonoyama,
  E0522 Itsukushima, E0523 Sanbonmatsu, E0531 Rengeyama. Unused glossary shorts
  (Kagami, Hatagae., Sanbon., Renge, Tokono., Kashira.) removed.
- Checked in DuckStation (chapter 1 savestate with `town_x` and the names loaded over
  GDB, all three map variants by switching 0x800F45EE): every changed label is centred
  and on screen, including Nagato-Katsuyama (col 7), Ogurayama / Tachibana / Homanzan at
  the left clamp and Gassan-Toda at the right clamp. The castle-town facility map labels
  ("Gear", "Exit", ...) fit. The v0.2.5 disc boots to the intro with `town_x` at
  0x8000FB64.
- Checkers: insert_ui 2,516 units, the same 10 jp-derived width warnings; insert_text
  7,289 units, 0 problems; apply_terms dry run 0 changes. Pool 764 of 896 bytes.
- Still Japanese on the travel map: the province names (image tiles, GRAPHIC).

## 0.2.4 — leftover fixes (in progress: menus, items, profiles)

- Plain names between Mouri retainers in U00414 ("Fukubara and I"), U01636 ("here
  comes Shiji") and U01652 ("report it to Shiji").
- The last 13 units with long pause runs (slices 027, 052, 055, 058, 061, 065) cut to
  "......". Checker clean; apply_terms: no changes.
- Menus / item & skill names / profiles: format analysis and tooling done
  (`docs/text_formats.md`).
  - `tools/extract_ui.py`: 2,519 units (IMSG 599, PROFILE 642, DATA 491, EXE 787) in
    80-unit slices `work/source/text/ui_slices/`, with per-unit limits (max_bytes,
    max_lines, line_px, line_bytes, wrap) and context; debug / unused strings listed in
    `ui_skipped.json`.
  - `tools/insert_ui.py` (check / preview / build) + `tools/build.py`: IMSG.E3 and DATA.E3
    in place; MAIN.EXE strings in place, or moved (all pointer / lui+addiu references
    patched) to freed slots and an 896-byte kernel-RAM pool; PROFILE.E3 rebuilt one
    sector per variant. With no `work/translation/en/ui/*.json` the .bin is identical.
  - `tools/vwf.py` optional patches, applied only with matching translations:
    `desc_cap` (item / skill descriptions 80 -> 99 bytes), `profile` (sector reader
    `prof_load`, verified in DuckStation), `profile_fmt` (format profiles 48 / 49),
    `pool` (moved strings). Line-printer caps (20 / 26) unchanged.
  - Test: 12 units (`work/source/ui_test.json`) built and read back; not left in the
    translation folder.
- UI draft: all 32 UI slices translated (2,513 units with text; 6 blank on purpose: E0130,
  E0133, E0134 town labels waiting for a width check, E0581 / E0582 binary data, P0085
  empty in the Japanese). Reports `work/translation/en/ui/reports/NNN.md`, `_progress.md`,
  `_gaps.md` (619 glossary gaps, 52 inconsistent renderings, 21 code dependencies).
- MAIN.EXE string space: 258 strings outgrow their slots (6,011 bytes). `insert_ui.py`
  now also fills the unused tails of strings translated in place and merges neighbouring
  free slots, so only 720 of the 896 pool bytes are used (before: "pool full", 2,140 bytes
  needed).
- Save title (D-02 / D-03): E0066 / E0067 start with the ", " split marker (E0474), so the
  save list breaks after the episode; E0481 made movable (`SAFE_PAIRS` in
  `extract_ui.py`: the lui at 0x800162E8 is in a delay slot but the other path reloads
  v0), so the titles read "Motonari N:" / "Terumoto N:". `insert_ui.py check` now checks
  the whole title against the 72-byte stack buffer (worst case 70 bytes + NUL).
- E0495 "from" ("Move items from the Storehouse?"); I0130 "an Archer Captain".
- `extract_ui.py` `LIMIT_OVERRIDES`: no px limit for the save-title pieces, the E0495
  particle and the weather words (all printed inside larger strings or growing boxes).
  Checker: 10 warnings left, all widths estimated from the Japanese (E0224, E0598-E0600,
  E0713, E0725, E0727-E0729, E0738; forge / skill panel columns, battle UI).
- Verified in game (chapter 1 castle): Settings screen, ring menus (Info / Story / Item
  Transfer / System, Officer / Workshop, Settings / Save / Load / Profiles), officer list
  and status pages, skill page, item transfer, item description panel (2 lines), profile
  index and profile pages (per-variant loader), save prompts, memory-card messages and the
  save title ("Motonari 1:Ep. 1: The Young Eagle's Debut, / in Koriyama"); saving to
  temporary memory returns to the menu normally.
- Still Japanese, found in game: stat labels and column headers (攻撃, 防御, 武将,
  所有道具, 金 ...) are image tiles, not text (GRAPHIC); the katakana reading beside names
  on profile / status pages (half-width kana in DATA.E3, 15-byte field; it may also drive
  the A-O index, so not changed). The profile index groups names by their Japanese
  reading ("A-O" holds Aio, Amago, Ouchi ...).
- Not yet checked in game: battle UI (balloons, battle-name banner, battle menus, forge
  columns, terrain / weather words), format profiles 48 / 49, 50-line profiles.
- UI gaps pass (`work/translation/en/ui/reports/_gaps_applied.md`): the non-user items of
  `_gaps.md` Section 2 applied to 84 UI units (supply ranks Lt. / Hv. Supply, Stores,
  Tokonoyama / Hogi, Hex Rite, Barrel / Solid / Nanban Armor, Ridge / Bear Fur mail,
  Ninja 3 Blades, Yoshiie Bow, "Lg. " / "Sm. " spacing, Shield Sm., Skill Points,
  uplands / woods / shoals, "the Ouchi attack on Gassan-Toda Castle", naval commander,
  Nomijima, main house / branch family ...). Script U00672 "Tokonoyama" (term_fixes rule
  `tokonoyama`). Glossary: 604 terms and 8 people added, 49 menu shorts + skill-menu
  shorts, I-17 / I-29 / I-36 style rules in the README. 12 open questions in
  `_ui_decisions.md`; forms that wait for an in-game width check are listed in the log.
  Checkers: insert_ui 10 allowed jp-derived warnings, insert_text 0 problems.

## 0.2.3 — user decisions applied, proofreading pass

- User decisions (all 21 items of `_decisions.md`, option A) applied: 32 units, 39 line
  edits (log: `work/translation/en/reports/_decisions_applied.md`). Captions U01372 and
  U03681; "Master" until succession, "Lord" after (Komatsumaru "Lord" from U00094,
  Terumoto "Master" up to U05353), "Master Shikanosuke" in U03269-U03270 (keys-limited
  rules `komatsumaru-lord`, `terumoto-master`, `shikanosuke-master` in term_fixes.json);
  plain names between Mouri retainers (U00122, U00431, U00441, U00443); 11 missionary
  units moved to the halting-comma voice (recorded in characters.json). Honorific policy
  in the glossary README and terms.json updated.
- Stage 3 (proofreading) done for all 92 slices: 67 units' English changed (48 of them
  long dot runs cut to "......"), about 60 stale notes updated (reports `proof_NNN.md`,
  `_proof_progress.md`, `_proof_summary.md`: 49 flagged items for accuracy, editorial,
  glossary and corpus-wide format decisions).
- apply_terms after the pass: 0 changes. Checker: 7,289 units, 0 problems; 7,260 / 7,289
  translated. Disc rebuilt: `work/output/test/MouriMotonari.cue` (v0.2.3).
- Slice 081 was emptied by its proofreader during a usage-limit cut-off and rebuilt
  from the agent's copy; compared against the 0.2.2 build it matches in 79 of 80 units
  (the one difference, U06487, is the proofreading edit).
- `tools/eex.py`: the string scanner now accepts byte 0xA0 (first dictionary code), so
  rebuilt English scripts parse completely.
- Open: U00414, U01636, U01652 still use "Lord Fukubara" / "Lord Shiji" between Mouri
  retainers (not on the approved list for rule 17); 13 units in slices 027, 052, 055,
  058, 061, 065 keep long "........" pause runs; 49 flagged items in `_proof_summary.md`.

## 0.2.2 — editorial pass and follow-up

- Stage 2 (editorial pass) done for all 92 slices: 677 units edited (reports
  `work/translation/en/reports/edit_NNN.md`, `_edit_progress.md`, `_edit_summary.md`).
  apply_terms re-run after it: no changes.
- Accuracy recheck of the editorial changes (BASE_RULES): 35 units rechecked against
  the Japanese, 7 meaning fixes (e.g. U02707 subject restored to Kuchiba).
- Glossary: 28 questions settled from evidence ("the Mouri Army", "the Mouri clan",
  "head of the clan", "Nagato-Katsuyama"; retreat captions "X retreated." / "X
  withdrew."; castle-room captions "Koriyama Castle: <Room>"); Ayame, Sakichi and
  Iku added; 12 new term_fixes rules, 44 line changes in 39 units; cross-slice
  consistency items aligned. Log: `_followup.md`.
- `_decisions.md`: 21 items for the user (13 width/presentation, 8 taste).
- Checker: 7,289 units, 0 problems; disc builds.

## 0.2.1 — terminology normalised, accuracy review started

- Glossary gaps resolved (all 108): one form per term in `work/glossary/terms.json`
  (367 -> 490 entries; `short` field for menu forms) and "Resolved gaps" in the
  glossary README. Examples: 大将 ranks = "Spear / Archer / Rifle / Mounted Archer
  Captain"; 気付け薬 "Stimulant" (distinct from 回復薬 "Restorative"); fortune grades
  Great Blessing / Blessing / Small Blessing / Curse / Great Curse; を退却させる "Make X
  retreat" vs の退却 "X retreats"; 甲山城 Koyama in both glossary files; commoners'
  お prefix dropped (Rei, Yuki, Ume; Okata kept); おやじ様 "Father".
- `tools/apply_terms.py` + `work/glossary/term_fixes.json`: per-unit term
  normalisation (only where the Japanese has the term; never touches '&' lines;
  dry run by default). Applied: 97 line changes in 95 units; re-run changes nothing.
- `docs/REVIEW.md`: brief for the three BASE_RULES review stages (accuracy,
  editorial, proofreading; do-not-touch list; reports `reports/<stage>_NNN.md`).
- Stage 1 (accuracy review) done for all 92 slices: 286 units' English changed,
  34 notes updated (reports `work/translation/en/reports/acc_NNN.md`, log
  `_acc_progress.md`). apply_terms re-run after the reviews: no changes. Checker
  clean; disc builds. `_acc_summary.md` lists 217 open items (161 kept
  ambiguities, 26 needing an in-game check, 14 suspected slips in the Japanese
  script, 13 for the user to decide, 3 cross-slice inconsistencies) and 36
  suspected glossary errors / questions.

## 0.2.0 — full script draft

- All 92 slices drafted: 7,260 of 7,289 script units in English, checker clean
  (`python tools/insert_text.py check`: 0 problems). Not translated on purpose:
  5 single half-width kana data strings (op01) and the 24 staff-credit units,
  which are already English.
- Every script fits the 96 KB script buffer with the dictionary compression
  (largest: R_18 85.6 KB; original Japanese 94.3 KB). Grown files use 561 of the
  13,500 OUTMOST.DAT padding sectors.
- Reports: 1,226 uncertainties logged in `work/translation/en/reports/013-091.md`;
  `_progress.md` (per-slice log); `_glossary_gaps.md` (108 terms rendered
  inconsistently or missing from the glossary, e.g. "Make X retreat" vs
  "X retreats", Captain vs General, two fortune-grade scales, item names).
- Not yet done: glossary-gap normalisation, the BASE_RULES review passes
  (accuracy, editorial, proofreading), in-game check beyond chapter 1's opening,
  menus / items / profiles (MAIN.EXE, IMSG.E3, PROFILE.E3).

## 0.1.2 — engine fixes: full-width lines, English name boxes, compression

- Dialogue lines use the full 168 px: the window's line printer (0x8003DE8C) cut
  lines after 26 / 28 bytes; its two caps (0x8003E984 / 0x8003E9A4) are now 80.
- English speaker name boxes: DATA.E3's 800 character records get English names
  (max 12 bytes; given names, "Surname I." on clashes, short generic labels such as
  "Mouri Troop", "Townsfolk"), and the inserter writes the same names into the
  '&' speaker lines, so the portrait lookup still matches (`tools/names.py`).
  Verified in game: "Mouri Troop" with the right portrait.
- Dialogue compression (`tools/dte.py`): bytes 0xA0-0xDF expand to 64 dictionary
  strings chosen from the translation; a hook on the script text copier's >= 0x80
  path expands them. Speaker lines, captions and choices stay plain. R_00 shrinks
  from 52.5 KB (plain English) to 44.5 KB; the largest scripts were estimated at
  up to 106 KB against the 96 KB script buffer. The inserter also checks each
  speaker section against the 1 KB text buffer.
- Captions may use up to 36 characters (their boxes grow 8 px per byte).
- Translation: slices 003-012 drafted (1,040 / 7,289 units, checker clean, built
  with no script-buffer warnings); slices 013-091 handed to a coordinator agent in
  waves of 10. Agents write their full reports to `work/translation/en/reports/NNN.md`.
- Brief: victory conditions follow terms.json ("Takeda Motoshige retreats").

## 0.1.1 — pilot translation (opening of chapter 1)

- Pilot: units U00000-U00239 (slices 000-002: chapter 1 opening, Okimoto's
  death, the first town scenes and facility tutorials) translated, checker clean;
  inserted by `python tools/build.py`. Chapter/episode titles, captions and the
  first battlefield dialogue verified in game.
- Disc builder: grown files are placed inside OUTMOST.DAT (27 MB padding at the
  end of the data area). The game's own CD reader hangs on sectors appended past
  the original end of the disc.
- Dialogue lines are wrapped at 26 characters as well as 168 px: the dialogue
  window also breaks lines after 26 bytes (found in game; counter not located yet).
- Found in game: caption/title boxes size themselves at 8 px per byte, so
  captions do not need the Japanese width limit; English is left-aligned in them.

## 0.1.0 — VWF + 4x font test build (first dialogue)

- MAIN.EXE: variable-width font for all single-byte text, drawn as 2x-density
  quads (Skies of Arcadia Latin font, as in Riot Stars / Seireiki Rayblade) over
  the game's 320x240 text canvas; a hidden 1x underlay in the canvas keeps the
  glyphs in sync with window clears and save/restore. See `docs/VWF.md`.
- Script text copier patched: bytes 0x20-0x7F are plain ASCII (they were packed
  hiragana / punctuation).
- Test disc `work/output/test/MouriMotonari.cue` (`python tools/build.py --test`):
  the opening battlefield conversation of chapter 1 in English (verified in game:
  wrapping, page breaks, speaker changes, no stale glyphs).
- Tools: `tools/eex.py` (event script parser/rebuilder, all 59 scripts round-trip),
  `tools/extract_text.py` (7,289 unique strings in 92 slices), `tools/insert_text.py`
  (pixel word-wrap, 3-line pages, checker), `tools/vwf.py`, `tools/build.py`
  (moves grown files, updates ISO directory and FAT_DATA.BIN), `tools/gdbtrace.py`,
  `tools/gdbreset.py`; reused from Riot Stars: extract_iso, build_disc, cdsector,
  masm, mips, gdbdbg/gdbmem (adapted to MAIN.EXE), dsstate, emu.ps1, skies_font.
- Docs: `docs/TRANSLATING.md` (agent brief), `docs/text_inventory.md`, `docs/VWF.md`.
- Glossary: `work/glossary/characters.json` (289 people: all 273 speakers + 16
  mentioned; readings from Wikipedia / Koei wiki, 57 marked as guesses; gender only
  with cited evidence), `work/glossary/terms.json` (367 places, castles, battles,
  chapter/episode titles, clans, honorifics, game terms), `work/glossary/README.md`
  (romanization and honorific policy, open questions).
