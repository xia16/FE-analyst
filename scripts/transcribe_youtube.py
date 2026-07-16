#!/usr/bin/env python3
"""Free YouTube transcription — no API key, no paid service.

Primary:  youtube-transcript-api (pulls YouTube's existing manual/auto captions)
Fallback: yt-dlp (downloads the caption track directly, then parses the VTT)

Usage:
    python scripts/transcribe_youtube.py <url-or-id> [--out DIR] [--langs en,zh-Hans,zh]

Writes two files to --out (default: reports/output/transcripts/):
    <video_id>.txt   — clean plain-text transcript
    <video_id>.json  — timestamped segments  [{start, dur, text}, ...]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Language preference order when the requested langs aren't all present.
DEFAULT_LANGS = ["en", "en-US", "zh-Hans", "zh-Hant", "zh", "zh-CN", "ja", "ko"]


def parse_video_id(url_or_id: str) -> str:
    """Accept a full URL, a youtu.be link, or a bare 11-char ID."""
    if re.fullmatch(r"[\w-]{11}", url_or_id):
        return url_or_id
    m = re.search(r"(?:v=|/shorts/|youtu\.be/|/embed/)([\w-]{11})", url_or_id)
    if m:
        return m.group(1)
    raise SystemExit(f"Could not extract a video id from: {url_or_id}")


# --------------------------------------------------------------- primary
def via_transcript_api(video_id: str, langs: list[str]) -> tuple[list[dict], str] | None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return None

    def _normalize(fetched) -> list[dict]:
        out = []
        for s in fetched:
            if isinstance(s, dict):  # old static API returns dicts
                out.append({"start": s["start"], "dur": s["duration"], "text": s["text"]})
            else:  # new 1.x snippet objects
                out.append({"start": s.start, "dur": s.duration, "text": s.text})
        return out

    # New instance-based API (>=1.0)
    try:
        api = YouTubeTranscriptApi()
        available = []
        try:
            for t in api.list(video_id):
                available.append((t.language_code, "auto" if t.is_generated else "manual"))
        except Exception:
            pass
        if available:
            print(f"  available captions: {available}")
        # Prefer requested langs, then any available, manual before auto.
        try_order = langs + [lc for lc, _ in sorted(available, key=lambda x: x[1] != "manual")]
        seen = set()
        try_order = [x for x in try_order if not (x in seen or seen.add(x))]
        fetched = api.fetch(video_id, languages=try_order or langs)
        lang = getattr(fetched, "language_code", "?")
        return _normalize(fetched), lang
    except AttributeError:
        pass  # fall through to old API
    except Exception as e:
        print(f"  transcript-api (new) failed: {type(e).__name__}: {str(e)[:140]}")

    # Old static API (<=0.6)
    try:
        data = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
        return _normalize(data), langs[0]
    except Exception as e:
        print(f"  transcript-api (old) failed: {type(e).__name__}: {str(e)[:140]}")
        return None


# --------------------------------------------------------------- fallback
def _parse_vtt(text: str) -> list[dict]:
    segs, cur_start, buf = [], None, []
    ts = re.compile(r"(\d\d:\d\d:\d\d[.,]\d\d\d)\s*-->\s*(\d\d:\d\d:\d\d[.,]\d\d\d)")

    def to_sec(t: str) -> float:
        h, m, s = t.replace(",", ".").split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    for line in text.splitlines():
        mt = ts.search(line)
        if mt:
            if cur_start is not None and buf:
                segs.append({"start": cur_start, "dur": 0.0, "text": " ".join(buf).strip()})
            cur_start, buf = to_sec(mt.group(1)), []
        elif line.strip() and "WEBVTT" not in line and not line.strip().isdigit():
            clean = re.sub(r"<[^>]+>", "", line).strip()
            if clean:
                buf.append(clean)
    if cur_start is not None and buf:
        segs.append({"start": cur_start, "dur": 0.0, "text": " ".join(buf).strip()})
    # de-dup consecutive identical lines (auto-caption rolling repeats)
    deduped = []
    for s in segs:
        if not deduped or deduped[-1]["text"] != s["text"]:
            deduped.append(s)
    return deduped


def via_ytdlp(video_id: str, langs: list[str]) -> tuple[list[dict], str] | None:
    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [
            sys.executable, "-m", "yt_dlp", "--skip-download",
            "--write-subs", "--write-auto-subs",
            "--sub-langs", ",".join(langs) + ",-live_chat",
            "--sub-format", "vtt", "-o", str(Path(tmp) / "%(id)s.%(ext)s"), url,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        vtts = list(Path(tmp).glob("*.vtt"))
        if not vtts:
            print(f"  yt-dlp: no subtitles found\n  {r.stderr[-300:]}")
            return None
        # pick the file whose lang appears earliest in preference order
        def rank(p: Path) -> int:
            for i, lg in enumerate(langs):
                if f".{lg}." in p.name:
                    return i
            return len(langs)
        vtt = sorted(vtts, key=rank)[0]
        lang = re.search(r"\.([\w-]+)\.vtt$", vtt.name)
        return _parse_vtt(vtt.read_text(encoding="utf-8", errors="ignore")), (
            lang.group(1) if lang else "?"
        )


def via_whisper(video_id: str, langs: list[str], model_size: str = "small",
                force_lang: str | None = None) -> tuple[list[dict], str] | None:
    """Last resort for caption-less videos: download audio + local Whisper STT.

    Free & offline (faster-whisper, MIT). yt-dlp fetches the raw audio stream so
    no system ffmpeg is required — faster-whisper decodes via bundled PyAV.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("  faster-whisper not installed (pip install faster-whisper)")
        return None

    url = f"https://www.youtube.com/watch?v={video_id}"
    tmp = Path(tempfile.mkdtemp())
    audio_tmpl = str(tmp / f"{video_id}.%(ext)s")
    r = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "-f", "bestaudio",
         "--no-post-overwrites", "-o", audio_tmpl, url],
        capture_output=True, text=True, timeout=300,
    )
    audio = next(iter(tmp.glob(f"{video_id}.*")), None)
    if audio is None:
        print(f"  yt-dlp audio download failed\n  {r.stderr[-300:]}")
        return None

    # Prefer an explicit --lang; otherwise let Whisper auto-detect (None) rather
    # than blindly forcing the first entry of the preference list (which would
    # transcribe non-English audio in the wrong language).
    forced = force_lang
    print(f"  transcribing with Whisper ({model_size}, int8, lang={forced or 'auto'})… "
          "this can take several minutes")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(audio), language=forced, beam_size=5, vad_filter=True)
    out = [{"start": round(s.start, 2), "dur": round(s.end - s.start, 2), "text": s.text.strip()}
           for s in segments]
    return out, info.language


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="YouTube URL or 11-char video id")
    ap.add_argument("--out", default="reports/output/transcripts")
    ap.add_argument("--langs", default=",".join(DEFAULT_LANGS))
    ap.add_argument("--whisper", action="store_true",
                    help="Force local Whisper STT (for caption-less videos)")
    ap.add_argument("--model", default="small", help="Whisper model size")
    ap.add_argument("--lang", default=None, help="Force Whisper language (e.g. zh, en); default auto-detect")
    args = ap.parse_args()

    video_id = parse_video_id(args.url)
    langs = [x.strip() for x in args.langs.split(",") if x.strip()]
    print(f"video id: {video_id}")

    result = None
    if not args.whisper:
        print("trying youtube-transcript-api…")
        result = via_transcript_api(video_id, langs)
        if not result or not result[0]:
            print("falling back to yt-dlp captions…")
            result = via_ytdlp(video_id, langs)
    if not result or not result[0]:
        print("no captions available — falling back to local Whisper STT…")
        result = via_whisper(video_id, langs, args.model, force_lang=args.lang)
    if not result or not result[0]:
        raise SystemExit("No transcript could be retrieved.")

    segments, lang = result
    text = "\n".join(s["text"] for s in segments if s["text"])
    words = len(text.split())

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{video_id}.txt").write_text(text, encoding="utf-8")
    (out_dir / f"{video_id}.json").write_text(
        json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    dur = segments[-1]["start"] if segments else 0
    print(
        f"\n✓ transcript language: {lang}\n"
        f"  segments: {len(segments)}  words: {words}  ~duration: {dur/60:.1f} min\n"
        f"  saved: {out_dir / (video_id + '.txt')}\n"
        f"         {out_dir / (video_id + '.json')}"
    )


if __name__ == "__main__":
    main()
