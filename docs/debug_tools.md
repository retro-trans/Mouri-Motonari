# In-game debug tools (DuckStation + GDB)

Building the same kit for another game: `docs/debug_tools_guide.md`.

All tools talk to the project's DuckStation (`tools/emu.ps1 start …`, GDB server on
port 2346, `[Debug] EnableGDBServer` in `work/emulator/duckstation/settings.ini`).

| Tool | What it does |
| --- | --- |
| `tools/gdbdbg.py run "press circle 4; wait 60; shot x.png"` | input and VRAM screenshots (both framebuffers) |
| `tools/hotload.py` | puts the current build into the running game |
| `tools/scene.py U00307 …` | shows any script text in the running game, at once |
| `tools/emulink.py` | shared helpers: registers, safe halt, input, script VM context |

## Hot reload — `tools/hotload.py`

After `tools/build.py`, a savestate made with an older build still holds the old
program in RAM. `hotload.py` writes the new one into it:

* the VWF kernel code (hooks, DTE dictionary, atlas state) and the font + UI string
  pool, exactly as the entry stub copies them at boot;
* every MAIN.EXE byte that differs from the original program, plus all translated
  string slots and patch sites (strings, pointers, lui+addiu pairs, hook jumps); the
  area from 0x80125458 (packet buffer at run time) is skipped;
* FAT_DATA.BIN (files move between builds; a stale table loads wrong sectors);
* the event script in the VM buffer, if no event block is running.

It halts at the VSync pad read and writes only when neither thread is inside the VWF
code (EPC, RA and stacks checked through the BIOS thread control block); otherwise it
tries the next frame. `--dry-run` reports only.

Not updated: data the game already copied into its own structures (DATA.E3 names,
officer and item tables of a running game). Those need a new game or a savestate made
with the new build. IMSG.E3, PROFILE.E3 and scripts loaded later come from the disc,
so they are current as long as DuckStation runs the new .cue.

## Scene preview — `tools/scene.py`

```
python tools/scene.py U00307                 one unit
python tools/scene.py U00051 U00115          several, in order (caption, choice, …)
python tools/scene.py U00140 --block         every text op of the unit's event block
```

The text ops of the unit (dialogue 0x27, captions 0x28-0x2B, labels 0x2C, choices
0x12) are taken from the built script on the test disc, wrapped as one event block
(u16 length, ops, op 0000) and written to the unused tail of the 96 KB VM buffer
(0x800C4190). When a scene's script tick calls the event-start routine 0x80021CB4 with
the VM idle, the read pointer (VM context 0x800C0BF0 +8) is set to that block and the
start marker (+0xC) to 0, so that same call runs it: portraits, name boxes, paging and
choices are the game's own. Callers that use 0x80021CB4 only as a query (battle unit
checks) are skipped: the caller must call 0x80022314 next. The ops have no side
effects; when the block ends the scene is idle again.

Screenshots go to `work/ui/shots/scene/<unit>_NN.png` (both framebuffers side by side,
one per page); Circle is pressed between pages until the block ends. Runs
`hotload.py` first (`--no-hotload` to skip), so the dictionary matches the text.

Works in castle rooms, on the town map and on the battle map (checked in the player
and enemy phases). The background is whatever scene the savestate is in.

Limits:
* The last Circle can also act in the scene (e.g. talk to the selected person); use a
  spot with nothing selected.
* `--block` flattens IF branches: all variants of a conversation play one after another.
* Battle animations, duels and menus are not script text; use a savestate and real
  input (or hot reload + the game's own menus) for those.

## Newer DuckStation (player savestates)

`work/emulator/duckstation-new` is a portable copy of DuckStation 0.1-12640 (same settings,
BIOS and cards as the project copy). Savestates made by a player's newer DuckStation
(format 0x5E) do not load in the project copy (0.1-12070, format 0x57). Select it with
`MOURI_EMU=new` for every `tools/emu.ps1` call (start / shot / stop); the GDB tools work
the same. `work/emulator/states/user_v0212_training.sav` is such a state (0.2.12, Ep. 1,
at the training ground; SCPH-1001). `v0214_workshop_list.sav` (same session, 0.2.14): the Koriyama
workshop's sword list (load it with `MOURI_EMU=new`). In town and room scenes Square opens
the list of people and exits (Exit leaves to the town map; there Square lists the places).

`work/emulator/duckstation-12777` is a portable copy of DuckStation 0.1-12777 (state format
0x66, the version a player used in November 2026; project settings, GDB on). Select it with
`MOURI_EMU=12777`. `work/emulator/states/user_v0216_ep8_map.sav` is that player's state on the
Ep. 8 battle map (Interception in Bingo, turn 5, 0.2.16, made from
`work/output/test/MouriMotonari.cue`): the 0.2.16 font atlas over the right part of the map.
After `hotload.py` the map picture in VRAM is still the damaged one; to test, upload
GRAPHIC/HM07.E3 again through the game's LoadImage (640,32 onwards, 384 halfwords wide), as
the map loader 0x8005622C does. The F10 screenshot key does not work in this copy; use
`gdbdbg.py shot`. A savestate from another DuckStation can be unpacked without loading it:
the main block is one zstd frame after the screenshot frame; in the 0x66 state main RAM
starts at offset 0x1A63 of the unpacked data and VRAM (1024x512 halfwords) at 0x201DDD.

`gdbdbg.py shot` grabs the framebuffer the game last displayed; screens that do not flip
buffers (the profile screen) show the previous screen there. Use `tools/emu.ps1 shot`.

## Savestates

`work/emulator/states/`: castle (`v025_ch1_quarters.sav`, `v025_ch1_samurai.sav`),
Arita council (`v026_ch1_arita_council.sav`, `v026_ch1_save_prompt.sav`), Ep. 1
battle (`v026_ep1_battle_start.sav`, `v026_ep1_battle_turn4.sav`), original disc
(`jp_ch1_town.sav`). Load with `tools/emu.ps1 start work/output/test/MouriMotonari.cue
-StateFile <state>`, then `tools/hotload.py`.

Memory card tests (save / load):
* A savestate holds the BIOS RAM of the BIOS it was made with: load the v025 / v026 / jp
  states with `PathNTSCJ = scph10000.bin`, and switch back to `ps-22a.bin` afterwards.
* DuckStation removes and re-inserts the card when the card file differs from the one in
  the savestate; the game's card driver can then wait forever. Use the card file the
  state was made with: `v026_ch1_save_prompt.sav` goes with `card_v026_save_prompt.mcd`
  (copy it over the card in `memcards/`), whose slot 1 holds a
  broken 0.2.6 save (header only), which also tests the list with a broken entry.
  `card_v0212_slot1_ch1.mcd` has a good save in slot 1 (Ep. 1) for loading from the title.
* Do not take `gdbdbg.py` screenshots while "Now saving" is shown: the grab stops the game
  inside the VSync interrupt and runs code there, and the card write fails like it did
  with the slow sort hook before 0.2.12. Wait ~900 frames, then check the card file
  (`work/emulator/duckstation/memcards/`): a complete save of this game ends at offset
  0x7080 of its first block.
* Card I/O can be traced at the BIOS file stubs (open 0x800AA88C, lseek 0x800AA89C, write
  0x800AA8BC, close 0x800AA8CC); after each async write the game's result is v0 at
  0x8009ABE4 (0 done, 2 error).

BIOS: the project emulator boots NTSC-J games with `ps-22a.bin` (SCPH-1001, what players
most often use; `settings.ini` `[BIOS] PathNTSCJ`). Builds up to 0.2.10 worked with the
earlier `scph10000.bin` but crashed SCPH-1001 at boot (docs/VWF.md, Memory). Test a new
build from power-on with SCPH-1001 at least once, not only from savestates. A BIOS that
boots more slowly makes `gdbdbg.py` time out (no pad read yet): wait before the first command.
