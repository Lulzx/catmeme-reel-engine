"""Narration TTS — local, offline, free.

Two providers:
  • piper     — higher-quality natural voices (preferred for long-form). Models in
                work/piper/<voice>.onnx (auto-downloaded on first use).
  • kittentts — tiny fallback model (KittenML/kitten-tts-nano-0.1).

`tempo` > 1 speeds delivery up (ffmpeg atempo) to keep narration snappy.
"""
from __future__ import annotations
import os
import subprocess
import sys
import wave

try:
    from engine.paths import WORK
except ImportError:
    from paths import WORK

AUDIO = os.path.join(WORK, "audio")
PIPER_DIR = os.path.join(WORK, "piper")
DEFAULT_VOICE = "en_US-ryan-high"          # piper narrator
KITTEN_VOICE = "expr-voice-5-m"
KITTEN_MODEL = "KittenML/kitten-tts-nano-0.1"

_kitten = None
_piper = {}


def _kitten_model():
    global _kitten
    if _kitten is None:
        from kittentts import KittenTTS
        _kitten = KittenTTS(KITTEN_MODEL)
    return _kitten


def _piper_voice(name):
    if name not in _piper:
        from piper import PiperVoice
        model = os.path.join(PIPER_DIR, f"{name}.onnx")
        if not os.path.exists(model):
            os.makedirs(PIPER_DIR, exist_ok=True)
            subprocess.run([sys.executable, "-m", "piper.download_voices", name],
                           cwd=PIPER_DIR, check=True)
        _piper[name] = PiperVoice.load(model)
    return _piper[name]


def _wav_dur(p):
    with wave.open(p, "rb") as w:
        return w.getnframes() / w.getframerate()


def _retempo(path, tempo):
    if not tempo or abs(tempo - 1.0) < 0.01:
        return
    tmp = path + ".t.wav"
    subprocess.run(["ffmpeg", "-y", "-nostdin", "-i", path, "-filter:a", f"atempo={tempo}", tmp],
                   check=True, capture_output=True)
    os.replace(tmp, path)


def synth(text, out, voice=None, provider="piper", tempo=1.0, speed=1.0):
    """Synthesize `text` to `out` (wav). Returns duration in seconds."""
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if provider == "piper":
        v = _piper_voice(voice or DEFAULT_VOICE)
        with wave.open(out, "wb") as w:
            v.synthesize_wav(text, w)
        _retempo(out, tempo)
        return _wav_dur(out)
    # kittentts fallback
    import soundfile as sf
    audio = _kitten_model().generate(text, voice=voice or KITTEN_VOICE, speed=speed)
    sf.write(out, audio, 24000)
    _retempo(out, tempo)
    return _wav_dur(out)
