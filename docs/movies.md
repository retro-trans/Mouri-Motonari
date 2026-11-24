# Movies (MOVIE/MOVIEnn.STR)

Ten STR files: MDEC video 320x240 at 15 fps (STRv2, 10 sectors per frame: 8 video + 2 XA)
and XA audio 37.8 kHz stereo. MOVIE00 is the KOEI logo / title intro; MOVIE01 plays after
New Game (Hiromoto's deathbed, then the map narration of 1506-1516). Story films with
speech, subtitled since 0.2.14 (`work/translation/en/movie/MOVIEnn.json`):

| Film | Scene | Lines |
| --- | --- | --- |
| MOVIE02 | Motonari meets his bride, Lady Myo, under the cherry trees | 6 |
| MOVIE03 | The Lesson of the Three Arrows | 5 |
| MOVIE04 | Before Itsukushima: Miyao Castle, the crossing in the storm | 8 |
| MOVIE05 | Yamanaka Shikanosuke's farewell and prayer | 9 |
| MOVIE06 | Gassan-Toda falls; Motonari looks back; Shikanosuke missing | 14 |
| MOVIE07 | Motonari's deathbed with Motoharu, Takakage and Terumoto | 9 |
| MOVIE08 | Takamatsu: Muneharu's seppuku, the news | 5 |

MOVIE00 (KOEI logo, 英傑伝シリーズ, "An Eiji Fukuzawa Production") and MOVIE09 (ending
film, 完 in the last frames) have no speech. No other film has on-screen Japanese text.

## Pipeline

| Step | Command | Output |
| --- | --- | --- |
| raw sectors | `python tools/movie.py raw MOVIE01` | `work/source/movie/MOVIE01.raw` (2352-byte sectors from the original disc) |
| frames | `python tools/movie.py frames MOVIE01` | `work/source/movie/MOVIE01/NNNN.png` (jPSXdec, NNNN = header frame number, 1-based) |
| speech | `python tools/movie.py audio MOVIE01`, then `<whisper python> tools/transcribe_movie.py MOVIE01` | `work/source/movie/MOVIE01.transcript.json` |
| re-check | `<whisper python> tools/transcribe_clip.py MOVIE04 32 62 [--prompt ...] [--vad]` | prints segments + word times for one stretch |
| translation | edit `work/translation/en/movie/MOVIE01.json` | subtitles (seconds) and labels (frames) |
| edit frames | `python tools/movie_edit.py MOVIE01 [--frames a-b] [--sheet x.png]` | `work/output/movie/MOVIE01/NNNN.png` + `replace.xml` (whole-frame replace) |
| re-encode | `python tools/movie.py patch MOVIE01` | `work/output/movie/MOVIE01.raw`, `replace.log`, `qscale.json` |
| review | `python tools/movie.py preview MOVIE01` | `work/output/movie/MOVIE01.mp4` (decoded by jPSXdec) |
| check | `python tools/movie_check.py MOVIE01 ...` | decoded vs edited error per frame |
| in game | title menu, then `python tools/play_movie.py 5`; `tools/emu.ps1 grab` | New Game plays MOVIE05 instead of MOVIE01 |
| disc | `python tools/build.py` | writes every `work/output/movie/*.raw` over its movie (same LBA and size) |

Tools outside the repository:
- jPSXdec v2.0 (github.com/m35/jpsxdec), unpacked in `work/bin/jpsxdec/app/`; needs Java.
- ffmpeg (audio extraction; demuxer `psxstr`). Its MDEC decoder is not exact (grey blocks
  in re-encoded frames that the console does not show), so frames and previews come from
  jPSXdec.
- Whisper: a 64-bit Python with faster-whisper and the large-v3 model. This machine has one
  in another project (`WHISPER_PY` / `WHISPER_HF` in `tools/transcribe_movie.py`). The
  transcript is checked against the story and names by hand: the first pass misheard names
  (幸千代丸, 尼子), a second pass with the names as `initial_prompt` fixed them.
  `transcribe_movie.py --prompt` passes such a name list. With a prompt, stretches of music
  can turn into loops of a name (尼子勝久、尼子勝久…); `transcribe_clip.py` re-runs one stretch
  without it. Homophones still need the story: 落城 (heard 薬状), 刻限 (黒幻), 両川 (稜線),
  大内 / 尼子 (大口 / 天子), 退く (行く).

## Subtitles

Burned into the frames: GenEi Late Gothic 12 px (`tools/fonts/genei-latin`, SIL OFL), light
grey with a 1 px dark outline and soft shadow, two lines at most, centred 7 px above the bottom
edge, on a translucent dark box (60 %) fitted to the text (`SUB_STYLE = 'box'`, since 0.2.14;
`movie_edit.py --style band|outline|box`). Until then a black band covered y 192-239 (the
player found it too heavy); outline alone was hard to read over light areas (white beards,
sky). The box costs about the same bits as the band (quantization 3-5 in MOVIE06). Each frame has only its 8 video sectors; jPSXdec re-encodes the
whole frame at the lowest quantization scale that fits. Text over the picture needed scale
9-11 (blurry); over a flat band it fits at 3-7 (up to 13 in rain). Times come from the
transcript; frame = round(seconds x 15) + 1.

Whole frames, not partial-replace (since 0.2.14): these STRv2 frames carry one quantization
scale, in the frame header, for all blocks. jPSXdec's partial-replace encoded the changed
blocks at a new scale but kept the header's, so where the scale went up the subtitles (and
MOVIE01's labels) decoded darker and softer by old / new (band peak 148 instead of 210 at
q4 over q3) — on the console as well. `python tools/movie_check.py MOVIE05` decodes the
patched film and compares every edited frame with its PNG (subtitle band and picture).

## On-screen labels (MOVIE01)

Kanji names on the map (大内義興, 尼子経久, 興 → 興元, 武田元繁, 松寿丸, 毛利元就) and the year
永正3年（一五〇六年）. `tools/movie_edit.py` removes them and draws English in the same place:

- Clean background: the map is still behind most labels, so the pixels under a label come
  from a frame of the same shot before the labels appear (`ref`, same phase of the 4-frame
  water cycle), times a smooth per-pixel gain (the map dims unevenly behind the portraits).
- Moving map (`chain`): the zoom / pan is found frame to frame and composed back to the
  nearest still frame, then refined on a ring around the label; the still frame's clean
  plate is resampled once. Only white / dark (text-coloured) differences are replaced.
- Fade-outs over a crossfading map (`fade`): the label's matte is taken from a still frame
  and subtracted ("unblended") at the opacity found by a least-squares fit of its detail.
- English: GenEi, white with a dark outline and shadow, following the Japanese label's
  position, size and opacity per frame (fly-ins and fades); labels that share frames with
  subtitles are lifted above the band. 興 flying from Yoshioki's name to Kochiyomaru
  (一字拝領) becomes "Oki", then the label "Okimoto". The year reads "Eisho 3 / (1506)".
- Known leftovers: a faint seam in the first frames of the year caption (1008-1011, map still
  zooming, text faint) and faint shadow residue under some labels in frames without a band.

Label spec fields (`labels[]` in the translation file): `frames`, `box` (search / edit box),
`ref` (clean frames), `early_boxes` ([until frame, box] for fly-ins), `exclude` (portrait
rectangles), `settled` (frame whose size = scale 1), `hold` (use the settled position),
`chain`, `fade`, `motion_ignore`, `size` (font px), `fixed_scale`.
