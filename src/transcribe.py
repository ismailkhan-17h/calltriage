import os
import sys
import json
import time
import requests

from pydub import AudioSegment
from pydub.silence import detect_nonsilent
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("PRISMA_API_URL")
API_KEY = os.getenv("PRISMA_API_KEY")
KEY_HEADER = os.getenv("PRISMA_KEY_HEADER", "X-API-Key")

MAX_SEG_MS = 10_000
RETRYABLE = (429, 502, 503, 504)


def split_audio(path):
    print("Loading audio:", path, flush=True)

    audio = AudioSegment.from_file(path).set_channels(1)

    spans = detect_nonsilent(
        audio,
        min_silence_len=400,
        silence_thresh=audio.dBFS - 16,
        seek_step=10,
    )

    segments = []
    cur_start, cur_end = None, None

    for s, e in spans:
        if cur_start is None:
            cur_start, cur_end = s, e
        elif e - cur_start <= MAX_SEG_MS:
            cur_end = e
        else:
            segments.append((cur_start, cur_end))
            cur_start, cur_end = s, e

    if cur_start is not None:
        segments.append((cur_start, cur_end))

    # Fallback: fixed windows if silence detection found nothing
    if not segments:
        segments = [
            (i, min(i + MAX_SEG_MS, len(audio)))
            for i in range(0, len(audio), MAX_SEG_MS)
        ]

    # Break any span longer than the limit
    final = []
    for s, e in segments:
        while e - s > MAX_SEG_MS:
            final.append((s, s + MAX_SEG_MS))
            s += MAX_SEG_MS
        final.append((s, e))

    return [(s, e, audio[s:e]) for s, e in final]


def transcribe_segment(seg_path, language_code="indic-auto", retries=4):
    """Returns (text, ok). ok=False means the API failed after all retries."""
    print("Sending audio to API:", seg_path, flush=True)

    if not API_URL or not API_KEY:
        raise ValueError("Missing PRISMA_API_URL or PRISMA_API_KEY in .env")

    for attempt in range(1, retries + 1):
        try:
            with open(seg_path, "rb") as f:
                r = requests.post(
                    API_URL,
                    headers={KEY_HEADER: API_KEY},
                    data={"language_code": language_code},
                    files={"audio_file": ("segment.wav", f, "audio/wav")},
                    timeout=(15, 120),
                )

            print("HTTP STATUS:", r.status_code, flush=True)

            if r.status_code in RETRYABLE:
                raise requests.exceptions.RequestException(
                    f"retryable status {r.status_code}"
                )

            r.raise_for_status()
            transcript = r.json().get("transcript", "").strip()
            print("Extracted transcript:", repr(transcript), flush=True)
            return transcript, True

        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt}/{retries} failed: {e}", flush=True)
            if attempt < retries:
                time.sleep(3 * attempt)

    print("Giving up on this segment.", flush=True)
    return "", False


def transcribe_call(path, out_dir="data/segments", language_code="indic-auto"):
    print("\nStarting transcription...", flush=True)

    if not os.path.isfile(path):
        raise FileNotFoundError(f"Audio not found: {path}")

    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]

    segments = split_audio(path)
    print("Total segments:", len(segments), flush=True)

    results = []
    failed = 0

    for i, (s, e, seg) in enumerate(segments):
        print(f"\nProcessing segment {i + 1}/{len(segments)}", flush=True)

        seg_path = os.path.join(out_dir, f"{base}_{i:03d}.wav")
        seg.export(seg_path, format="wav")

        text, ok = transcribe_segment(seg_path, language_code)
        if not ok:
            failed += 1

        if text:
            results.append({
                "start_s": round(s / 1000, 1),
                "end_s": round(e / 1000, 1),
                "text": text,
                "audio": seg_path,
            })

    print("\nTotal successful transcripts:", len(results), flush=True)
    if failed:
        print(
            f"WARNING: {failed} segment(s) failed after retries. "
            f"Delete the cached JSON for '{base}' in data/transcripts or "
            f"data/transcripts_noisy and rerun to get a complete transcript.",
            flush=True,
        )

    return results


if __name__ == "__main__":
    print("TRANSCRIPTION SCRIPT STARTED", flush=True)

    if len(sys.argv) < 2:
        print("Usage: python src/transcribe.py <audio_file> [language_code]")
        sys.exit(1)

    language_code = sys.argv[2] if len(sys.argv) > 2 else "indic-auto"

    supported_languages = [
        "as-IN", "bn-IN", "en-IN", "gu-IN", "hi-IN",
        "kn-IN", "ml-IN", "mr-IN", "pa-IN", "ta-IN",
        "te-IN", "indic-auto",
    ]

    if language_code not in supported_languages:
        print("Unsupported language code:", language_code)
        print("Supported languages:", ", ".join(supported_languages))
        sys.exit(1)

    result = transcribe_call(sys.argv[1], language_code=language_code)

    print("\n========== FINAL TRANSCRIPTION ==========\n")
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)