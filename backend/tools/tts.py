# Text to speech, offline on the server. Piper (natural neural voices) when it can run; pyttsx3 (espeak-ng, installed
# on Railway via railpack.json) as the fallback. Speech is returned as MP3 and cached by its text, so replaying is instant.
# The UI sends long texts a few sentences at a time, so playback starts quickly even though Piper takes ~1s per sentence.
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import wave
from pathlib import Path

MAX_CHARS = 8000  # roughly 8 minutes of speech
CACHE_DIR = Path(tempfile.gettempdir()) / "vidyapath_tts"
TIMEOUT_SECONDS = 90

# Piper: any voice from https://huggingface.co/rhasspy/piper-voices, e.g. en_GB-jenny_dioco-medium. A voice with several
# speakers (en_US-l2arctic-medium) takes PIPER_SPEAKER, a name or number; SVBI and TNI (female), ASI and RRBI (male)
# are speakers whose first language is Hindi.
PIPER_VOICE = os.getenv("PIPER_VOICE", "en_US-lessac-medium")
PIPER_SPEAKER = os.getenv("PIPER_SPEAKER", "")
SPEED = float(os.getenv("TTS_SPEED", "1.05"))  # Piper length scale: above 1 is slower
VOICES_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
VOICES_DIR = Path(tempfile.gettempdir()) / "vidyapath_voices"  # downloaded once per server (about 60 MB)
RETRY_SECONDS = 300  # after Piper fails to start, use pyttsx3 for this long before trying again
THREADS = int(os.getenv("TTS_THREADS", "0"))  # 0 = the CPUs this container may actually use

# pyttsx3 (the fallback)
RATE = int(os.getenv("TTS_RATE", "160"))  # words per minute (pyttsx3 default 200 is fast for lessons)
ESPEAK_VOICE = os.getenv("ESPEAK_VOICE", "")  # a voice id or name; empty = Indian English if installed, else US English
ROOT = Path(__file__).resolve().parents[2]  # the pyttsx3 process imports backend from here


class Unavailable(RuntimeError):
    """No speech engine on this machine; the UI falls back to the browser's voice."""


def speech_mp3(text):
    """Returns (path of an MP3 of `text` read aloud, the engine that made it: "piper" or "pyttsx3")."""
    text = " ".join(str(text).split())[:MAX_CHARS]
    voice = _piper_voice()
    if voice is not None:
        try:
            return _cached(f"piper|{PIPER_VOICE}|{PIPER_SPEAKER}|{SPEED}", text, lambda wav: _piper_wav(voice, text, wav)), "piper"
        except Exception as e:
            print(f"Piper failed, using pyttsx3: {e}", file=sys.stderr)
    return _cached(f"pyttsx3|{RATE}|{ESPEAK_VOICE}", text, lambda wav: _pyttsx3_wav(text, wav)), "pyttsx3"


def warm_up():
    """Downloads and loads the Piper voice in the background, so the first Read aloud is quick."""
    threading.Thread(target=_piper_voice, daemon=True).start()


def _cached(engine, text, make_wav):
    key = hashlib.sha256(f"{engine}|{text}".encode("utf-8")).hexdigest()
    mp3 = CACHE_DIR / f"{key}.mp3"
    if mp3.exists():
        return mp3
    CACHE_DIR.mkdir(exist_ok=True)
    wav = CACHE_DIR / f"{key}.{threading.get_ident()}.wav"  # per thread: two requests for one text don't clash
    try:
        make_wav(wav)
        tmp = mp3.with_suffix(f".{threading.get_ident()}.part")
        tmp.write_bytes(_to_mp3(wav))
        tmp.replace(mp3)  # appears complete or not at all
    finally:
        wav.unlink(missing_ok=True)
    return mp3


def _to_mp3(wav_path):
    import lameenc

    with wave.open(str(wav_path), "rb") as w:
        encoder = lameenc.Encoder()
        encoder.set_bit_rate(64)  # speech: small files, still clear
        encoder.set_in_sample_rate(w.getframerate())
        encoder.set_channels(w.getnchannels())
        encoder.set_quality(5)
        return encoder.encode(w.readframes(w.getnframes())) + encoder.flush()


# --------------------------------------------------------------------------- #
# Piper
# --------------------------------------------------------------------------- #
_piper = None
_piper_failed_at = 0.0
_piper_lock = threading.Lock()  # one download/load at a time
_synth_lock = threading.Lock()  # Piper's phonemizer (espeak) is not thread-safe


def _voice_url(name):
    """en_US-lessac-medium -> .../en/en_US/lessac/medium/en_US-lessac-medium"""
    region, speaker, quality = name.split("-", 2)
    return f"{VOICES_URL}/{region.split('_')[0]}/{region}/{speaker}/{quality}/{name}"


def _download(url, dest):
    tmp = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(url, timeout=120) as response, open(tmp, "wb") as f:
        shutil.copyfileobj(response, f)
    tmp.replace(dest)


def _piper_voice():
    """The loaded Piper voice, or None if Piper can't run here (then pyttsx3 is used)."""
    global _piper, _piper_failed_at
    if _piper is not None or time.time() - _piper_failed_at < RETRY_SECONDS:
        return _piper
    with _piper_lock:
        if _piper is None:
            try:
                from piper import PiperVoice

                VOICES_DIR.mkdir(exist_ok=True)
                for ext in (".onnx.json", ".onnx"):
                    path = VOICES_DIR / f"{PIPER_VOICE}{ext}"
                    if not path.exists():
                        _download(_voice_url(PIPER_VOICE) + ext, path)
                _piper = _with_threads(PiperVoice.load(str(VOICES_DIR / f"{PIPER_VOICE}.onnx")))
            except Exception as e:
                _piper_failed_at = time.time()
                print(f"Piper voice {PIPER_VOICE} unavailable, using pyttsx3: {e}", file=sys.stderr)
    return _piper


def _cpu_limit():
    """CPUs this container may use. os.cpu_count() is the whole host (often dozens on Railway); the cgroup quota is the
    real limit, and running more threads than it allows makes onnxruntime many times slower."""
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()
        if quota != "max":
            return max(1, int(int(quota) / int(period)))
    except (OSError, ValueError):
        pass
    return len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (os.cpu_count() or 1)


def _with_threads(voice):
    """Piper's own session uses one thread per host CPU; replace it with one sized to this container."""
    import onnxruntime

    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = THREADS or min(_cpu_limit(), 8)
    options.inter_op_num_threads = 1
    voice.session = onnxruntime.InferenceSession(str(VOICES_DIR / f"{PIPER_VOICE}.onnx"), sess_options=options,
                                                 providers=["CPUExecutionProvider"])
    print(f"Piper voice {PIPER_VOICE} ready with {options.intra_op_num_threads} thread(s)", file=sys.stderr)
    return voice


def _speaker_id(voice):
    if not PIPER_SPEAKER:
        return None
    speakers = voice.config.speaker_id_map or {}
    return speakers.get(PIPER_SPEAKER, int(PIPER_SPEAKER) if PIPER_SPEAKER.isdigit() else None)


def _piper_wav(voice, text, wav_path):
    from piper import SynthesisConfig

    config = SynthesisConfig(speaker_id=_speaker_id(voice), length_scale=SPEED)
    with _synth_lock, wave.open(str(wav_path), "wb") as w:
        voice.synthesize_wav(text, w, syn_config=config)


# --------------------------------------------------------------------------- #
# pyttsx3: each synthesis runs in its own short-lived process. pyttsx3's espeak driver keeps shared state between
# utterances and returns before the audio is written; a separate process can't interfere, and is killed on timeout.
# --------------------------------------------------------------------------- #
_pyttsx3_slots = threading.Semaphore(2)  # at most two synthesis processes at once


def _pyttsx3_wav(text, wav_path):
    with _pyttsx3_slots:
        try:
            done = subprocess.run([sys.executable, "-m", "backend.tools.tts", str(wav_path)], input=text.encode("utf-8"),
                                  capture_output=True, timeout=TIMEOUT_SECONDS, cwd=ROOT)
        except subprocess.TimeoutExpired:
            raise Unavailable("The speech engine took too long")
    if done.returncode != 0 or not wav_path.exists():
        reason = done.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or ["no audio produced"]
        raise Unavailable(f"Text to speech is not available on the server: {reason[0]}")


def _pick_espeak_voice(voices):
    def find(*words):
        for v in voices:
            label = f"{v.id} {v.name}".lower()
            if all(w in label for w in words):
                return v.id
        return None
    if ESPEAK_VOICE:
        return find(ESPEAK_VOICE.lower())
    return find("english", "india") or find("en-in") or find("english", "america") or find("en-us")


def _pyttsx3_synthesize(text, out_path):
    import pyttsx3

    finished = threading.Event()
    engine = pyttsx3.init()
    engine.setProperty("rate", RATE)
    voice = _pick_espeak_voice(engine.getProperty("voices") or [])
    if voice:
        engine.setProperty("voice", voice)
    # On Linux runAndWait() can return before the audio file is written, so also wait for this event
    engine.connect("finished-utterance", lambda **_: finished.set())
    engine.save_to_file(text, out_path)
    engine.runAndWait()
    if not finished.wait(TIMEOUT_SECONDS) or not os.path.exists(out_path):
        sys.exit("The speech engine did not produce audio")


if __name__ == "__main__":  # the pyttsx3 process: python -m backend.tools.tts OUT.wav < text
    sys.stdout = sys.stderr  # pyttsx3 prints "Audio saved to ..."; keep stdout clean
    _pyttsx3_synthesize(sys.stdin.buffer.read().decode("utf-8"), sys.argv[1])
    os._exit(0)  # don't wait for espeak's background thread to wind down
