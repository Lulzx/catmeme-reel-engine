"""Caption timings. whisper.cpp gives accurate word *timing*; the displayed
*text* comes from the known narration script (whisper mishears — "dot"->"duck" —
so we never trust its words, only its clock).

  tokens_for({sid: wav}, {sid: scriptText}) -> {sid: [{text,startMs,endMs}]}
"""
from __future__ import annotations
import json
import os
import subprocess

try:
    from engine.paths import WORK, ROOT
except ImportError:
    from paths import WORK, ROOT

TRANSCRIBE = os.path.join(ROOT, "remotion", "scripts", "transcribe.mjs")
CAP_WORK = os.path.join(WORK, "captions")


def align(script_text, whisper_words):
    """Map the exact script words onto whisper's word-timing buckets.

    Robust to whisper splitting a word ("doomer"->"do"+"er") or merging: script
    word i takes the time span of whisper bucket [i*m/n .. (i+1)*m/n). Exact text,
    speech-following timing.
    """
    sw = script_text.split()
    n = len(sw)
    if n == 0 or not whisper_words:
        return []
    m = len(whisper_words)
    out = []
    for i, word in enumerate(sw):
        j0 = min(m - 1, (i * m) // n)
        j1 = max(j0, min(m - 1, ((i + 1) * m) // n - 1))
        out.append({
            "text": word,
            "startMs": whisper_words[j0]["startMs"],
            "endMs": whisper_words[j1]["endMs"],
        })
    return out


def tokens_for(wavs: dict, scripts: dict | None = None) -> dict:
    if not wavs:
        return {}
    scripts = scripts or {}
    os.makedirs(CAP_WORK, exist_ok=True)
    items = []
    for sid, wav in wavs.items():
        w16 = os.path.join(CAP_WORK, f"{sid}.16k.wav")
        subprocess.run(["ffmpeg", "-y", "-nostdin", "-i", wav, "-ar", "16000", "-ac", "1", w16],
                       check=True, capture_output=True)
        items.append({"id": sid, "wav": w16})
    inp = os.path.join(CAP_WORK, "in.json")
    outp = os.path.join(CAP_WORK, "out.json")
    json.dump(items, open(inp, "w"))
    subprocess.run(["node", TRANSCRIBE, inp, outp], check=True,
                   cwd=os.path.join(ROOT, "remotion"))
    whisper = json.load(open(outp))
    # Relabel whisper timing with the known script text.
    return {sid: align(scripts.get(sid, ""), words) if scripts.get(sid) else words
            for sid, words in whisper.items()}
