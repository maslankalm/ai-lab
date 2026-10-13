#!/usr/bin/env python3
"""Run the quality eval set against the router (../run.sh, 127.0.0.1:8888).

  python3 quality/run.py                      # full: 2 rounds x 2 models x 16 tasks
  python3 quality/run.py --only M3 S2 C3      # subset, for smoke tests
  python3 quality/run.py --rounds 1

Both models get identical settings: their recommended sampling (temp 1.0, top_p 0.95,
top_k 20, min_p 0.05), thinking on at reasoning_effort=medium, max_tokens 8192, same seed
per round. Model-written code runs ONLY inside Docker: --network none, read-only root,
256 MB RAM, 1 CPU, 64 pids, 20 s timeout.
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, time, urllib.error, urllib.request, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import evalset as E  # noqa: E402

URL = "http://127.0.0.1:8888"
KEY = open(os.path.join(ROOT, "secrets", "api-key.txt")).read().strip()
MODELS = ["qwen3.8-27b", "bonsai2-27b"]
SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05,
            "reasoning_effort": "medium", "max_tokens": 8192}

HARNESS = r"""
import json, sys
sys.path.insert(0, "/work")
{tests}
def norm(v):
    if isinstance(v, (list, tuple)): return [norm(x) for x in v]
    return v
def call(x):
    return f(*x) if isinstance(x, tuple) else f(x)
res = {{"passed": 0, "total": 0, "fail": []}}
for x, w in T:
    res["total"] += 1
    try:
        got = call(x)
        if norm(got) == norm(w): res["passed"] += 1
        else: res["fail"].append(f"{{x!r}} -> {{got!r}}, want {{w!r}}")
    except Exception as e:
        res["fail"].append(f"{{x!r}} raised {{type(e).__name__}}: {{e}}")
for x in globals().get("BAD", []):
    res["total"] += 1
    try:
        got = call(x); res["fail"].append(f"{{x!r}} -> {{got!r}}, want ValueError")
    except ValueError:
        res["passed"] += 1
    except Exception as e:
        res["fail"].append(f"{{x!r}} raised {{type(e).__name__}}, want ValueError")
print(json.dumps(res))
"""


def sandbox(code, tests, mode):
    d = tempfile.mkdtemp(prefix="qeval-")
    try:
        open(os.path.join(d, "solution.py"), "w").write(code)
        open(os.path.join(d, "tests.py"), "w").write(HARNESS.format(tests=tests))
        cmd = ["docker", "run", "--rm", "--network", "none", "--read-only", "--memory", "256m",
               "--cpus", "1", "--pids-limit", "64", "--security-opt", "no-new-privileges",
               "-v", f"{d}:/work:ro", "-w", "/work", "python:3.12-slim",
               "timeout", "20", "python", "-I", "/work/tests.py"]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        line = (p.stdout.strip().splitlines() or [""])[-1]
        try:
            r = json.loads(line)
        except Exception:
            return False, f"harness error rc={p.returncode}: {(p.stderr or p.stdout)[-160:]!r}"
        ok = r["passed"] == r["total"]
        return ok, f"{r['passed']}/{r['total']} tests" + ("" if ok else f"; e.g. {r['fail'][:2]}")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def chat(model, task, seed):
    body = {"model": model, "messages": task["messages"], "seed": seed, **SAMPLING}
    if task.get("tools"):
        body["tools"] = task["tools"]; body["parallel_tool_calls"] = True
    req = urllib.request.Request(URL + "/v1/chat/completions", data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=3600) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read().decode()[:200]}"}, time.time() - t0
    return d, time.time() - t0


def validity(msg, finish):
    """Problems a user would notice regardless of correctness."""
    c = msg.get("content") or ""
    flags = []
    if finish == "length": flags.append("TRUNCATED (hit max_tokens)")
    if not c.strip() and not msg.get("tool_calls"): flags.append("EMPTY")
    if len(c) > 400 and len(zlib.compress(c.encode())) / len(c) < 0.08: flags.append("LOOPING")
    return flags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--only", nargs="*", help="task id prefixes")
    ap.add_argument("--models", nargs="*", default=MODELS)
    a = ap.parse_args()
    tasks = [t for t in E.TASKS if not a.only or any(t["id"].startswith(p) for p in a.only)]

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = os.path.join(ROOT, "results", f"quality-{stamp}")
    os.makedirs(out_dir)
    raw = open(os.path.join(out_dir, "raw.jsonl"), "w")
    print(f"{len(tasks)} tasks x {len(a.models)} models x {a.rounds} rounds -> {out_dir}", flush=True)

    rows = []
    for rnd in range(1, a.rounds + 1):
        order = a.models if rnd % 2 else list(reversed(a.models))   # alternate who goes first
        for model in order:
            for t in tasks:
                d, secs = chat(model, t, seed=rnd)
                if "error" in d:
                    row = dict(round=rnd, model=model, task=t["id"], area=t["area"], passed=False,
                               detail=d["error"], flags=["API ERROR"], secs=round(secs, 1))
                else:
                    ch = d["choices"][0]; msg = ch["message"]
                    g = t["grade"]
                    passed, detail = (g(msg, sandbox=sandbox) if getattr(g, "needs_sandbox", False)
                                      else g(msg))
                    u = d.get("usage", {}); tm = d.get("timings", {})
                    row = dict(round=rnd, model=model, task=t["id"], area=t["area"],
                               passed=bool(passed), detail=detail,
                               flags=validity(msg, ch.get("finish_reason")),
                               secs=round(secs, 1), completion_tokens=u.get("completion_tokens"),
                               reasoning_chars=len(msg.get("reasoning_content") or ""),
                               tg=round(tm.get("predicted_per_second", 0), 1))
                    raw.write(json.dumps({**row, "content": msg.get("content"),
                                          "tool_calls": msg.get("tool_calls"),
                                          "reasoning": msg.get("reasoning_content")},
                                         ensure_ascii=False) + "\n"); raw.flush()
                rows.append(row)
                mark = "PASS" if row["passed"] else "FAIL"
                print(f"  r{rnd} {model:<12} {t['id']:<17} {mark}  {row['secs']:6.1f}s "
                      f"{row.get('completion_tokens') or 0:5d}tok  {row['detail'][:70]}"
                      + (f"  !! {row['flags']}" if row["flags"] else ""), flush=True)

    json.dump(rows, open(os.path.join(out_dir, "graded.json"), "w"), indent=2)
    print("\n=== pass rate by model (all rounds) ===")
    for m in a.models:
        r = [x for x in rows if x["model"] == m]
        p = sum(x["passed"] for x in r)
        print(f"  {m:<12} {p}/{len(r)}  ({100*p/max(1,len(r)):.0f}%)   "
              f"median time {sorted(x['secs'] for x in r)[len(r)//2]:.0f}s   "
              f"flags: {sum(bool(x['flags']) for x in r)}")
    print(f"\n  -> {out_dir}")


if __name__ == "__main__":
    main()
