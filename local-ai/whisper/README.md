# whisper — local speech-to-text

whisper.cpp (Homebrew build, Metal GPU) + Whisper **large-v3-turbo** + **Silero VAD**: a
YouTube URL or a local audio/video file in, a `.txt` transcript and `.srt` subtitles out.
Transcripts are small enough to hand to the local LLMs in [`../llama-cpp-prism`](../llama-cpp-prism/)
for summaries or Q&A (an hour of speech is ~10–15K tokens; the models take 262K).

## Use

```sh
./transcribe.sh "https://www.youtube.com/watch?v=..."   # language auto-detected
./transcribe.sh talk.mp4 pl                              # force a language
VAD=0 ./transcribe.sh <url|file>                         # without VAD -> turbo-novad.*
```

Output: `transcripts/<video-id or file name>/turbo.txt` + `turbo.srt`, plus `audio.wav`
(16 kHz mono, reused on re-runs) and the whisper log. `transcripts/` is gitignored.

## Install

`../setup.sh` does both steps:

- `brew install whisper.cpp ffmpeg yt-dlp` — whisper.cpp is upstream and packaged, so brew
  is fine here (unlike the llama.cpp fork, which has no package).
- `./download_models.sh` — pinned Hugging Face revisions, SHA256-checked:
  - `ggml-large-v3-turbo.bin` 1.62 GB (`ggerganov/whisper.cpp`)
  - `ggml-silero-v6.2.0.bin` 0.9 MB (`ggml-org/whisper-vad`)

## Speed (M5 Pro, measured, including the YouTube download)

| audio | large-v3-turbo | large-v3 (full) |
|---|---|---|
| 14–20 min talks | 19–37 s (**33–46x** real time) | 64–127 s (10–16x) |
| 86 min two-speaker Polish podcast | **2.7 min** | 8.6 min |

## Quality — WER against human captions

[`tests/eval.py`](tests/eval.py) downloads each video's **human-made** YouTube captions as
the reference, transcribes with language auto-detection, and scores word error rate after
light normalisation. YouTube's own auto-captions are scored the same way as a baseline.
Raw numbers: [`results/eval-20260925-130039.json`](results/eval-20260925-130039.json).

| video | YouTube auto | turbo | **turbo + VAD** | full | full + VAD |
|---|---|---|---|---|---|
| English TED talk, 19 min | 3.2% | 1.8% | **1.4%** | 3.7% | 2.3% |
| English TEDx talk, 14 min | 2.3% | 4.0% | **1.7%** | 9.7% | 7.0% |
| Polish TEDx talk, 20 min | (none) | 12.1% | **12.2%** | 14.3% | 12.8% |
| Polish TEDx talk, 17 min | 22.1% | 22.4% | **21.3%** | 21.9% | 25.2% |

What the numbers hide — every long difference was checked by hand:

- **turbo + VAD wins**, and beats YouTube's own auto-captions on both English talks.
- **VAD fixed Whisper's best-known failure.** Without it, both models invented text during
  silent or music-only intros — subtitle *credits* ("Transcriber: … Reviewer: …", a
  channel's web address) learned from their training data. VAD drops non-speech before
  Whisper sees it; every invented intro disappeared.
- **The full model is worse, not better**: repetition loops (the same sentence 3–5x), and
  once it replaced the first 30 s of real speech with a sign-off line ("thanks, see you in
  the next episodes"). It is also ~3x slower, so it was dropped.
- **Polish WER is mostly the reference, not the model.** Human captions are "clean
  verbatim" and heavily edited for Polish. Where Whisper *and* YouTube both differ from the
  captions in the same way, the captions changed the words. The transcripts read fluently.
- Small scorer pitfalls fixed along the way: curly vs straight apostrophes (`can’t` split
  into two words), `[music]` / `(applause)` tags, credits lines in the reference.
