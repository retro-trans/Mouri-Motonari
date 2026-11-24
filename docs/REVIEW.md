# Review passes — brief for review agents

BASE_RULES.md defines three stages, each by separate agents, one slice of 80
units each: **accuracy** → **editorial** → **proofreading**. Read BASE_RULES.md
(the "Shared review workflow" and the section for your stage) and
docs/TRANSLATING.md (format and limits) first. They are binding.

## Inputs

* `work/source/text/slices/NNN.json` — the Japanese (units in story order).
* `work/translation/en/NNN.json` — the English to review (`key`, `en`, `note`).
* `work/translation/en/reports/NNN.md` — the translator's report: every
  uncertainty listed there must be examined and resolved or confirmed.
* Context: the neighbouring slices (Japanese and English), `work/source/text/units.json`.
* Glossary: `work/glossary/characters.json`, `terms.json`, `README.md`.

## Do-not-touch list

Names and terms are fixed by script (`tools/apply_terms.py`), not by agents.
Do not change the spelling of any character name, place, castle, clan, battle,
title, rank, item or other term that is in the glossary, even if you would
prefer another form: if you think a glossary form is wrong, say so in your
report. Never edit `&` speaker lines.

## What to change

Edit `work/translation/en/NNN.json` in place: only the `en` of units that have
a real problem for your stage (keep `key` order; you may update `note`). One
unit in, one unit out. Keep line counts of title/label/choice units. Then run
`python tools/insert_text.py check work/translation/en/NNN.json` and fix every
reported problem.

* **Accuracy** (stage 1): compare with the Japanese in scene order — meaning,
  missing/added details, speaker→listener direction, referents, emotional
  force, deliberate pauses/fragments, restored subjects and verbs. Resolve each
  translator uncertainty where the scene allows; keep an ambiguity only where
  the scene genuinely does not settle it.
* **Editorial** (stage 2): clarity, flow, natural spoken English, character
  voice and register (lords vs commoners), consistent wording. Fix what is
  wrong; leave what is merely different. Return meaning doubts to accuracy
  (report them, do not guess).
* **Proofreading** (stage 3): spelling, grammar, punctuation, typos, duplicated
  or missing words, formatting. No stylistic rewrites.

## Report

Write `work/translation/en/reports/<stage>_NNN.md` (stage = `acc`, `edit` or
`proof`): rows examined vs rows in slice, edited unit keys with the reason for
each substantive change, translator uncertainties resolved / kept, suspected
glossary errors, and your own uncertainties. Final reply: at most 3 lines (rows
examined/total, units edited, checker result).
