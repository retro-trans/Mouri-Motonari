# Translating Mouri Motonari: Chikai no Sanshi — brief for translation agents

Japanese PS1 strategy RPG (Koei, 1998) following the life of Mouri Motonari
(1497–1571), lord of Aki province, from the death of his elder brother Okimoto
to the unification of the Chugoku region and beyond (Sengoku period). Story
scenes (castle, towns, villages) alternate with battle maps.

Read first: `BASE_RULES.md` (binding rules), `work/glossary/README.md`,
`work/glossary/characters.json` and `work/glossary/terms.json`. Look up every
name, place, clan, battle and title there and always use its `en` spelling.
If a name is missing, give your best Hepburn reading and list it in `note`.

## Input

`work/source/text/slices/NNN.json`: 80 units in story order. Each unit:

| field | meaning |
| --- | --- |
| `key` | unit id; copy it to the output |
| `kind` | `dialogue`, `title`, `label`, `choice` (see Format) |
| `first` | where it first occurs: `R_05/1/3/1a2f` = story script part 05 (`S_` = battle map script), event 1, block 3, offset |
| `count` | how many times this exact text occurs |
| `jp` | the Japanese; `\n` = line break |

For context read the neighbouring units, the slices before/after yours, or
`work/source/text/units.json`. Units are in script order, so the unit before
yours is usually the line just before it in the scene.

## Output

`work/translation/en/NNN.json` (same NNN): a JSON list, one object per input
unit, same order:

```json
{"key": "U00123", "en": "English text", "note": "optional: decisions / doubts"}
```

Use `note` for every non-obvious decision (who a line is aimed at, a kept
ambiguity, a restored subject you were unsure of, a tie you broke, a guessed
name reading). Leave `note` out when there is nothing to say.

## Format

* Printable ASCII only (no curly quotes, no accented letters, no macrons:
  "Ryuo", "Okimoto", not "Ryūō"). Use `...` for ellipses (the Japanese often
  uses `……` — one `...` is enough, two for a long trailing pause), `--` for a
  dash or an interrupted line.
* **dialogue**: the Japanese is split into sections by speaker lines `&Name`
  (e.g. `&毛利元就`). Copy every `&` line **exactly as it is in the Japanese**
  (Japanese characters, digits included), same number and order: the game uses
  it to pick the portrait and the name box; a script translates the name box.
  Under each speaker line write that speaker's English text as normal prose.
  Do NOT insert line breaks yourself: the inserter word-wraps to the 168 px
  window and pages every 3 lines. Japanese blank lines are only page padding —
  ignore them, except: put a blank line in your English where a new page
  should start for a deliberate beat (a pause, a change of thought, a reaction
  after "..."). The window is small: about 30 characters per line, 3 lines
  per page; long speeches simply run over several pages, which is fine.
* **title** (chapter / episode titles, location captions such as castle or
  room names): the box fits the text, so write the glossary form in full, up to
  288 px (about 50 characters) per line (e.g. "Chapter 1:
  Unification of Aki", "Koriyama Castle: Council Chamber").
* **label**: *narration* (prose shown in a box without a portrait) is re-wrapped by the
  inserter to 240 px per line; write it as prose and keep the Japanese blank lines
  between parts: each part starts a new page (6 lines per page). *Battle names and
  victory / defeat conditions* (same box): keep the Japanese lines, each up to 240 px.
  Victory-condition lists follow terms.json: `Victory Conditions` / `  1. Takeda Motoshige retreats`.
  *Scene goals* ("Go to the council chamber"; the box fits the text): one line, up to
  256 px, no need to abbreviate.
* **choice** (menu options, one per line): keep exactly the same number of lines and
  break where the Japanese breaks. Each line must fit the width of the longest
  Japanese line of the unit (12 px per Japanese character; English averages
  5–6 px per character, so roughly 2 English characters per Japanese one).
  Full-width spaces used for indentation (e.g. `　一、`) become two spaces.
* Do not translate or alter anything inside `&...` speaker lines.

Check your file before finishing and fix every problem it reports:

    python tools/insert_text.py check work/translation/en/NNN.json

If a title/label line still does not fit after compressing (abbreviate,
rephrase — never drop the end), leave the best version and say so in `note`.

## Style

* This is a historical drama: samurai lords and retainers speak with dignity
  but in natural, modern English (no "thee/thou", no fake archaic grammar).
  Townsfolk, soldiers, bandits and pirates talk casually and colourfully.
  Keep each character's voice (see `personality` in characters.json).
* Restore subjects and verbs that Japanese drops when the scene settles who
  (BASE_RULES); check the direction of 頼む / よろしく / お任せください.
* Honorifics and forms of address follow `work/glossary/README.md` (e.g. 殿 →
  "my lord" when addressing, 兄上 → "Brother", 父上 → "Father").
* Do not soften insults, threats or crude lines.
* Do not infer gender from a name; use characters.json evidence or neutral
  wording.
* Historical facts (dates, battles, ranks) are as the Japanese says; do not
  add explanations.

Do not edit any other file, except your report (below).

## Report

Write your full report (rows examined vs rows in slice, every non-obvious
decision and uncertainty with unit keys, names missing from the glossary, the
checker result) to `work/translation/en/reports/NNN.md`. Your final message
back must be at most 3 lines: rows examined/total, checker result, and the
number of uncertainties logged in the report.
