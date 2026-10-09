# Text to speech with pyttsx3 (offline; on Linux it drives espeak-ng, installed on Railway via railpack.json).
# Speech is returned as MP3 and cached by its text, so replaying something is instant.
# Each synthesis runs in its own short-lived process: pyttsx3's espeak driver keeps shared state between
# utterances and can hang when requests follow each other quickly; a separate process can't, and is killed on timeout.
import hashlib
import os
import subprocess
import sys
import tempfile
import threading
import wave
from pathlib import Path

MAX_CHARS = 8000  # roughly 8 minutes of speech
RATE = int(os.getenv("TTS_RATE", "160"))  # words per minute (pyttsx3 default 200 is fast for lessons)
VOICE = os.getenv("TTS_VOICE", "")  # a voice id or name; empty = Indian English if installed, else US English
TIMEOUT_SECONDS = 90
CACHE_DIR = Path(tempfile.gettempdir()) / "vidyapath_tts"
ROOT = Path(__file__).resolve().parents[2]  # the synthesis process imports backend from here

_slots = threading.Semaphore(2)  # at most two synthesis processes at once


class Unavailable(RuntimeError):
    """No speech engine on this machine (e.g. espeak-ng not installed); the UI falls back to the browser's voice."""


def _to_mp3(wav_path):
    import lameenc

    with wave.open(str(wav_path), "rb") as w:
        encoder = lameenc.Encoder()
        encoder.set_bit_rate(48)  # speech: small files, still clear
        encoder.set_in_sample_rate(w.getframerate())
        encoder.set_channels(w.getnchannels())
        encoder.set_quality(5)
        return encoder.encode(w.readframes(w.getnframes())) + encoder.flush()


def speech_mp3(text):
    """Returns the path of an MP3 of `text` read aloud."""
    text = " ".join(str(text).split())[:MAX_CHARS]
    key = hashlib.sha256(f"{RATE}|{VOICE}|{text}".encode("utf-8")).hexdigest()
    mp3 = CACHE_DIR / f"{key}.mp3"
    if mp3.exists():
        return mp3
    CACHE_DIR.mkdir(exist_ok=True)
    wav = CACHE_DIR / f"{key}.{threading.get_ident()}.wav"  # per thread: two requests for one text don't clash
    with _slots:
        try:
            done = subprocess.run([sys.executable, "-m", "backend.tools.tts", str(wav)], input=text.encode("utf-8"),
                                  capture_output=True, timeout=TIMEOUT_SECONDS, cwd=ROOT)
        except subprocess.TimeoutExpired:
            wav.unlink(missing_ok=True)
            raise Unavailable("The speech engine took too long")
    if done.returncode != 0 or not wav.exists():
        wav.unlink(missing_ok=True)
        reason = done.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or ["no audio produced"]
        raise Unavailable(f"Text to speech is not available on the server: {reason[0]}")
    tmp = mp3.with_suffix(f".{threading.get_ident()}.part")
    tmp.write_bytes(_to_mp3(wav))
    tmp.replace(mp3)  # appears complete or not at all
    wav.unlink(missing_ok=True)
    return mp3


# --------------------------------------------------------------------------- #
# The synthesis process: python -m backend.tools.tts OUT.wav < text
# --------------------------------------------------------------------------- #
def _pick_voice(voices):
    def find(*words):
        for v in voices:
            label = f"{v.id} {v.name}".lower()
            if all(w in label for w in words):
                return v.id
        return None
    if VOICE:
        return find(VOICE.lower())
    return find("english", "india") or find("en-in") or find("english", "america") or find("en-us")


def _synthesize(text, out_path):
    import pyttsx3

    finished = threading.Event()
    engine = pyttsx3.init()
    engine.setProperty("rate", RATE)
    voice = _pick_voice(engine.getProperty("voices") or [])
    if voice:
        engine.setProperty("voice", voice)
    # On Linux runAndWait() can return before the audio file is written, so also wait for this event
    engine.connect("finished-utterance", lambda **_: finished.set())
    engine.save_to_file(text, out_path)
    engine.runAndWait()
    if not finished.wait(TIMEOUT_SECONDS) or not os.path.exists(out_path):
        sys.exit("The speech engine did not produce audio")


if __name__ == "__main__":
    sys.stdout = sys.stderr  # pyttsx3 prints "Audio saved to ..."; keep stdout clean
    _synthesize(sys.stdin.buffer.read().decode("utf-8"), sys.argv[1])
    os._exit(0)  # don't wait for espeak's background thread to wind down
