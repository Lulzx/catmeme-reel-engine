#!/usr/bin/env python3
"""Render a story.json into a finished cat-meme reel.

Design follows the cat-meme reaction-story style:
  - a constant top "POV:" speech bubble (the premise)
  - named characters: every cat gets a bold outlined label above its head
  - 1-3 cats per scene, chroma-keyed and GROUNDED on the surface (contact shadow),
    scaled small and placed at distinct x positions (can face each other)
  - a small italic *action* / "dialogue" caption per beat
  - cozy, scene-relevant photo backgrounds (fetched + cached)
  - optional end card (SUBSCRIBE / FOLLOW FOR PART 2)

Each cat keeps its own audio; multi-cat scenes mix the audio. Beats are
concatenated into out/final.mp4.
"""
import json, os, sys, subprocess, textwrap, io, re, ssl, urllib.request, urllib.parse
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import match as M
import paths
# offline scene library is preferred over the web; see paths.py for the layout
from paths import CLIPS, STORIES, OUTPUT, BACKGROUNDS as LIBRARY
from paths import OVERLAYS as CAP, BG_RENDER as BG, BG_CACHE as CACHE, BEAT_CLIPS as OUT

paths.ensure()

# fonts ------------------------------------------------------------------------
F_BUBBLE = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"        # POV text
F_LABEL  = "/System/Library/Fonts/Supplemental/Arial Black.ttf"       # ME / MOM
F_ACTION = "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf" # *action*
F_CARD   = "/System/Library/Fonts/Supplemental/Impact.ttf"            # end card
def font(path, size):
    try: return ImageFont.truetype(path, size)
    except Exception: return ImageFont.load_default()

# image fetch ------------------------------------------------------------------
_SSL = ssl.create_default_context(); _SSL.check_hostname=False; _SSL.verify_mode=ssl.CERT_NONE
_UA  = {"User-Agent": "cat-reel/1.0 (educational meme project)"}
def _get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=25, context=_SSL).read()

# ---- local scene library (bundled AI backgrounds) — preferred over the web ----
# scene stem -> keywords that should map a free-text query onto it. Kept precise:
# a wrong library scene is worse than falling back to a real web photo.
LIB_KW = {
 "airport":["airport","airplane","plane","flight","terminal","runway"],
 "amusementpark":["amusement","themepark","carnival","fairground","rollercoaster","rides"],
 "bank":["bank","atm","vault","teller"],
 "beach":["beach","seaside","shore","sand","coast","ocean","sea","tropical"],
 "cinema":["cinema","movie","movies","film","screening"],
 "classroom":["classroom","lesson","students","lecture"],
 "concert":["concert","gig","band","festival"],
 "fantacy":["fantasy","magical","magic","surreal","fairytale","mystical","dream"],
 "forest":["forest","woods","woodland","jungle","trees"],
 "grassland":["grassland","meadow","prairie","savanna","field","grass"],
 "gym":["gym","fitness","workout","exercise","weights"],
 "highway":["highway","freeway","motorway","road","traffic","driving","commute"],
 "home":["home","house","living","livingroom","bedroom","apartment","lounge","sofa","couch"],
 "hospital":["hospital","clinic","medical","ward","doctor","nurse","emergency"],
 "kitchen":["kitchen","cooking","breakfast","stove","countertop"],
 "lab":["lab","laboratory","science","experiment","chemistry","research"],
 "library":["library","bookshelf","books","reading","librarian"],
 "museum":["museum","gallery","exhibit","exhibition"],
 "mountain":["mountain","mountains","peak","summit","hill","alps","cliff"],
 "park":["park","garden","bench","lawn"],
 "playground":["playground","swings","slide","seesaw","junglegym"],
 "pool":["pool","swimming","poolside"],
 "port":["port","harbor","harbour","dock","pier","wharf","marina"],
 "restaurant":["restaurant","dining","diner","cafe","bistro","eatery","meal"],
 "river":["river","stream","creek","riverbank"],
 "rooftop":["rooftop","roof","skyline","cityscape","downtown","terrace","sunset","city"],
 "school":["school","campus","schoolyard"],
 "shop":["shop","store","mall","supermarket","market","boutique","retail"],
 "stage":["stage","spotlight","performance"],
 "station":["station","train","subway","metro","railway","platform"],
 "theater":["theater","theatre","auditorium","drama"],
 "village":["village","countryside","rural","town","hamlet"],
}
_lib_index = None
def _library():
    global _lib_index
    if _lib_index is None:
        _lib_index = {}
        if os.path.isdir(LIBRARY):
            for fn in os.listdir(LIBRARY):
                if fn.lower().endswith((".jpg",".jpeg",".png")):
                    _lib_index[os.path.splitext(fn)[0].lower()] = os.path.join(LIBRARY, fn)
    return _lib_index

def library_path(name):
    """Direct lookup of a named scene, e.g. place='kitchen' -> library/kitchen.jpg."""
    return _library().get((name or "").strip().lower())

def library_match(query):
    """Best library scene for a free-text query, by stem + keyword overlap.
    Returns a path only on a clear hit (so weak matches fall through to the web)."""
    files = _library()
    if not files:
        return None
    qt = set(re.findall(r"[a-z0-9]+", query.lower()))
    best, best_score = None, 0
    for stem, path in files.items():
        score = (2 if stem in qt else 0) + len(qt & set(LIB_KW.get(stem, [stem])))
        if score > best_score:
            best, best_score = path, score
    return best if best_score >= 1 else None

# filler words that make an image search over-specific and return nothing — a
# verbose scene line like "phone screen text message closeup dark" matches almost
# no CC photos, but "phone screen" matches plenty.
_BG_STOP = {"closeup","close","up","interior","exterior","indoor","indoors","dark",
            "night","evening","morning","cozy","soft","dim","dimly","lit","glow",
            "glowing","scene","background","view","shot","with","the","and","of","a"}

def _bg_queries(query):
    """The exact query, then simpler fallbacks built from the salient (non-filler)
    words. The two-word core is tried before the three-word one: empirically it's
    both the most reliable to return results and the most on-topic ("neon bar" →
    bar signs, where "neon bar purple" drifts to a car wrap). A lone keyword is
    avoided — "neon"/"bar" are too ambiguous — so a wordy scene line resolves to a
    relevant photo rather than an off-topic one or a blank gradient."""
    words = re.findall(r"[a-z0-9]+", query.lower())
    core  = [w for w in words if w not in _BG_STOP] or words
    cands = [query, " ".join(core[:2]), " ".join(core[:3])]
    out, seen = [], set()
    for c in cands:
        c = c.strip()
        if c and c not in seen:
            seen.add(c); out.append(c)
    return out

def _openverse_search(query):
    """Run one Openverse search. Returns the first usable RGB image, or None when
    the search ran but yielded nothing usable. Raises on a network/JSON error so
    the caller can tell a real miss apart from a transient failure."""
    api = ("https://api.openverse.org/v1/images/?q=" + urllib.parse.quote(query)
           + "&page_size=12&mature=false&license_type=all")
    data = json.loads(_get(api))          # network/JSON errors propagate
    for r in data.get("results", []):
        # thumbnail first: it's a live, right-sized CDN image; the original `url`
        # often points at a source page that 403s or isn't an image at all.
        for u in (r.get("thumbnail"), r.get("url")):
            if not u: continue
            try:
                im = Image.open(io.BytesIO(_get(u))).convert("RGB")
                if im.width >= 240 and im.height >= 240:
                    return im
            except Exception:
                continue
    return None

def fetch_image(query):
    """Scene-relevant photo for `query` from Openverse (keyless CC). Cached.
    Tries the full query then simpler fallbacks so wordy descriptions still land
    a photo. A `.miss` marker is written only when every variant genuinely comes
    up empty (not on a network error), so repeat renders fall straight through to
    the gradient without re-hitting the network."""
    slug = re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_")[:60]
    cache = os.path.join(CACHE, slug + ".jpg")
    miss  = os.path.join(CACHE, slug + ".miss")
    if os.path.exists(cache):
        return cache
    if os.path.exists(miss):
        return None
    try:
        for q in _bg_queries(query):
            im = _openverse_search(q)
            if im is not None:
                im.save(cache, quality=90); return cache
    except Exception:
        return None                       # transient/network error — retry next run
    open(miss, "w").close()               # every variant returned nothing usable
    return None

# background painting ----------------------------------------------------------
PALETTES = {
    "bedroom":((18,18,38),(40,34,66)), "office":((38,52,74),(70,90,120)),
    "boss":((46,10,12),(96,20,24)), "void":((8,8,10),(24,24,30)),
    "hallway":((28,40,42),(52,72,74)), "mirror":((36,64,72),(120,170,180)),
    "friday":((150,40,90),(250,140,40)), "brain":((30,12,54),(74,30,110)),
    "rage":((60,8,8),(150,28,20)), "snack":((40,28,16),(92,60,30)),
    "dawn":((44,30,62),(240,150,92)), "alarm":((90,18,18),(220,80,40)),
    "neutral":((30,30,36),(60,60,72)),
}
def gradient(w, h, top, bot):
    base = Image.new("RGB",(w,h)); px=base.load()
    for y in range(h):
        t=y/max(1,h-1)
        c=tuple(int(top[i]*(1-t)+bot[i]*t) for i in range(3))
        for x in range(w): px[x,y]=c
    return base

def cover(img, w, h):
    ir,tr=img.width/img.height, w/h
    if ir>tr:
        nw=int(img.height*tr); x=(img.width-nw)//2; img=img.crop((x,0,x+nw,img.height))
    else:
        nh=int(img.width/tr); y=(img.height-nh)//2; img=img.crop((0,y,img.width,y+nh))
    return img.resize((w,h), Image.LANCZOS)

def make_background(spec, w, h, path, shadows=()):
    """Photo (fetched/local) or gradient, dimmed for legibility, with contact
    shadows drawn where each cat stands."""
    # resolve a background photo, preferring offline assets over the web:
    #   explicit image  ->  named library scene  ->  library keyword match
    #   ->  Openverse web fetch  ->  (gradient fallback below)
    src=None
    if spec.get("image") and os.path.exists(spec["image"]):
        src=spec["image"]
    elif spec.get("place"):
        src=library_path(spec["place"])
    if src is None and spec.get("img"):
        src=library_match(spec["img"]) or fetch_image(spec["img"])
    photo=Image.open(src).convert("RGB") if src else None
    if photo is not None:
        img=cover(photo,w,h)
        ov=Image.new("RGBA",(w,h),(0,0,0,0)); d=ImageDraw.Draw(ov)
        d.rectangle([0,0,w,h],fill=(0,0,0,46))
        top=int(h*0.26)
        for y in range(top): d.line([(0,y),(w,y)],fill=(0,0,0,int(150*(1-y/top))))
        img=Image.alpha_composite(img.convert("RGBA"),ov).convert("RGB")
    else:
        top,bot=PALETTES.get(spec.get("palette","neutral"),PALETTES["neutral"])
        img=gradient(w,h,top,bot)
    # contact shadows (drawn on a blurred layer so they read as soft)
    if shadows:
        sh=Image.new("RGBA",(w,h),(0,0,0,0)); ds=ImageDraw.Draw(sh)
        for (cx,cy,rw,rh) in shadows:
            ds.ellipse([cx-rw,cy-rh,cx+rw,cy+rh],fill=(0,0,0,120))
        sh=sh.filter(ImageFilter.GaussianBlur(14))
        img=Image.alpha_composite(img.convert("RGBA"),sh).convert("RGB")
    img.save(path)

# text overlay -----------------------------------------------------------------
def _wrap(d, text, font, maxw):
    out=[]
    for para in text.split("\n"):
        words=para.split(" "); line=""
        for wd in words:
            t=(line+" "+wd).strip()
            if d.textlength(t,font=font)<=maxw or not line: line=t
            else: out.append(line); line=wd
        out.append(line)
    return out

def make_overlay(w, h, path, pov="", action="", labels=(), card=""):
    """Transparent overlay: POV bubble (top), action caption, per-cat name labels,
    and an optional big center card."""
    img=Image.new("RGBA",(w,h),(0,0,0,0)); d=ImageDraw.Draw(img)
    bubble_bottom=int(h*0.03)
    # POV speech bubble: white rounded box, black bold text
    if pov:
        fb=font(F_BUBBLE,int(min(w,h)*0.047))
        lines=_wrap(d,pov,fb,w*0.72)
        lh=int(fb.size*1.22); tw=max(d.textlength(l,font=fb) for l in lines)
        pad=int(fb.size*0.55); bw=int(tw+pad*2); bh=int(lh*len(lines)+pad*1.3)
        bx0=(w-bw)//2; by0=int(h*0.06)
        d.rounded_rectangle([bx0,by0,bx0+bw,by0+bh],radius=int(fb.size*0.55),
                            fill=(255,255,255,255))
        for i,l in enumerate(lines):
            d.text((w//2, by0+pad//2+i*lh), l, font=fb, fill=(15,15,15,255), anchor="ma")
        bubble_bottom=by0+bh
    fl=font(F_LABEL,int(min(w,h)*0.046))
    # action / dialogue caption — sits DOWN near the cat, just above its name
    # label (matching the reference), not pinned under the bubble.
    if action:
        fa=font(F_ACTION,int(min(w,h)*0.040))
        lines=_wrap(d,action,fa,w*0.82); lh=int(fa.size*1.2)
        if labels:
            anchor_top=min(t for (_,_,t) in labels)        # highest cat's head
            action_bottom=anchor_top-int(h*0.012)-fl.size-int(h*0.012)
        else:
            action_bottom=int(h*0.55)
        y0=max(action_bottom-lh*len(lines), bubble_bottom+int(h*0.02))
        for i,l in enumerate(lines):
            d.text((w//2, y0+i*lh), l, font=fa, fill=(255,255,255,255),
                   anchor="ma", stroke_width=max(2,fa.size//11), stroke_fill=(0,0,0,255))
    # per-character name labels (above each cat head)
    for (text,cx,top_y) in labels:
        d.text((cx, top_y-int(h*0.012)), text.upper(), font=fl, fill=(255,255,255,255),
               anchor="mb", stroke_width=max(3,fl.size//8), stroke_fill=(0,0,0,255))
    # big end card
    if card:
        fc=font(F_CARD,int(min(w,h)*0.10))
        lines=_wrap(d,card,fc,w*0.86); lh=int(fc.size*1.05)
        y0=(h-lh*len(lines))//2
        for i,l in enumerate(lines):
            d.text((w//2, y0+i*lh), l, font=fc, fill=(255,255,255,255),
                   anchor="ma", stroke_width=max(4,fc.size//12), stroke_fill=(0,0,0,255))
    img.save(path)

# geometry: where each cat sits, given its subject bbox -------------------------
def layout(cast_clips, positions, sizes, baselines, W, H):
    geos=[]
    for clip,pos,size,base in zip(cast_clips,positions,sizes,baselines):
        bx0,by0,bx1,by1=clip["bbox"]; cw,ch=clip["width"],clip["height"]
        bbh=max(0.15,by1-by0)
        dispH=size*H/bbh
        dispW=dispH*(cw/ch)
        Y=int(base*H - by1*dispH)
        X=int(pos*W - ((bx0+bx1)/2)*dispW)
        cat_cx=int(pos*W)
        cat_top=int(Y + by0*dispH)
        cat_w=(bx1-bx0)*dispW
        geos.append(dict(X=X,Y=Y,dispW=int(dispW),dispH=int(dispH),
                         cx=cat_cx,top=cat_top,base_y=int(base*H),catw=cat_w))
    return geos

def run(cmd):
    p=subprocess.run(cmd,capture_output=True,text=True)
    if p.returncode!=0:
        sys.stderr.write(p.stderr[-2500:]+"\n"); raise SystemExit("ffmpeg failed")
    return p

DEFAULT_POS={1:[0.5],2:[0.30,0.70],3:[0.22,0.5,0.78]}

def render(story_path, seed_used=None):
    # seed_used: a list of clip ids already used by *other* videos in a batch;
    # the matcher avoids them so clips don't repeat across the batch. Passed by
    # reference and grown in place, so the caller can thread it through a batch.
    story=json.load(open(story_path))
    cv=story.get("canvas",{}); W,H,FPS=cv.get("w",1080),cv.get("h",1920),cv.get("fps",30)
    pov=story.get("pov",""); default_max=story.get("max_beat_dur",4.5)
    base_default=story.get("baseline",0.9)
    catalog=M.load_catalog(); by_id={c["id"]:c for c in catalog}
    beats=list(story["beats"])
    if story.get("outro"):
        beats.append({"card":story["outro"],"bg":{"palette":"void"},"dur":2.6,
                      "cast":story.get("outro_cast",[])})

    # cross-video set (soft): clips other videos used — discouraged, not banned.
    cross_used=seed_used if seed_used is not None else []
    story_used=[]; beat_files=[]   # within THIS video: hard no-repeat
    for i,beat in enumerate(beats):
        cast=beat.get("cast",[])
        # resolve each character's clip
        clips=[]; local_used=[]
        for c in cast:
            if c.get("clip"): clip=by_id[c["clip"]]
            else:
                # hard-exclude repeats within this video; softly avoid clips used
                # by other videos (quality still wins over novelty).
                _,clip,_=M.best(c.get("want",[]),c.get("query",""),catalog,
                                exclude=story_used+local_used,
                                penalize=set(cross_used))
            if clip is None:
                raise SystemExit(f"beat {i}: no clip matches {c.get('want') or c.get('query')!r}")
            clips.append(clip); local_used.append(clip["id"])
        story_used+=local_used; cross_used+=local_used
        # geometry
        n=len(cast)
        pos=[c.get("pos") for c in cast]
        defpos=DEFAULT_POS.get(n,[ (j+0.5)/n for j in range(n)])
        pos=[p if p is not None else defpos[j] for j,p in enumerate(pos)]
        sizes=[c.get("size",0.46 if n==1 else 0.40) for c in cast]
        bases=[c.get("baseline",beat.get("baseline",base_default)) for c in cast]
        geos=layout(clips,pos,sizes,bases,W,H)
        # duration: bounded by the shortest clip in the scene
        if clips:
            dur=round(min(beat.get("dur",default_max),
                          min(cl["duration"] for cl in clips)),2)
        else:
            dur=beat.get("dur",2.5)
        # assets
        shadows=[(g["cx"],g["base_y"],max(40,g["catw"]*0.55),max(10,g["catw"]*0.13))
                 for g in geos]
        bgp=os.path.join(BG,f"beat_{i:02d}.png")
        ovp=os.path.join(CAP,f"ov_{i:02d}.png")
        bgspec=dict(beat.get("bg",{})); bgspec.setdefault("palette","neutral")
        make_background(bgspec,W,H,bgp,shadows=shadows)
        labels=[(c["name"],g["cx"],g["top"]) for c,g in zip(cast,geos) if c.get("name")]
        make_overlay(W,H,ovp,pov=pov if not beat.get("card") else "",
                     action=beat.get("action",""),labels=labels,card=beat.get("card",""))
        # ffmpeg compositing
        out=os.path.join(OUT,f"beat_{i:02d}.mp4")
        inputs=["-loop","1","-framerate",str(FPS),"-t",str(dur),"-i",bgp]
        for cl in clips:
            inputs+=["-ss","0","-t",str(dur),"-i",os.path.join(CLIPS,cl["file"])]
        inputs+=["-loop","1","-framerate",str(FPS),"-t",str(dur),"-i",ovp]
        ov_idx=len(clips)+1
        fc=[f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[bg]"]
        prev="bg"
        for j,(cl,g,c) in enumerate(zip(clips,geos,cast)):
            k=j+1; sim=c.get("key_similarity",0.12)
            flip=",hflip" if c.get("flip") else ""
            # low similarity keeps even dull-green clips' subjects; despill then
            # strips the residual green fringe (so we don't over-key the cat).
            fc.append(f"[{k}:v]chromakey={cl['key_color']}:{sim}:0.08{flip},"
                      f"despill=type=green:mix=0.6:expand=0.4,"
                      f"scale={g['dispW']}:{g['dispH']}[c{j}]")
            tag=f"t{j}"
            fc.append(f"[{prev}][c{j}]overlay={g['X']}:{g['Y']}[{tag}]")
            prev=tag
        fc.append(f"[{prev}][{ov_idx}:v]overlay=0:0,format=yuv420p[v]")
        cmd=["ffmpeg","-y","-nostdin"]+inputs
        if clips:
            aud="".join(f"[{j+1}:a]" for j in range(len(clips)))
            fc.append(f"{aud}amix=inputs={len(clips)}:duration=longest:normalize=0,"
                      f"aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=11[a]")
        else:
            cmd+=["-f","lavfi","-t",str(dur),"-i","anullsrc=r=48000:cl=stereo"]
        cmd+=["-filter_complex",";".join(fc),"-map","[v]"]
        cmd+=["-map","[a]"] if clips else ["-map",f"{ov_idx+1}:a"]
        cmd+=["-r",str(FPS),"-c:v","libx264","-preset","veryfast","-crf","20",
              "-pix_fmt","yuv420p","-c:a","aac","-ar","48000","-ac","2","-shortest",out]
        run(cmd)
        beat_files.append(out)
        names="+".join(c.get("name","?") for c in cast) or "card"
        print(f"  beat {i:02d}  {dur:4.1f}s  [{','.join(cl['id'] for cl in clips) or '-'}]  {names:20s} {beat.get('action','')[:40]}")

    # concat
    listf=os.path.join(OUT,"concat.txt")
    with open(listf,"w") as f:
        for bf in beat_files: f.write(f"file '{os.path.abspath(bf)}'\n")
    final=os.path.join(OUTPUT,story.get("output","final.mp4"))
    # Beats are all encoded with identical params (W/H/fps/pix_fmt/codec/audio),
    # so the concat demuxer can stream-copy them — no re-encode, no double-encode
    # quality loss, much faster. +faststart still moves the moov atom for web.
    run(["ffmpeg","-y","-nostdin","-f","concat","-safe","0","-i",listf,
         "-c","copy","-movflags","+faststart",final])
    print(f"\n  -> {final}")
    return final

if __name__=="__main__":
    # RENDER_SEED (JSON list of clip ids) lets a batch caller seed cross-video
    # diversity for subprocess renders; harmless when absent.
    _seed=None
    try: _seed=json.loads(os.environ.get("RENDER_SEED","")) or None
    except Exception: _seed=None
    render(sys.argv[1] if len(sys.argv)>1 else os.path.join(STORIES,"functional-adult.json"),
           seed_used=_seed)
