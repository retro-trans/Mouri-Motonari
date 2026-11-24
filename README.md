# Mouri Motonari: Chikai no Sanshi — translation project

An open toolchain for translating **Mouri Motonari: Chikai no Sanshi** (PlayStation,
Koei, 1998, SLPS-01285), plus the English translation built with it.

## Contribute

The story, menus, items, skills, officer profiles, battle speech, the story films and the
interface graphics are translated, but the game has not been played through to the end
yet, and no human has proofread the English against the Japanese. If you want to
contribute to this project or the next in any way — be it bug reports, proofreading or
playtesting — please join my Discord:

**[discord.gg/nZBZfTDfCP](https://discord.gg/nZBZfTDfCP)**

## Play it

The latest release is **[v0.8.0](https://github.com/retro-trans/Mouri-Motonari/releases/tag/v0.8.0)**,
the first public release: a full patch for the Japanese release (**SLPS-01285**). The story
scenes, battle scripts, menus, items, skills, officer profiles and interface graphics are
in English, drawn with a variable-width font, and the story films have English subtitles
over the original Japanese voices.

### Apply

Use [Retro Trans](https://github.com/retro-trans/retro-trans-tools), or apply the `.xdelta`
with DeltaPatcher or xdelta3. Use a raw single-track BIN (MODE2/2352) with its CUE.

| Your source image | Patch |
|---|---|
| Japanese release, SLPS-01285 | `MouriMotonari-English-v0.8.0.xdelta` |

Check the source hashes in `README-v0.8.0.txt` if your patcher reports a mismatch; keep
checksum verification enabled.

For example:

```
xdelta3 -d -s "Mouri Motonari - Chikai no Sanshi (Japan).bin" MouriMotonari-English-v0.8.0.xdelta MouriMotonari-English-v0.8.0.bin
```

The patched BIN has the original disc length. Load it through a CUE that names the new
file: use `MouriMotonari-English-v0.8.0.cue` from the release, or copy your own CUE and
edit its `FILE` line. For a CHD, extract it to BIN/CUE first (`chdman extractcd`).

**Boot the new image fresh.** Old emulator save states keep the previous executable and
data; memory-card saves work, including saves made with the Japanese game.

On the battle map, **L2** shows or hides Endurance and SP bars under every unit (green /
blue for Motonari's side and allies, darker shades for the enemy). Visited villages,
houses and other places get a small ticked box in the corner of their cell.

## Translate it

Fork it to fix the English, or to take the game into another language. Start with
**[docs/TRANSLATING.md](docs/TRANSLATING.md)** (story scripts) and
[docs/REVIEW.md](docs/REVIEW.md) (the review passes). The binding rules are in
[BASE_RULES.md](BASE_RULES.md); names and terms are in `work/glossary/`.

The English lives in `work/translation/en/` as `*.en.json`: the committed copies of the
working files with the Japanese removed (`tools/strip_jp.py`). The build reads them when
the working files are absent. To rebuild:

1. Put your own dump of the Japanese disc in the repository root as
   `Mouri Motonari - Chikai no Sanshi (Japan).bin` (raw MODE2/2352, single track).
2. `python tools/extract_iso.py "Mouri Motonari - Chikai no Sanshi (Japan).bin" work/source/disc`
3. `python tools/extract_text.py` and `python tools/extract_ui.py` (the Japanese text,
   git-ignored).
4. The English letters come from your own *Skies of Arcadia* (USA, Dreamcast) disc:
   `python tools/skies_font.py` (see its header for the disc path).
5. `python tools/build.py` writes `work/output/test/MouriMotonari.bin/.cue`.

The film subtitles need the re-encoded frames from `tools/movie.py` / `tools/movie_edit.py`
(jPSXdec, see [docs/movies.md](docs/movies.md)); without them the build keeps the original
films.

You need your own copy of the game. This repository contains no disc image, no game data
and no dump of the original Japanese script.

## What is here

| Path | Contents |
|---|---|
| `docs/TRANSLATING.md` `docs/REVIEW.md` | **start here** — the translation brief and the review passes |
| `docs/VWF.md` | the variable-width font: hooks, VRAM layout, the battle-map unit bars |
| `docs/text_formats.md` | menu, item, skill and profile text: formats and insertion |
| `docs/text_inventory.md` | where every kind of text lives, and what is still Japanese |
| `docs/movies.md` | film subtitles: transcription, burning in, re-encoding |
| `docs/debug_tools.md` | DuckStation + GDB tools: virtual pad, VRAM grabs, hot reload, savestates |
| `docs/recruitment.md` `docs/recruit_guide.html` | who joins the Mouri, by episode, and how |
| `tools/` | extractors, script rebuilder, MIPS assembler, the build, VCDIFF patcher, graphics and movie tools |
| `work/translation/en/*.en.json` | the English translation (story, `ui/`, `movie/`) |
| `work/glossary/` | characters, terms, the honorific policy, term fixes |
| `CHANGELOG.md` | every build, what changed, and what broke |

## Do not sell this

This patch is free. Do not sell it, and do not sell anything made with it - no
pre-patched discs or images, no loaded memory cards or consoles, no paywalled or ad-gated
downloads.

It is an unofficial fan translation of a game Koei Tecmo owns. Selling it takes money for
work that was given away, and it is the surest way to get a project like this shut down.

## Credits

| Role | |
|---|---|
| Project lead | pow |
| Proofreading | *none yet - see [Status](#status)* |
| Playtesting | pow |

Translation passes, tooling and reverse engineering used Claude (Anthropic), directed by
pow. The translation is machine-produced and then edited - see the release notes for what
that means in practice.

- Latin glyph pixels: the original *Skies of Arcadia* USA Dreamcast game font
  (SEGA/Overworks), as in the Seireiki Rayblade translation. This project grants no new
  license to that game artwork; no standalone font file is included.
- Film subtitles use [GenEi Late Gothic](https://okoneya.jp/font/genei-latin.html)
  (SIL Open Font License, `tools/fonts/genei-latin/LICENSE.txt`).
- Names follow Japanese Wikipedia and the Koei wiki; see `work/glossary/README.md`.

## Status

The translation is in progress. `CHANGELOG.md` is the honest record, including the builds
that crashed and why.

Every line was machine-translated and then put through separate machine review passes
(accuracy, editorial, proofreading) with a shared glossary: 7,289 story units and 2,523
menu, item, skill and profile units. **No human has proofread it against the Japanese
yet.** The 81 film subtitles come from assisted transcripts of the Japanese voices; a human
listening pass is still outstanding.

In-game checks so far: played by hand up to Episode 8 (story scenes, battles, duels,
training ground, workshop, saving and loading), plus targeted DuckStation checks of the
screens each build changed. The stylized title logo and the Eiketsuden series logo stay in
Japanese. **No full playthrough yet. Real PlayStation hardware has not been tested.**
