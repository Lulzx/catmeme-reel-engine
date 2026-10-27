---
name: make-chat-reel
description: Write and render a group-chat cat reel, where the whole short is a family/office/society group chat and every member is a cat sending texts and video notes. Use when asked for a "chat reel", "group chat episode", "family group video", another episode of i-got-the-job, or a reel in the new chat format. Produces data/chats/<slug>.json and output/<slug>.mp4.
---

# Make a group-chat reel

Full reference: `docs/20-group-chat-format.md` (script schema, every event type,
pacing, renderer internals). Template: `data/chats/i-got-the-job.json`. Run
everything from the repo root.

## Steps

1. **Pick the group and the ending.** One group (family, society, office, school
   parents, wedding planning) and one chat-mechanics punchline: a deleted message,
   "wrong chat", a reaction from the wrong person, someone added or removed,
   "You left" then "added you". Write the ending before anything else.

2. **Cast by role, never by personal name.** Papa, Mummy, Chachu, Bua, Sharma ji's
   son, Secretary uncle, Boss. Keep the recurring cast in their parts: 182 yapapa
   (the endless video note), 184 DEREK (the rival, his laugh), 183 the small
   German cat (the unhelpful forward). Give each person a distinct `color` and an
   `avatar` clip id.

3. **Write `data/chats/<slug>.json`**, one event per line. Open with `t: -1`
   history the audience recognises, then a `compose` + `text` hook. 6–10 messages,
   2–3 video notes, one escalation (someone gets added), the ending. Target ≤ 28s.
   Messages follow `docs/15-human-voice.md`: lowercase, specific numbers and
   times, no em dashes, no noun-phrase punchlines.

4. **Pick video-note clips by sound.** Loud, expressive clips go in video notes;
   find the sound with
   `ffmpeg -i clips/<id>* -af silencedetect=n=-30dB:d=0.25 -f null - 2>&1 | grep silence_`
   and set `start` on the noise. Use `fit: 0.8` for big-face clips.
   Check how often a clip has been used, so the same cats don't star in every
   episode (`engine/allocate.py` only reads story files, not chats):
   `sqlite3 data/videos.db "select clip_id, count(*) n from clip_usage group by 1 order by n desc limit 15"`

5. **Score it** against `.claude/skills/make-reel/SCORING.md` (75 to pass, same
   gates). Rewrite until it clears.

6. **Render and check.**
   ```bash
   python3 engine/chat_render.py data/chats/<slug>.json
   ffmpeg -nostdin -v error -y -ss 12 -i output/<slug>.mp4 -frames:v 1 /tmp/check.png
   ```
   Look at frames from the start, middle and ending. Check that no bubble is cut
   off, the video notes show the whole cat, and the banner is legible.

7. **Queue or publish.** Add a `youtube` block (pov, title, description, tags;
   vary the description), then:
   ```bash
   python3 engine/chat_render.py data/chats/<slug>.json --register
   python3 -m engine.upload <slug>          # publish now; or leave it for the schedulers
   ```
