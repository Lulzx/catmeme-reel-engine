#!/usr/bin/env python3
"""Build catalog.json — the once-computed clip library.

Combines:
  - technical metadata probed from each video (duration, w/h, orientation)
  - the dominant green key-color, sampled from a representative frame
  - hand-authored emotion descriptors (from one-time visual analysis)

The resulting catalog.json is what an LLM matches against later, so it never
needs to re-watch the videos.
"""
import json, os, glob, subprocess, collections
from PIL import Image
import paths
from paths import CLIPS, FRAMES, CATALOG

paths.ensure()

def extract_frame(clip_path, idx):
    """Extract one representative frame (~40% in, capped at 8s) if missing."""
    fp = os.path.join(FRAMES, f"{idx}.jpg")
    if os.path.exists(fp):
        return fp
    dur = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=nk=1:nw=1", clip_path], capture_output=True, text=True).stdout.strip()
    ts = min(float(dur or 0)*0.4, 8)
    subprocess.run(["ffmpeg","-nostdin","-v","error","-ss",str(ts),"-i",clip_path,
        "-vframes","1","-vf","scale=320:-1", fp, "-y"], check=False)
    return fp

# --- one-time visual + title analysis (the "describe once" step) -------------
# primary  : the dominant feeling in one phrase
# emotions : searchable tags an LLM can ask for
# action   : what the cat physically does
# sound    : character of the clip's own audio (this audio is kept in the edit)
# use_for   : natural-language guide for when to drop this clip into a story
# quality  : good | partial (imperfect key / real bg) | low (tiny/blurry) | avoid
EMO = {
 "001": dict(primary="explaining / lecturing", emotions=["explaining","lecturing","pointing","matter-of-fact","presenting","making-a-point"], action="cat stands upright and gestures with a paw as if explaining", sound="talking-style meowing", use_for="laying out an argument, mansplaining, presenting a plan", quality="avoid", note="8-min compilation, too long for a single beat"),
 "002": dict(primary="dramatic shock", emotions=["dramatic","shocked","gasp","betrayed","theatrical","disbelief"], action="kitten recoils dramatically", sound="dramatic gasp/mew", use_for="a shocking reveal, theatrical betrayal, gasp moment", quality="good"),
 "003": dict(primary="goofy derp", emotions=["goofy","derp","silly","confused","dumb","blep","clueless"], action="cross-eyed cat with tongue out", sound="soft derpy noise", use_for="acting dumb, a clueless reaction, brain-empty moment", quality="good"),
 "004": dict(primary="deadpan 'huh?'", emotions=["huh","confused","deadpan","unimpressed","what","skeptical","blank-stare"], action="cat sits and stares flatly", sound="flat 'huh?' meow", use_for="not understanding, a deadpan 'what?', unimpressed silence", quality="good"),
 "005": dict(primary="slap / attack", emotions=["slap","attack","smack","violence","conflict","retaliation","fight"], action="one cat smacks another", sound="quick scuffle", use_for="someone gets hit, instant retaliation, a slap to reality", quality="good"),
 "006": dict(primary="disgust / gagging", emotions=["disgust","gagging","nausea","grossed-out","revulsion","ew","yuck"], action="cat gags over food", sound="gagging/retching", use_for="something disgusting, an 'ew' reaction, revulsion", quality="good"),
 "007": dict(primary="driving away", emotions=["driving","commuting","road-trip","leaving","going-somewhere"], action="cat grips a steering wheel", sound="ambient", use_for="commuting, driving off, heading somewhere", quality="partial", note="real car interior, only partial green"),
 "008": dict(primary="sad pleading", emotions=["sad","crying","pleading","sorrow","disappointed","melancholy","defeated"], action="close-up of a teary-eyed cat meowing softly", sound="sad little meow", use_for="defeat, heartbreak, pleading, walking away disappointed", quality="good"),
 "009": dict(primary="yapping / ranting", emotions=["talking","complaining","ranting","yapping","crunching","arguing"], action="cat with mouth working, chattering", sound="continuous crunchy meowing", use_for="ranting, non-stop yapping, complaining at length", quality="good"),
 "010": dict(primary="zoning out", emotions=["zoning-out","blank","dissociating","spaced-out","daydreaming","tired","checked-out"], action="black cat stares into space", sound="ambient", use_for="mentally checking out, dissociating mid-conversation, going blank", quality="good"),
 "011": dict(primary="couple talking", emotions=["talking","conversation","gossip","couple","discussing","relationship"], action="two cats face each other talking", sound="back-and-forth meows", use_for="a conversation, gossip, a couple bickering, discussing", quality="good"),
 "012": dict(primary="rage scream", emotions=["screaming","rage","yelling","outburst","shouting","furious","explosion"], action="cat throws head back and screams", sound="loud cat scream", use_for="explosive anger, screaming a line, losing it", quality="good"),
 "013": dict(primary="calling out", emotions=["meowing","calling","talking","asking","announcing","demanding"], action="cat opens mouth and meows at camera", sound="clear meow", use_for="announcing something, asking a question, calling out", quality="good"),
 "016": dict(primary="patient waiting", emotions=["waiting","anticipation","patient","expectant","hopeful","ready"], action="kitten sits upright waiting", sound="quiet", use_for="waiting for a reply, anticipation, sitting ready and hopeful", quality="good"),
 "017": dict(primary="hype dancing", emotions=["dancing","celebrating","hype","groove","party","vibing","excited"], action="chunky cat dances", sound="upbeat", use_for="celebration, hype, partying, the good-news payoff", quality="good"),
 "018": dict(primary="rockstar solo", emotions=["rockstar","performing","guitar","musician","jamming","dramatic-solo"], action="cat plays a guitar", sound="guitar/music", use_for="a dramatic performance, going full rockstar, an epic moment", quality="good"),
 "019": dict(primary="meme spin-dance", emotions=["dancing","spinning","silly","meme-dance","hype"], action="Maxwell cat spins and dances", sound="music", use_for="a silly victory dance, meme energy", quality="ok", note="low-res 852x480"),
 "020": dict(primary="smug rizz", emotions=["smug","confident","rizz","flirty","cool","charming","self-satisfied"], action="cat reclines and smirks", sound="smooth", use_for="walking in confident, flirting, oozing rizz, being cocky", quality="good"),
 "021": dict(primary="loud meowing", emotions=["meowing","crying-out","complaining","talking","demanding"], action="cat meows insistently", sound="repeated meows", use_for="nagging, demanding attention, complaining loudly", quality="good"),
 "022": dict(primary="sleepy peace", emotions=["sleepy","peaceful","content","dozing","relaxed","calm","cozy"], action="orange cat dozes contentedly", sound="quiet purr", use_for="being cozy, sleepy contentment, blissful calm", quality="good"),
 "023": dict(primary="intense stare (turning red)", emotions=["staring","intense","embarrassed","flustered","building-anger","awkward","suspicious"], action="cat stares as its face slowly turns red", sound="quiet tension", use_for="building rage, flustered embarrassment, an awkward intense stare", quality="good"),
 "024": dict(primary="cool & unbothered", emotions=["cool","unbothered","dismissive","aloof","nonchalant","drake"], action="hooded cat looks away dismissively", sound="ambient", use_for="dismissing an option, being too cool to care, the 'nah' panel", quality="ok", note="dim lighting"),
 "025": dict(primary="startled jump", emotions=["startled","shocked","jump-scare","surprised","alarmed","spooked"], action="cat flinches violently", sound="startled yelp", use_for="a sudden scare, getting caught, an alarming surprise", quality="good"),
 "026": dict(primary="driving", emotions=["driving","commuting","road-rage","going-somewhere"], action="cat steers a car with both paws", sound="ambient", use_for="driving to work, a commute, road rage", quality="good"),
 "027": dict(primary="furious glare", emotions=["angry","furious","menacing","glaring","rage","irritated","threatening"], action="red-tinted cat glares menacingly", sound="low growl", use_for="a menacing boss, simmering fury, a threatening glare", quality="good"),
 "030": dict(primary="fast-food worker", emotions=["working","fast-food","job","service","employee","mcdonalds"], action="cat in a McDonald's cap", sound="ambient", use_for="a service job, 'welcome to McDonalds', working a shift", quality="good"),
 "031": dict(primary="silly banana cat", emotions=["silly","banana","awkward","random","goofy","costume","walking-in"], action="cat in a banana suit walks in", sound="quiet", use_for="an awkward entrance, random silliness, comic relief", quality="good"),
 "032": dict(primary="cute happy dance", emotions=["cute","dancing","happy","playful","adorable","excited","wholesome"], action="fluffy kitten bounces and dances", sound="upbeat", use_for="adorable excitement, a happy little dance, wholesome joy", quality="good"),
 "033": dict(primary="busy typing", emotions=["typing","working","busy","office","coding","emailing","productive","panic-work"], action="cat types furiously at a computer", sound="keyboard clicks", use_for="frantic work, sending an email, brain working overtime", quality="good"),
 "035": dict(primary="broken & dead inside", emotions=["broken","dead-inside","exhausted","cursed","done","traumatized","monday","empty"], action="cat with glowing eyes, utterly broken", sound="eerie", use_for="Monday morning, being completely done, dead inside, burnout", quality="good"),
 "036": dict(primary="chatty explaining", emotions=["talking","explaining","chatting","gossiping","telling","rehearsing"], action="cat talks animatedly in profile", sound="chatty meows", use_for="rehearsing a speech, explaining yourself, telling a story", quality="good"),
 "037": dict(primary="victory dance (Toothless)", emotions=["dancing","celebrating","hype","victory","silly-dance"], action="cartoon Toothless dances", sound="music", use_for="a victory dance, meme celebration", quality="ok", note="cartoon, not a cat"),
 "039": dict(primary="snacking", emotions=["eating","snacking","munching"], action="cat eats chips", sound="crunch", use_for="casually snacking while watching drama", quality="low", note="tiny 144x144, blurry"),
 "040": dict(primary="wholesome smile", emotions=["happy","smiling","friendly","cheerful","approving","wholesome"], action="corgi grins warmly", sound="happy pant", use_for="genuine approval, a warm smile, wholesome agreement", quality="good", note="dog, not a cat"),
 "041": dict(primary="laughing", emotions=["laughing","giggling","amused","lol","mocking","cant-stop-laughing"], action="cat covers face laughing", sound="giggling", use_for="bursting out laughing, mocking, finding it hilarious", quality="good"),
 "042": dict(primary="chill vibing", emotions=["vibing","dancing","chill","happy","groove","relaxed-fun"], action="cartoon cat sways and vibes", sound="music", use_for="vibing along, low-key celebration, chill good mood", quality="ok", note="cartoon"),
}

# Controlled emotion vocabulary — the 25-word cat taxonomy (from the AI_Reaction_bot
# study). Merged ON TOP of each clip's hand-authored `emotions` tags so an author can
# reliably reach any clip with a standard feeling word, without losing the specific tags.
TAXONOMY = ["happy","sad","surprised","scared","unimpressed","playful","angry",
 "content","loving","curious","indifferent","hungry","relaxed","confused","annoyed",
 "excited","terrified","mischievous","pensive","jealous","nervous","affectionate",
 "bored","proud","sleepy","resigned","disgusted"]
TAX_ADD = {
 "001":["proud","pensive"],            "002":["surprised","scared","terrified"],
 "003":["confused","playful","curious"], "004":["unimpressed","confused","indifferent","bored"],
 "005":["angry","annoyed","mischievous"], "006":["disgusted"],
 "008":["sad","nervous","resigned","scared"], "009":["annoyed","angry","hungry"],
 "010":["bored","indifferent","pensive","relaxed"], "011":["curious","affectionate","loving"],
 "012":["angry","terrified","scared"], "013":["curious","hungry","annoyed"],
 "016":["nervous","curious","pensive","content"], "017":["excited","happy","playful"],
 "018":["proud","excited","playful"], "019":["playful","excited","happy"],
 "020":["proud","content","mischievous","loving"], "021":["annoyed","hungry"],
 "022":["sleepy","relaxed","content"], "023":["annoyed","nervous","jealous","pensive"],
 "024":["indifferent","bored","relaxed"], "025":["surprised","scared","terrified","nervous"],
 "027":["angry","annoyed"], "030":["bored","indifferent"],
 "031":["playful","mischievous","curious"], "032":["happy","excited","playful","affectionate"],
 "033":["nervous","annoyed"], "035":["resigned","sad","bored"],
 "036":["curious","playful","proud"], "037":["excited","happy","proud","playful"],
 "039":["hungry","content","relaxed"], "040":["happy","content","loving","affectionate"],
 "041":["happy","playful","mischievous","excited"], "042":["relaxed","content","happy"],
}
# sanity: every addition must be a taxonomy word, and every taxonomy word must be used
assert all(t in TAXONOMY for v in TAX_ADD.values() for t in v), "non-taxonomy tag in TAX_ADD"
_used = {t for v in TAX_ADD.values() for t in v}
assert _used == set(TAXONOMY), f"taxonomy words never used: {set(TAXONOMY)-_used}"

def probe(path):
    def g(stream, ent):
        return subprocess.run(["ffprobe","-v","error","-select_streams",stream,
            "-show_entries",ent,"-of","default=noprint_wrappers=1:nokey=1",path],
            capture_output=True,text=True).stdout.strip().splitlines()
    dur = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1",path],capture_output=True,text=True).stdout.strip()
    wh = g("v:0","stream=width,height")
    w,h = (int(wh[0]),int(wh[1])) if len(wh)>=2 else (0,0)
    return float(dur or 0), w, h

def key_color(idx):
    """Sample the dominant green from the border region of the frame."""
    fp = os.path.join(FRAMES, f"{idx}.jpg")
    if not os.path.exists(fp):
        return "0x00d000"
    im = Image.open(fp).convert("RGB")
    W,H = im.size
    px = im.load()
    band = max(2, W//12)
    greens = []
    for x in range(W):
        for y in range(H):
            edge = x < band or x >= W-band or y < band or y >= H-band
            if not edge:
                continue
            r,g,b = px[x,y]
            if g > 90 and g > r*1.25 and g > b*1.25:   # clearly green
                greens.append((r,g,b))
    if not greens:
        return "0x00d000"
    # mode by coarse quantization, then average the modal bucket
    q = collections.Counter((r//16, g//16, b//16) for r,g,b in greens)
    (qr,qg,qb),_ = q.most_common(1)[0]
    bucket = [c for c in greens if (c[0]//16,c[1]//16,c[2]//16)==(qr,qg,qb)]
    r = sum(c[0] for c in bucket)//len(bucket)
    g = sum(c[1] for c in bucket)//len(bucket)
    b = sum(c[2] for c in bucket)//len(bucket)
    return f"0x{r:02x}{g:02x}{b:02x}"

def subject_bbox(idx):
    """Normalized [x0,y0,x1,y1] of the non-green subject, so the renderer can
    ground the cat (feet on a surface) and place its name label above its head."""
    fp = os.path.join(FRAMES, f"{idx}.jpg")
    if not os.path.exists(fp):
        return [0.0, 0.0, 1.0, 1.0]
    im = Image.open(fp).convert("RGB")
    W, H = im.size
    px = im.load()
    cols = [0]*W
    rows = [0]*H
    for x in range(W):
        for y in range(H):
            r, g, b = px[x, y]
            green = g > 90 and g > r*1.2 and g > b*1.2
            if not green:
                cols[x] += 1
                rows[y] += 1
    def extent(arr, n):
        peak = max(arr) if arr else 0
        if peak == 0:
            return 0, n-1
        thr = max(2, peak*0.12)             # ignore sparse edge noise
        lo = next((i for i,v in enumerate(arr) if v > thr), 0)
        hi = next((i for i in range(n-1,-1,-1) if arr[i] > thr), n-1)
        return lo, hi
    x0, x1 = extent(cols, W)
    y0, y1 = extent(rows, H)
    return [round(x0/W,3), round(y0/H,3), round((x1+1)/W,3), round((y1+1)/H,3)]

catalog = []
for path in sorted(glob.glob(os.path.join(CLIPS, "[0-9]*.*"))):
    if os.path.splitext(path)[1].lower() not in (".webm",".mkv",".mp4"):
        continue
    base = os.path.basename(path)
    idx = base.split(" ")[0]
    if idx not in EMO:
        continue
    extract_frame(path, idx)          # self-contained: make the frame if absent
    dur,w,h = probe(path)
    title = base.split(" - ",1)[1].rsplit(" [",1)[0] if " - " in base else base
    e = EMO[idx]
    catalog.append(dict(
        id=idx, file=base, title=title,
        duration=round(dur,2), width=w, height=h,
        orientation=("portrait" if h>w else "landscape" if w>h else "square"),
        key_color=key_color(idx),
        bbox=subject_bbox(idx),
        primary=e["primary"],
        emotions=list(dict.fromkeys(e["emotions"] + TAX_ADD.get(idx, []))),
        action=e["action"],
        sound=e["sound"], use_for=e["use_for"], quality=e["quality"],
        note=e.get("note",""),
    ))

out = CATALOG
with open(out,"w") as f:
    json.dump(catalog, f, indent=2, ensure_ascii=False)
print(f"wrote {out} ({len(catalog)} clips)")
for c in catalog:
    print(f"  {c['id']}  key={c['key_color']}  {c['quality']:7s} {c['primary']}")
