"""Voice-over through Fish Audio (https://fish.audio), cached on disk.

    from voice import speak
    path, seconds = speak("Breaking news.", voice="0380b387bf9a4a8b8e5e2df81ecdc077")

The API key comes from the FISH_API_KEY environment variable, or the first line of
`fish_api_key.txt` at the repo root (gitignored). Each (text, voice, model, speed) is
synthesised once into work/voice/<hash>.wav, so re-rendering a reel costs nothing.
"""
import hashlib, json, os, subprocess, urllib.error, urllib.request, wave

try:
    from engine.paths import ROOT, WORK
except ImportError:
    from paths import ROOT, WORK

API = "https://api.fish.audio/v1/tts"
CACHE = os.path.join(WORK, "voice")
DEFAULT_MODEL = "s2.1-pro-free"     # the free developer tier; "s2.1-pro" needs API credit


def api_key():
    key = os.environ.get("FISH_API_KEY")
    path = os.path.join(ROOT, "fish_api_key.txt")
    if not key and os.path.exists(path):
        key = open(path).readline().strip()
    if not key:
        raise SystemExit("No Fish Audio key: set FISH_API_KEY or put it in fish_api_key.txt")
    return key


def _duration(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / w.getframerate()


def speak(text, voice, model=DEFAULT_MODEL, speed=1.0):
    """Return (wav path, seconds) for `text` in the given Fish Audio voice model."""
    os.makedirs(CACHE, exist_ok=True)
    tag = hashlib.sha1(json.dumps([text, voice, model, speed]).encode()).hexdigest()[:16]
    out = os.path.join(CACHE, f"{tag}.wav")
    if not os.path.exists(out):
        body = {"text": text, "reference_id": voice, "format": "wav", "sample_rate": 44100,
                "latency": "normal", "prosody": {"speed": speed, "volume": 0}}
        req = urllib.request.Request(API, data=json.dumps(body).encode(), method="POST", headers={
            "Authorization": f"Bearer {api_key()}", "Content-Type": "application/json",
            "model": model})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                audio = r.read()
        except urllib.error.HTTPError as e:
            raise SystemExit(f"Fish Audio {e.code}: {e.read().decode(errors='replace')[:300]}")
        raw = out + ".part"
        with open(raw, "wb") as f:
            f.write(audio)
        # trim the model's leading/trailing silence so lines land on their cue
        subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", raw, "-af",
                        "silenceremove=start_periods=1:start_threshold=-45dB,"
                        "areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse",
                        "-ar", "48000", "-ac", "1", out], check=True)
        os.remove(raw)
    return out, _duration(out)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        sys.exit("usage: python3 engine/voice.py <voice-id> <text>")
    print(*speak(" ".join(sys.argv[2:]), sys.argv[1]))
