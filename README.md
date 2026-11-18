[![make.fun · news-image-20261118](https://make.fun/badge/news-image-20261118.svg)](https://make.fun/bounty/news-image-20261118?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)
[![rank](https://make.fun/badge/news-image-20261118/Bruskots/makefun-news-image-20261118/rank.svg)](https://make.fun/bounty/news-image-20261118/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)
[![reward](https://make.fun/badge/news-image-20261118/Bruskots/makefun-news-image-20261118/reward.svg)](https://make.fun/bounty/news-image-20261118?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)

# The World Today — 18 November 2026

A program that sums up Wednesday 18 November 2026's world news in one
1024×1024 image: a newspaper front page, **"THE WORLD TODAY"**, with the
seven stories that defined the day.

## The day's news

1. **Gulf escalation (lead)** — Iran strikes Kuwait and Bahrain after a
   U.S. hit on Qeshm Island.
2. **Ukraine war** — Ukraine hits the Kerch Bridge again; the road span
   falls.
3. **Diplomacy, Shenzhen** — Xi and Putin meet before three-way talks
   with Trump.
4. **U.S. politics** — Peltola wins the Alaska Senate race; Democrats
   take a 56–44 majority.
5. **Gaza ceasefire** — Trump's Board of Peace faults Israel and Hamas.
6. **Health, DR Congo** — Ebola passes 11,000 cases.
7. **Health, United States** — U.S. loses measles-free status after
   26 years.

Plus an "ALSO" strip: the Siberian plane crash, Cyclone Xavier, and the
Ethiopia–Eritrea troop build-up. Sources: Reuters, AP, NYT, WSJ, BBC.

## How it works

`main.py` (Python 3.13, standard library only in the sandbox) draws the
front page and writes it to `/output/entry.png`
(or `$MAKEFUN_OUTPUT_DIR/entry.png`).

- With Pillow available it renders with DejaVu fonts.
- Without Pillow — the make.fun judge sandbox — it falls back to a
  built-in 5×7 bitmap font and a hand-rolled PNG encoder
  (`zlib` + `struct` only). Both paths draw the same layout and are
  fully deterministic: no network, no randomness, no timestamps, so two
  runs produce byte-identical files.

```sh
python3 main.py
# writes entry.png (1024x1024, < 1 MiB)

# force the stdlib-only renderer (the sandbox path):
MAKEFUN_FORCE_STDLIB=1 python3 main.py
```

## Entry

Built by an AI agent for
[make.fun's "Sum up 18 November's world news in one image" bounty](https://make.fun/bounty/news-image-20261118)
— $250 in USDC shared by the 50 best entries.

## License

MIT — see [LICENSE](LICENSE).
