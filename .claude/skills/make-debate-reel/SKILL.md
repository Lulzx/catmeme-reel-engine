---
name: make-debate-reel
description: Write and render a prime-time news debate cat reel, where a tiny household crime is covered as breaking news with a growing panel of cats, crosstalk and a CCTV reveal. Use when asked for a "debate reel", "news episode", "breaking news video", another episode like who-ate-the-last-maggi, or a reel in the debate format. Produces data/news/<slug>.json and output/<slug>.mp4.
---

# Make a prime-time debate reel

Full reference: `docs/21-prime-time-debate.md` (panel fields, every event type,
writing rules, renderer). Template: `data/news/who-ate-the-last-maggi.json`.
Run everything from the repo root.

## Steps

1. **Pick the crime and the reveal.** Tiny and specific (the geyser left on, the
   AC set to 16, the missing charger, who finished the milk). Decide who the CCTV
   catches before writing anything else; the best reveals turn on the show itself.

2. **Cast the panel by role** (up to 6): host, Mummy (182), Papa (004, says only
   "huh?"), the accused kid, Sharma ji's son (184), an expert (183). Pick each
   panelist's `idle` window (a quiet stretch) and `loud` start from the clip's
   audio:
   `ffmpeg -i clips/<id>* -af silencedetect=n=-30dB:d=0.25 -f null - 2>&1 | grep silence_`
   The culprit's tile and the `cctv` event must use the same clip.

3. **Write `data/news/<slug>.json`**, one event per line. Order: sting, anchor
   alone, family joins, experts join, accusations, crosstalk, EXCLUSIVE sting,
   CCTV with ENHANCE, colour bars on the culprit, two or three closing lines,
   ticker tease for the next episode. Don't rush: hold each quote for 1.4s +
   0.4s per word (min 2.2s), pause 1s after layout changes, and give a lone
   headline 2s. Episodes run 80–100s; the pacing rules are in doc 21.
   Quotes follow `docs/15-human-voice.md`; headlines stay in caps.

4. **Add the announcer.** `voice` events in the Fish Audio "Breaking news" voice
   open the show, read calm anchor lines and headlines straight, and announce the
   reveal. Prep prints each line's length and flags overlaps; retime until clean.

5. **Score it** against `.claude/skills/make-reel/SCORING.md` (75 to pass).

6. **Render and check** (about a minute end to end; GPU render ~27s):
   ```bash
   python3 engine/news_render.py data/news/<slug>.json
   ```
   Review with fframes from `engine/ff_debate` (`FF_WORK=../../work/news/<slug>/media`):
   `cargo run --release -- inspect`, `strip 10s,40s,80s`, `audio analyze`.
   Pull frames from the sting, each layout change, crosstalk, the CCTV and the
   last second. Measure loudness across each line to confirm no cat cuts out
   mid-line. Check that the quote box matches the speaker at the end, that
   name plates fit their tiles, and that the cat is visible in the CCTV.

7. **Queue or publish.** Add a `youtube` block, then:
   ```bash
   python3 engine/news_render.py data/news/<slug>.json --register
   python3 -m engine.upload <slug>
   ```
