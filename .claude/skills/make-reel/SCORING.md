# Script scoring — the gate before anything is rendered or queued

**You score this, not a script.** There is no scoring binary and there should not
be one: every metric here is a judgement about whether something is funny, and a
regex cannot make that call. Read the story JSON, hold the whole thing in your
head, and score it the way a person deciding what to post would.

Every script is scored **out of 100** and must clear **75** *and* every hard gate
before it is rendered, added to `data/videos.db`, or scheduled.

## How to run a scoring pass

1. Read the full `data/stories/<slug>.json` — the `pov`, every beat caption in
   order, and the `outro`.
2. **Read it aloud, start to finish, in one go.** Most of the signal is here. If
   you catch yourself performing enthusiasm to make it work, it isn't working.
3. Score the eight metrics below. Write down the number *and* one sentence of
   reasoning per metric — the reasoning is what makes a rewrite possible.
4. Check the hard gates.
5. Report every script's total in one table, then say plainly which are queued
   and which are being rewritten.

Score cold. The failure mode is grading your own writing generously because the
batch needs sixteen videos. A batch of nine that clears the bar beats sixteen
that don't, and **shipping a below-threshold script is the one outcome that is
not allowed.** If you cut a script, name it and say why.

---

## Hard gates — fail any and it cannot be posted at any total

| gate | why |
|---|---|
| `punchline` < 12/20 | if the last beat doesn't land, the reel has no reason to exist |
| `hook` < 8/15 | if the POV line doesn't stop a thumb, nobody reaches the punchline |
| `human voice` < 10/15 | this channel has been called out for AI scripts twice in 22 comments |
| any asterisk in a caption | rule 18, doc 15 — it renders literally into the frame |
| `python3 -m engine.lint_voice <slug>` reports an **error** | those are the tells viewers named by name |

A 74 with a 19/20 punchline is a setup rewrite. A 78 with a 9/20 punchline is a
**fail** — do not queue it, do not average it away.

---

## The eight metrics

### 1. `hook` — 15
The `pov` line alone. Nothing else on screen for the first second.

- **13–15** — a situation the viewer has personally lived *and* never seen named.
  "POV: the wind flipped your umbrella at the crossing."
- **9–12** — clearly relatable, but the feed has seen this one.
- **5–8** — a category, not a situation ("POV: mondays").
- **0–4** — needs the video to explain what it means.

### 2. `punchline` — 20 *(the money metric)*
The **last beat only**. Not the funniest line in the middle.

- **17–20** — a real turn. A **reversal** (the precaution causes the damage: "the
  bag was also in the puddle"), a **callback** (a beat-1 detail returns changed),
  or an **absurd escalation that stays specific** ("it is now a hot wet sock").
- **12–16** — it lands, but you saw it coming two beats out.
- **6–11** — a wry shrug. "i closed the calendar." "it is 6pm." The narrator
  giving up is where a punchline goes, not a punchline. **Gate fail.**
- **0–5** — the script stops, or the last beat restates the premise.

Test: cover the last beat and write down what you expect. If your guess matches
what's there, cap it at 16.

### 3. `surprise` — 12
Turns anywhere in the script that you didn't predict. The side character
undercutting the narrator counts. A smooth escalation ladder does not.

- **10–12** — two genuine swerves. **6–9** — one. **0–5** — none; it's an arc.

### 4. `human voice` — 15
Does it read like a person telling you something mildly annoying, or like a
performance of being relatable? The full rulebook is `docs/15-human-voice.md`;
run `engine.lint_voice` first so you're only judging what a linter can't.

- **13–15** — flat setup beats carrying real weight, single clauses, nothing
  labelling the feeling.
- **8–12** — mostly clean, one or two lines that are a bit written.
- **0–7** — noun-phrase punchlines, every beat a quip, tidy parallel rhythm.
  **Gate fail below 10.**

### 5. `specificity` — 12
Rule 14. Concrete detail is the cheapest anti-AI signal and it's what people
quote back in the comments.

- **10–12** — four or more real details, and they're load-bearing: "₹80",
  "7:40pm", "slide 12", "eleven days".
- **6–9** — two or three, or they're decorative.
- **0–5** — "some money", "the other day", "a while".

Judge whether the detail *does work*, not whether a number is present. "eleven
things" is worth more than "100%" because it sounds like counting.

### 6. `pace & shape` — 10
5–9 beats. At least a third flat (setup, a timestamp, a plain fact) — real
humour needs boring lines to push off. Arc varied from the last few scripts
(slow burn / anticlimax / flat-then-spike, doc 15 rule 2).

- **9–10** — the shape is doing work and isn't the same as the last three reels.
- **5–8** — serviceable but it's the standard ladder again.
- **0–4** — every beat is a joke, or it's twelve beats long.

### 7. `shareability` — 10
Would a viewer send it to one specific person, or comment "this is literally
you"? Named villains and recognisable roles travel; private moments don't.

- **8–10** — someone gets tagged. **4–7** — relatable but solitary.
- **0–3** — no reason to pass it on.

### 8. `casting` — 6
Do the cats fit the beats, and is the recurring cast in place?

- **5–6** — 182 (yapapa, the one who won't stop talking) and 183 (german cat, the
  small guy with the unhelpful tip) are both cast and *earn* their lines; every
  other beat's clip matches the emotion.
- **3–4** — mascots present but pasted in.
- **0–2** — mascots missing, or a clip fights its caption.

Run `python3 -m engine.allocate --check <slugs>` alongside this: it reports clip
repeats and over-exposed clips across the batch (see `docs/16-clip-diversity.md`).
That's an input to this score, not a substitute for it.

---

## Reporting format

```
slug                     hook punch surp voice spec pace share cast  TOTAL  verdict
one-puddle-at-9am          13    18   10    14   10   9    8     6     88   PASS
...
```

Then, in prose: which are queued, which are being rewritten, and for each
rewrite the one metric that sank it. Never silently drop a failing script.

## Keeping the rubric honest

This rubric is a guess about what works until the numbers say otherwise.
`python3 -m engine.insights` ranks live reels by views/day and
`docs/14-analytics-and-trends.md` records which lanes actually win. Spot-check
occasionally: score three top performers and three flops blind. **If the top
performers score badly here, the rubric is wrong — fix the rubric, not the reels.**
