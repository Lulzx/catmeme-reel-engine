# 15 — Writing captions that don't read as AI

*(Added 2026-07-26, after viewers started calling the scripts AI-generated.)*

The reels have no voiceover (the audio is the cats' own), and the complaints are
specifically about **the caption text**, not the visuals. So this is a writing problem,
and this doc is the writing rulebook.

(Background reuse is a separate, real problem — `home` covers 35% of all beats, which
makes the feed look samey — but it is not what viewers were reacting to. See rule 13
and doc 06.)

## The two comments that triggered this

Out of 18 comments channel-wide, exactly two were the complaint — but they're precise:

- **`fan-hot-air`** — *"Hey chatgpt"*, clarified in a reply as
  *"i mean like 'hey chatgpt generate me a cool story of ......'"*
- **`final-day-schedule`** — *"Holy AI script"*

Both scripts share the same fingerprint:

```
*cheek pressed to the fan cage. peak desperation.*
*accepting the puddle life. deadpan.*
*lucky jersey on. couch coordinates locked in.*
*face down. muted. the ritual is protected.*
```

Three things are happening in every one of those lines:
1. a **noun-phrase fragment used as a punchline** ("peak desperation.", "genius.",
   "the ritual is protected.") — this is *the* signature, more than any other tell;
2. **two clauses welded with a full stop** into a tidy little rhythm, every single beat;
3. in `fan-hot-air`, the emotion tag itself leaked into the caption — *"deadpan."* is a
   `want` tag, not something a person writes.

Everything else in the comments was positive. The fix is narrow: kill this register.

## What else was giving it away

Measured across 112 stories / 872 captions:

| Tell | Evidence | Why it reads as AI |
|---|---|---|
| One arc, every time | every story an 8-beat setup→escalate→panic→defeat | a human writing 112 jokes would not land on the same shape 112 times |
| Every beat is a joke | ~100% of captions are quips | real humour needs flat setup lines to push off |
| Punctuation tics | em dash in 5%, `...` in 9% of captions | the em-dash/ellipsis habit is the single most-named LLM tell |
| Mirrored wit | "fun fact FIRST, name last, role never" | the tricolon/parallel-inversion is an LLM reflex |
| Metaphor closers | "soul buffering", "I am now wallpaper" | abstract-noun punchlines are a generated-text signature |
| One ALL-CAPS word per script | AGAIN, THIS, NOT, KID | mechanical emphasis, applied on schedule |
| Title Case titles | "You Tell A Joke In The Group Chat…" | nobody types like this |
| One outro on 45 videos | `FOLLOW IF THIS IS YOU` ×45 | identical furniture across a feed |
| Narrating the picture | "the fake professional smile activates" | captions should add what the image can't show |
| Asterisks on screen | `*i pull it*` in all 872 captions | markdown emphasis rendered literally into the frame — see rule 18 |

## The rules

**Shape**
1. **Vary the beat count** — 5 to 9, deliberately different per story. Not every joke
   needs an escalation ladder; some are two beats of setup and a hard cut.
2. **Vary the arc.** Three shapes to rotate: *slow burn* (escalate to a peak),
   *anticlimax* (build, then nothing happens — that's the joke), *flat-then-spike*
   (four boring beats, one detonation).
3. **At least a third of the beats must not be funny.** Setup, timestamps, plain
   statements of fact. `*3am*` is a complete beat.

**Line level**

4. **No noun-phrase punchlines.** This is the one that got called out. Never end a beat
   with a labelling fragment: *peak desperation. / genius. / the ritual is protected. /
   couch coordinates locked in.* If the line names the feeling instead of showing the
   thing, cut it. Say what happened, not what it amounts to.
5. **Never let a `want` tag into a caption.** "deadpan", "resigned", "defeated" are
   matcher inputs. The cat's face does that job; writing it too is the giveaway.
6. **Stop welding two clauses per beat.** "*cheek pressed to the fan cage. peak
   desperation.*" is the house rhythm and it's mechanical. Most beats should be a
   single clause. Let some be three words.
7. **No em dashes.** Use a full stop or start a new beat.
8. **One `...` per script, maximum.** Zero is better.
9. **No metaphor punchlines.** Ban abstract-noun closers: soul, void, chaos, buffering,
   personality, existence. End on a concrete action or a plain admission instead
   ("i ate it anyway", "still didn't refill it").
10. **No parallel/mirrored constructions.** If a line has a satisfying A-B-C rhythm,
    break it.
11. **Max one ALL-CAPS word per script**, and only where a person would genuinely shout.
12. **Lowercase everything**, titles included. Capitalise only proper nouns.
13. **Don't caption what's already on screen.** If the cat looks panicked, the caption
    should say something the picture doesn't.
14. **Be specific.** "₹40" beats "some money". "the 7:12 bus" beats "the bus". Concrete
    detail is the cheapest anti-AI signal there is, and it's what people quote back.

**Punctuation of the caption itself**

18. **No asterisks. Use quotes.** *(added 2026-07-30)* The caption is drawn to the
    frame literally — `*i pull it*` puts two visible asterisks on screen, which is
    markdown leaking into a video. Two forms only:
    - **spoken line → double quotes:** `"i can jump this"`
    - **narration → bare text, no markers at all:** `it is 6pm.`

    Lean on the quoted form. A line someone actually says is concrete by
    construction, which is most of rule 4 and rule 13 for free — `*peak
    desperation.*` isn't a thing anyone says out loud, so the register that got
    called out can't survive the rewrite. The italic font still applies, so quoted
    dialogue and bare narration stay visually distinct without any punctuation
    doing the work.

**Furniture**

15. **Rotate the outro**, and write it in the same voice as the script. Never reuse the
    same card more than ~3 times in a batch.
16. **Rotate backgrounds.** `home` was 35% of all beats. Pick the scene the joke actually
    happens in, and don't repeat one scene across consecutive videos in a batch.
17. **Vary the description.** The identical boilerplate + hashtag block on every upload
    reads as automated to both viewers and the algorithm.

## These rules are a floor, not the goal

Everything above is about not sounding generated. It is not the same thing as being
funny, and a script can pass every rule here and still be a wry shrug that nobody
laughs at. Endings like *"i closed the calendar."* clear the linter and fail the
reel.

So the last beat carries the reel: a **reversal** (the precaution causes the
damage), a **callback**, or an **absurd escalation that stays specific**. The flat
beats in rule 3 exist to give that ending something to push off. Scored explicitly
as the `punchline` metric in
[`.claude/skills/make-reel/SCORING.md`](../.claude/skills/make-reel/SCORING.md),
which gates what gets rendered.

## The sniff test

Read the script aloud. If it sounds like a *performance of being relatable*, it's wrong.
If it sounds like a friend telling you something mildly annoying that happened, it's right.

Then check: could this caption sit in any other video in the batch? If yes, it's too
generic. Make it specific to this one situation.
