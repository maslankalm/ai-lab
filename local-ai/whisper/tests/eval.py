#!/usr/bin/env python3
"""Score whisper.cpp transcripts against HUMAN YouTube captions (word error rate).

  python3 tests/eval.py                 # all videos in VIDEOS, both models
  python3 tests/eval.py --models turbo

For every video: download the manual captions (the reference) and YouTube's own
auto-captions (a baseline), transcribe with each model via ../transcribe.sh using
language auto-detection, then compute WER after light normalisation (lowercase, no
punctuation, no [music]/(applause) tags). Human captions are usually "clean verbatim"
(fillers dropped, small edits), so even a perfect transcript scores a few % WER --
compare models to each other and to YouTube, not to 0.
"""
import argparse, difflib, glob, json, os, re, subprocess, sys, time, unicodedata

H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEOS = [  # id, spoken language (only used to pick the reference captions)
    ("5MuIMqhT8DM", "en"),   # Matt Walker, Sleep Is Your Superpower (TED), 19 min
    ("gUV5DJb6KGs", "en"),   # Karen Faith (TEDxKC), 14 min
    ("ktjMz7c3ke4", "pl"),   # Jacek Walkiewicz (TEDxWSB), 20 min
    ("purKIRrPJvc", "pl"),   # Mariusz Kedzierski (TEDx), 17 min
]


def captions(vid, lang, auto):
    d = os.path.join(H, "transcripts", vid); os.makedirs(d, exist_ok=True)
    tag = "auto" if auto else "human"
    out = os.path.join(d, f"yt-{tag}.txt")
    if os.path.exists(out):
        return open(out).read()
    subs = f"{lang}-orig,{lang}" if auto else lang
    subprocess.run(["yt-dlp", "--no-warnings", "-q", "--skip-download",
                    "--write-auto-subs" if auto else "--write-subs", "--sub-langs", subs,
                    "--sub-format", "json3", "-o", os.path.join(d, f"yt-{tag}"),
                    f"https://www.youtube.com/watch?v={vid}"], check=True)
    files = sorted(glob.glob(os.path.join(d, f"yt-{tag}.*.json3")))
    if not files:
        return None
    ev = json.load(open(files[0]))["events"]
    text = " ".join("".join(s.get("utf8", "") for s in e.get("segs", [])) for e in ev)
    open(out, "w").write(text)
    return text


def words(t):
    t = unicodedata.normalize("NFC", t.lower()).replace("’", "'").replace("‘", "'")  # curly -> straight
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", t)          # [music], (applause), (laughter)
    t = re.sub(r"[^\w\s']|_", " ", t).replace("'", "")
    return t.split()


def wer(ref, hyp):
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1] / max(1, len(ref))


def diffs(ref, hyp, n=6):
    sm = difflib.SequenceMatcher(a=ref, b=hyp, autojunk=False)
    out = [(" ".join(ref[a1:a2]), " ".join(hyp[b1:b2]))
           for op, a1, a2, b1, b2 in sm.get_opcodes() if op != "equal"]
    return out[:: max(1, len(out) // n)][:n]


def problems(ref, hyp):
    """Long passages the transcript invented or dropped (>=5 words), and repetition loops."""
    sm = difflib.SequenceMatcher(a=ref, b=hyp, autojunk=False)
    big = [(op, " ".join(ref[a1:a2])[:70], " ".join(hyp[b1:b2])[:70])
           for op, a1, a2, b1, b2 in sm.get_opcodes() if op != "equal" and max(a2 - a1, b2 - b1) >= 5]
    loops = re.findall(r"(\b(?:\w+\s+){3,8}?)\1{2,}", " ".join(hyp) + " ")
    return big, loops


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=["turbo"])  # full removed 2026-09-25
    ap.add_argument("--score-only", action="store_true", help="don't transcribe, score what's on disk")
    a = ap.parse_args()
    rows = []
    for vid, lang in VIDEOS:
        d = os.path.join(H, "transcripts", vid)
        ref = words(captions(vid, lang, auto=False) or "")
        captions(vid, lang, auto=True)
        print(f"\n== {vid} ({lang})  reference: {len(ref)} words", flush=True)
        timing = {}
        if not a.score_only:
            for m in a.models:
                p = subprocess.run([os.path.join(H, "transcribe.sh"), vid, "auto"], capture_output=True, text=True)
                if p.returncode:
                    print(f"  {m} FAILED: {p.stderr[-300:]}"); continue
                timing[m] = p.stdout.strip().split(": ", 1)[-1].split(" ->")[0]
        for sysname in ["yt-auto"] + [f"{m}{v}" for m in a.models for v in ("-novad", "")]:
            f = os.path.join(d, f"{sysname}.txt")
            if not os.path.exists(f):
                continue
            hyp = words(open(f).read())
            w = wer(ref, hyp); big, loops = problems(ref, hyp)
            det = ""
            if os.path.exists(os.path.join(d, f"{sysname}.log")):
                det = (re.search(r"auto-detected language: (\w+)", open(os.path.join(d, f"{sysname}.log")).read()) or [None, "?"])[1]
            print(f"  {sysname:<12} WER {w:6.1%}  long diffs {len(big):2d}  loops {len(loops)}  "
                  f"{('lang=' + det) if det else '':<8} {timing.get(sysname, '')}", flush=True)
            for op, r_, h_ in big[:4]:
                print(f"      {op:<7} ref={r_!r}\n              got={h_!r}")
            rows.append(dict(video=vid, lang=lang, system=sysname, wer=round(w, 4), long_diffs=len(big),
                             loops=len(loops), detected=det, timing=timing.get(sysname)))
    stamp = time.strftime("%Y%m%d-%H%M%S")
    os.makedirs(os.path.join(H, "results"), exist_ok=True)
    json.dump(rows, open(os.path.join(H, "results", f"eval-{stamp}.json"), "w"), indent=2)
    print(f"\n-> results/eval-{stamp}.json")


if __name__ == "__main__":
    main()
