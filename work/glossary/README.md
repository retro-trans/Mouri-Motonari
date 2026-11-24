# Glossary: Mouri Motonari: Chikai no Sanshi (English)

Files:
- `characters.json`: 300 entries. All 273 speaker labels from `work/source/text/speakers.json`, plus 19 named people who are mentioned but never speak or speak only under a generic label (`"speaking": false`; Ayame, Sakichi and Iku were added 2026-10-28).
- `terms.json`: 1101 entries (604 added from the UI gaps pass, 2026-10-28). Chapters and episodes, battles and battle UI text, provinces and regions, castles, other places, caption and room words, clans and factions, the honorific policy, game terms, unit classes, items, skills and minor (non-speaking) names. An optional `short` field gives the menu/caption short form where the full form does not fit.
- `term_fixes.json`: the replacement table for `tools/apply_terms.py` (wrong renderings found in the corpus -> glossary form). Re-run `python tools/apply_terms.py` (dry run) and `--apply` after every review pass; agents' edits come first, the script after.

## Character fields
`jp`, `en` (ASCII, used in game text), `en_macron` (reference), `short` (only when `en` > 16 chars, for the ~100 px name box), `reading` (kana, family and given name separated by a space), `reading_confidence` (`wikipedia` / `game_wiki` / `guess` / `generic`), `gender` and `gender_evidence`, `role`, `personality`, `nicknames`, `historical`, `speaking`, `lines` (count from speakers.json), `first_unit`, `sources`, and `note` where something was decided or is in conflict.

## Romanization
- Modified Hepburn. Japanese order: family name first ("Kikkawa Motoharu", "Kobayakawa Takakage").
- `en` has no macrons because the game font is ASCII-only. A long vowel is written as a single letter (ō→o, ū→u): "Saito", "Hanzo", "Ouchi", "Kono". `en_macron` keeps the macrons.
- **Fixed exception:** 毛利 is always **"Mouri"**, never "Mori", to match the game's official title (*Mouri Motonari: Chikai no Sanshi*) and the project name. This applies to compounds too ("Mouri Army", "Mouri clan").
- 兵衛 (べえ) → "-bei" (Kanbei, Zenbei, Jubei, Shinbei).
- Childhood names are written as one word: Tokujumaru, Takewakamaru, Takechiyo, Komatsumaru. 少輔太郎 / 少輔次郎 → "Sho no Taro" / "Sho no Jiro", as the Koei wiki writes them. Family members call them "Taro" / "Jiro".
- Name-box short forms use the given name ("Takakage", "Hideyoshi"). Where that would clash with another character's given name, the short form is "Surname I." ("Shishido M.", "Matsudaira H."). The 16-char limit is a proxy and still needs to be measured.
- Women: 〜の方 → "Lady X" (Lady Sugi, Lady Fuji, Lady Aio), 〜姫 → "Lady X" (Lady Kiku, Lady Myo). "Okata" stays a name. The Koei wiki uses "Sugi no Kata" etc. instead; this is a style choice for the user to confirm.
- Reading sources, in order of priority: the Wikipedia (ja) person article, then the ja.wikipedia article on the game (毛利元就 誓いの三矢), then the Koei fandom wiki. Every conflict is recorded in that entry's `note`.

## Honorific and address policy (full list in terms.json, `type: honorific_policy`)
- Never keep -dono or -sama as suffixes.
- Bare 殿 (との) → "my lord" when addressing him, "His Lordship" / "our lord" when speaking about him. 殿 read しんがり means **rearguard**.
- 〜殿 → "Lord X" for lords, superiors and allied daimyo. Between peers or to inferiors, drop it and use the plain name.
- 〜様 → "Lord X" (lords), "Lady X" (women), "Master X" (a lord's children, clergy). 〜公 → "Lord X".
- **Succession (user decision 14A, 2026-10-28):** an heir is "Master X" until his succession and "Lord X" after it. Komatsumaru: "Master" up to U00071, "Lord" from U00094 (Okimoto's death) on. Terumoto: "Master" up to U05353 (he refuses the headship in R_19 and is never shown accepting); "Lord" from U05415, after the narration U05409 that tells of his succession. Keys-limited rules `komatsumaru-lord` / `terumoto-master` in `term_fixes.json`.
- **Heirs and teachers (15A):** "Master X" for any heir who is not yet head of his house (Master Sho no Taro, Master Magoshiro, the young Shikanosuke at home in U03269-U03270) and for teachers (Master Okura). Rule `shikanosuke-master`; the adult Shikanosuke (U04606 on) stays "Lord Shikanosuke".
- **Retainers among themselves (17A):** plain names between Mouri retainers, even with 殿 ("Fukubara", "Saka"; U00122, U00431, U00441, U00443). "Lord X" is kept for independent lords and other houses' castle lords (Koi, Kagawa, Kumagai, Shimizu) and for another house's senior retainer named by someone outside the Mouri retainers (U00059, Lady Aio: "Lord Kamei").
- Lady Sugi keeps plain names for Motonari and Komatsumaru (16A).
- Missionary voice (20A): halting-comma style; see 宣教師 `personality` in characters.json.
- 兄上/兄者 → "Brother". 父上 → "Father". 母上 → "Mother". 叔父上 → "Uncle". お爺さま → "Grandfather". お侍様 → "sir". 親方 → "Master". 大殿 → "my lord" / "the old lord".
- All first-person pronouns (拙者, それがし, わし, 私) → "I". Show register through word choice, not archaic pronouns. 貴様 is hostile, so make the line itself rude.

## Generic speaker labels
- Every label is ≤16 chars and gender-neutral wherever the label is shared by many NPCs: Townsperson, Farmer, Soldier, Elder (老人 includes old women), Swordsman, Apothecary, Monk, Komuso Monk, Ninja, Pirate, Bandit, Strategist (軍師), Tactician (兵法家), Yamabushi, Merchant, Retainer, Drill Officer, Storekeeper, Missionary, Biwa Minstrel, Workshop Clerk, Supply Unit, Cavalry, Spearmen, Page, Commander, Mouri Soldier, Mysterious Monk.
- Gendered only where the label itself is gendered: Boy, Girl, Maid (侍女), Kunoichi, and the wives (Takamoto's Wife, Motoharu's Wife, Takakage's Wife, Hirotada's Wife for 室). 鹿之介の母 → "Shikanosuke's Mother", short "Lady Yamanaka".
- The script numbers duplicate generic speakers (兵士3, 武将9). The numbers were already stripped. It is not known whether the game shows them. If it does, append " 1", " 2", etc. and stay within the width.
- For a generic speaker, never pick he/she from the label alone. Read the scene.

## Gender
Gender was taken only from Wikipedia (historical people) or from script evidence (男/息子/娘/父/妻, how others address them, くノ一). It was never inferred from a name. **44 named non-generic characters remain `unknown`** (Utajima Shigezo and Tsuchiya Yukaku were set to male from script evidence on 2026-10-28; Sakichi was added as unknown). These are mostly game-original craftsmen whose lines contain no gender marker. Before using he/she for them, check the in-game portrait, or use neutral phrasing.

## Guess readings (`reading_confidence: "guess"`, 57)
Game-original characters with no reading found online (no game wiki, guide or Wikipedia entry gives one):
志乃 しの, 斉栄 さいえい, 土谷幽覚 つちや ゆうかく, 穂村忠重 ほむら ただしげ, 関義信 せき よしのぶ, 伊木尋長 いぎ ひろなが, 村田三十郎 むらた さんじゅうろう, 猪垣三郎太 いがき さぶろうた, 小島善兵衛 こじま ぜんべえ, 九門村重 くもん むらしげ, 石山越忠 いしやま えつただ, 百舌鳥一草 もず いっそう, 手島松吾 てしま しょうご, 竹間貞国 たけま さだくに, 徳俵米造 とくだわら よねぞう, 米倉与六 よねくら よろく, 津田余市 つだ よいち, 雪見風綱 ゆきみ かぜつな, 大蔵真之進 おおくら しんのしん, 唐島通典 からしま みちのり, 諏訪雁次郎 すわ がんじろう, 比古重春 ひこ しげはる, 居駒忠良 いこま ただよし, 剣持六郎 けんもち ろくろう, 加藤権六 かとう ごんろく, 新藤光胤 しんどう みつたね, 日生紀秋 ひなせ のりあき, 相馬宝雪 そうま ほうせつ, 斉藤小六 さいとう ころく, 神楽双円 かぐら そうえん, 沼田八兵衛 ぬまた はちべえ, 山之上為次 やまのうえ ためつぐ, 三笠陣左 みかさ じんざ, 長谷部宗安 はせべ むねやす, 板野蔵源八 いたのくら げんぱち, 野間兵三郎 のま へいざぶろう, 小野堂軒 おの どうけん, 桐生新兵衛 きりゅう しんべえ, 国瓦長高 くにがわら ながたか, 根本甚助 ねもと じんすけ, 羽佐間元景 はざま もとかげ, 安岐信治 あき のぶはる, 馬島十兵衛 まじま じゅうべえ, 矢ノ原祐秀 やのはら すけひで, 宇田島茂造 うたじま しげぞう, 楢岡源坐 ならおか げんざ, 福延大膳 ふくのぶ だいぜん, 田路彦一 とうじ ひこいち, 高橋右京太 たかはし うきょうた, 江尻又造 えじり またぞう.
Minor names not found on Wikipedia: 新里式部 にいざと しきぶ, 右田重正 みぎた しげまさ, 石川久孝 いしかわ ひさたか, 粟屋 あわや, 佐吉 さきち, 松 まつ, 竹 たけ.

Place readings that are guesses (terms.json): 船山城 Funayama, 宝満山城 Homanzan, 音明城 Otoake (probably the game's spelling of 乙明城), 青光井山 Aomitsui, 沢渡川 Sawatari.

## Resolved gaps (2026-10-27)
The 108 gaps in `work/translation/en/reports/_glossary_gaps.md` are settled in `terms.json` (each entry's `note` says why). The corpus was normalised by `tools/apply_terms.py` (97 line changes in 95 units). These forms are on the do-not-touch list (`docs/REVIEW.md`):
- **Ranks:** 大将 in the troop ranks = **Captain** (Spear / Archer / Rifle / Mounted Archer Captain); the Japanese rank word is 大将 in all four, "General" would blur with 総大将 "commander-in-chief".
- **Fortune grades:** Great Blessing / Blessing / Small Blessing / Curse / Great Curse.
- **Items:** 回復薬 Restorative vs 気付け薬 **Stimulant** (they had been merged). Heal Rice / Heal Barley / Heal Meat / Heal Tea / Heal Sake. Minor / Major Heal Medicine. Menu abbreviations are the `short` values and are used only where the menu width forces them.
- **Victory conditions:** ～を退却させる = "Make X retreat" (given name only over 168 px); ～の退却 = "X retreats". The distinction is kept because the Japanese differs (causative vs noun).
- **Captions:** 到着した "arrived.", 現れた / 登場した "appeared.", "X joined your army.", always with a period; 援軍 "reinforcements" (then "relief army", then given name, never bare "relief"); 本城 "<Given>'s Seat: <Castle>", 居城 "<Given>'s Castle: <Castle>"; "Episode N:" up to 36 chars, else "Ep. N:"; Episode 1 is now "The Young Eagle's Debut".
- **Named techniques:** shouted ninjutsu "Art of X"; skill-menu names keep "X Art".
- **Names:** the お prefix on commoners' names is dropped (Ume, Iku, Rei, Yuki; Okata is the exception). 広家様 = "Master Hiroie". 奥方様 = "Her Ladyship" (spoken about) / "my lady" (spoken to). おやじ様 = "Father" (was "Pops"). 甲山城 = Koyama (characters.json role text fixed).
- **Other:** Movement (stat), written oath (起請文), the ninja arts (忍術), ninja (忍び), military / civil faction, bonesetting, encirclement, Yamato-Koriyama, the Master of the Storehouse.
- **Documented width exceptions** (left as is): U00902 "See vassals" (60 px slot); U02131 and U03524 "... joined your army" without period (36 chars); U05665 "Shikanosuke's Amago remnants arrived" (36 chars; "appeared" does not fit).
- **Still guesses:** Norimitsu, Muneshige, Kuro, Kobuse.
- The "possible source errors" list stays in the gaps report; nothing was changed for it.

## Unresolved or for the user to decide
1. Whether to keep "Mouri" as the only ou-spelled exception (alternative: wapuro "ou" everywhere, e.g. "Saitou").
2. 世鬼政清: **Seki** Masakiyo (ja.wikipedia game article, and the historical 世鬼 family) vs "Seiki" (Koei wiki). Chose Seki.
3. 斉栄: Saiei chosen; the Koei wiki has "Sai'ie". 土谷幽覚: Yukaku chosen; the Koei wiki has "Yuugen".
4. 和田与一: "Yaichi" per the Koei wiki (normally よいち "Yoichi"). 斉藤辰美: "Tatsuyoshi" per the Koei wiki (could be Tatsumi).
5. 妙姫: みょう "Myo" per the Koei wiki ("Myōhime"). The kanji could also be read たえ "Tae".
6. 福原 is Fukubara (Wikipedia person articles; the brief's instruction). The game article and the Koei wiki use Fukuhara. 渡辺通 is Kayo (Wikipedia, Koei wiki); the game article uses Toru. 尼子誠久 is Sanehisa (person article); the game article uses Masahisa. 吉見正頼 is Masayori (Koei wiki); Wikipedia gives Tadayori/Masayori.
7. 志道広忠 has no historical record under that name; the historical heir was Shiji Motoyasu. Marked `historical: false`. 安藤景綱, 江田隆連, 新里式部 and 右田重正: historicity is unverified.
8. 菊姫 marries Shishido Takaie, Kunishi Motosuke or Kodama Naritada depending on the story branch (U01415–U01418, U01686–U01688).
9. 武芸者 label: "Swordsman" matches the unit class. Switch to "Martial Artist" if a female 武芸者 line is confirmed.
10. Name-box width (16 chars ≈ 100 px) has not been measured. Shorts may need to change after the font width check.
11. The 44 `unknown` genders listed above need portrait checks.

## Follow-up pass (2026-10-28)
The glossary questions from the accuracy and editorial passes are settled or moved to the user: see `work/translation/en/reports/_followup.md` and `_decisions.md`. New do-not-touch forms: "the Mouri Army" (毛利軍), "the Mouri clan" (毛利家), "head of the clan" (当主), "Nagato-Katsuyama" in dialogue too, room captions "Koriyama / Katsuyama / Yuzuki Castle: <Room>", caption pattern "X retreated." (退却) / "X withdrew." (撤退).

## User decisions applied (2026-10-28)
All 21 items of `work/translation/en/reports/_decisions.md` were answered with option A; the changes are logged in `_decisions_applied.md`. New do-not-touch forms: "Lord Komatsumaru" from U00094, "Master Terumoto" up to U05353, "Master Shikanosuke" in U03269-U03270, plain names between Mouri retainers, the missionary's halting-comma voice, the title card "Mouri Motonari: Oath of the Three Arrows".

## UI gaps pass (2026-10-28)
Source: `work/translation/en/ui/reports/_gaps.md`; what changed is logged in `work/translation/en/ui/reports/_gaps_applied.md`; open questions are in `_ui_decisions.md`.
- **Added:** the 603 Section 1 terms of the UI drafts (weapons, armour, books, materials, skills, ranks, battle UI, menus, places, offices and history words), each with its UI keys in `sources`; `short` is the menu form where it differs. Eight people went to `characters.json` (Ichifuji Yoshinori, Amago Masahisa, Amano Tokage, Ashikaga Yoshitane, Kitabatake Tomofusa, Kanbe Tomomori, Suzuki Shigehide, Sakon). Childhood names and variant kanji went into the existing entries' `nicknames` (海賊丸 Kaizokumaru, a guess; 虎市丸 Toraichimaru; 松寿丸 Shojumaru; 鹿之助; 妙の方 / お妙). 雷切 "Raikiri" is a sword (terms.json).
- **Readings that follow the game's furigana:** 鳥籠山 = **Tokonoyama** (P0025-P0027; was the guess "Torikagoyama"; label "Tokono."; script U00672 fixed by the `tokonoyama` rule); 保木 = **Hogi** (P0440; keeps it apart from the province Hoki).
- **Guesses:** 一藤 Ichifuji, 海賊丸 Kaizokumaru, 紅切 Benikiri, 魂霧 Tamagiri, 合鍛 Awase, 伊東祐忠 Ito Suketada, and the town labels Shirayama, Kashirazaki, Ueshi.
- **Menu shorts:** the 49 shorts of Section 1.11 and the 10-byte skill-menu shorts ("Psn. Arrow", "Dnc. Blade", "Train. Art", "Home / Valor / Cheer Song" ...). A `short` is used only where the menu width forces it.
- **Style rules (I-17, I-29, I-36):**
  - 兜: **"Helm"** in item names (width: "Ridge Helm", "Fudo Helm"), **"helmet"** in prose and descriptions (I0123, I0219, I0227).
  - 武将: **"Officer(s)"** for the UI role word (unit lists, profession column, "Officers (%s)", descriptions "officer"); the generic speaker label in the script stays **"Commander"** (characters.json 武将).
  - 深手: the status label is **"Wounded"**; the onset message says a unit **"is badly wounded"**; the cure says it is **"no longer wounded"**. Do not use "bad wounds" or "injured".
- **Other rules settled in this pass:** one word per Japanese armour word (桶側 Barrel, 仏胴 Solid, 南蛮 Nanban, 筋兜 Ridge, 熊毛 Bear Fur, 水牛 Buffalo, 籠手 bracers, 胴具足 body armor); 大型 / 小型 = "Lg." / "Sm." with a space where 72 px allows (no space in Sm.Bamboo Bow, Sm.Rattan Bow, Lg.Bamboo Bow, Lg.Shigeto Bow: documented width exceptions); "Nanb." only where "Nanban" does not fit; 名品 = "Fine" in menus, "Masterwork" in dialogue; 倉庫 = "the Storehouse" in messages, "Stores" as the menu short; 蔵 short "Vault" (terrain only); terrain words in prose follow the terrain names ("uplands", "woods", "shoals"); 技能値 = "Skill Points" (capitalised); 怨の祈祷 / 恨の祈祷 = "Hex Rite" / "Spite Rite"; 水軍の将 = "naval commander", navies capitalised ("the Bungo Navy"); 本家 / 別家 = "main house" / "branch family"; 一向衆門徒 = "the Ikko followers"; the Ep. 7 Ouchi campaign = "the Ouchi attack on Gassan-Toda Castle" (the Ep. 17 battle stays "Siege of Gassan-Toda Castle").
- **Pending (user):** I-01 manual tiers, I-05 Store/Retr., I-07 Koyama / Kabutoyama, I-09 Lady Myo / Okata, I-20 Faranki / Furanki, I-26 Armsmith, I-28 Artisan / Trainer, I-38 / I-39 battle names, I-43 土豪, I-52 Nagato-Katsuyama label. The glossary records the current forms with "pending" in the note.
