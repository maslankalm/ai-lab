#!/usr/bin/env python3
"""Head-to-head: Qwen3.8-27B UD-Q4_K_XL vs Ternary Bonsai 2 27B (PTQ1_0 and PQ2_0),
all on the PrismML llama.cpp fork, on this Mac. Stdlib only.

Same server settings for every config: -c 262144 --parallel 1 -ngl 999, q8_0 KV,
flash attention on, no speculation. Configs are INTERLEAVED within each round, because
absolute tok/s on this machine drifts with thermal state (see ../llm-bench/README.md).

Workload is raw /completion (no chat template, so no thinking), greedy, fixed lengths:
tokens are tokens, so this measures the engine, not reasoning verbosity.

This measures speed and memory only. It does NOT measure answer quality.

Sanity checks, because a fast broken model is worthless:
  - coherence: output must look like text (a misapplied Hadamard runtime yields garbage)
  - CPU fallback: a multi-GB "CPU model buffer" means the GPU is silently not being used
  - PTQ1_0 vs PQ2_0 greedy output compared (PrismML claims the repack is lossless)
"""
import argparse, json, os, re, signal, socket, statistics, subprocess, sys, time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PRISM_SERVER = os.path.join(HERE, "bin", "current", "llama-server")
QWEN_GGUF = os.path.join(HERE, "models", "Qwen3.8-27B-UD-Q4_K_XL.gguf")

CONFIGS = {
    # The original run also had Unsloth's stock llama.cpp build as a baseline (results in README.md).
    "qwen38-prism": (PRISM_SERVER, QWEN_GGUF),
    # bonsai2-ptq1 (PTQ1_0, same weights) was dropped: ~14% slower than PQ2_0 on Metal.
    "bonsai2-pq2":  (PRISM_SERVER, os.path.join(HERE, "models", "Ternary-Bonsai-2-27B-PQ2_0.gguf")),
}
COMMON = ["-c", "262144", "--parallel", "1", "-ngl", "999",
          "-ctk", "q8_0", "-ctv", "q8_0", "-fa", "on", "--metrics", "-lv", "5"]

PROMPTS = {
    "prose": ("Write a detailed technical explanation of how a write-ahead log guarantees "
              "durability in a relational database. Cover checkpointing, group commit, "
              "and crash recovery.\n\n", 512),
    "code":  ("Write a complete, well-commented Python implementation of a thread-safe LRU "
              "cache with TTL expiry, including a test suite.\n\n```python\n", 512),
}
DEEP_UNIT = ("The quick brown fox jumps over the lazy dog while the system processes another "
             "batch of records from the write-ahead log. ")
DEEP = (DEEP_UNIT * 330 + "\n\nSummarise the passage above in detail.\n\n", 256)  # ~8K tokens


def free_port(start=8900):
    for p in range(start, start + 50):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p)); return p
            except OSError:
                pass
    raise RuntimeError("no free port")


class Server:
    def __init__(self, name, binary, model):
        self.name, self.binary, self.model = name, binary, model
        self.port = free_port()
        self.log_path = os.path.join(HERE, "logs", f"{name}-{int(time.time())}.log")

    def start(self, timeout=600):
        self.fh = open(self.log_path, "w")
        cmd = [self.binary, "-m", self.model, "--host", "127.0.0.1",
               "--port", str(self.port)] + COMMON
        t0 = time.time()
        self.proc = subprocess.Popen(cmd, stdout=self.fh, stderr=subprocess.STDOUT,
                                     preexec_fn=os.setsid)
        while time.time() - t0 < timeout:
            if self.proc.poll() is not None:
                raise RuntimeError(f"{self.name} exited rc={self.proc.returncode}:\n"
                                   + self.tail(25))
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health",
                                            timeout=2) as r:
                    if r.status == 200:
                        self.load_s = time.time() - t0
                        return self
            except Exception:
                time.sleep(1)
        self.stop(); raise TimeoutError(f"{self.name} not healthy in {timeout}s")

    def log(self):
        self.fh.flush()
        return open(self.log_path, errors="replace").read()

    def tail(self, n):
        return "\n".join(self.log().splitlines()[-n:])

    def memory(self):
        L = self.log()
        def s(p):
            v = [float(x) for x in re.findall(p, L)]
            return sum(v) if v else 0.0
        comp = [float(x) for x in re.findall(r"compute buffer size\s*=\s*([\d.]+) MiB", L)]
        rss = subprocess.run(["ps", "-o", "rss=", "-p", str(self.proc.pid)],
                             capture_output=True, text=True).stdout.strip()
        tensor = re.search(r"has tensor\s*=\s*(\w+)", L)
        return {
            # weights: mmap'd (_Mapped) or copied onto the device
            "gpu_weights_mib": s(r"MTL\d*(?:_Mapped)? model buffer size\s*=\s*([\d.]+) MiB"),
            # KNOWN_ISSUES tell for silent CPU fallback: several GB here
            "cpu_weights_mib": s(r"CPU(?:_Mapped)? model buffer size\s*=\s*([\d.]+) MiB"),
            "kv_mib": s(r"KV buffer size\s*=\s*([\d.]+) MiB"),
            "ssm_mib": s(r"RS buffer size\s*=\s*([\d.]+) MiB"),
            "compute_mib": max(comp) if comp else 0.0,
            "rss_gib": int(rss) / 1024 / 1024 if rss.isdigit() else 0.0,
            "tensor_api": tensor.group(1) if tensor else "?",
            "spec": [l.strip()[-100:] for l in L.splitlines() if " spec " in l][:2],
            "n_ctx": (re.search(r"n_ctx_slot\s*=\s*(\d+)", L) or [None, "?"])[1],
        }

    def complete(self, prompt, n):
        body = json.dumps({"prompt": prompt, "n_predict": n, "temperature": 0.0,
                           "top_k": 1, "seed": 1234, "cache_prompt": False}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/completion", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=1800) as r:
            return json.loads(r.read())

    def stop(self):
        if getattr(self, "proc", None) and self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM); self.proc.wait(30)
            except Exception:
                try: os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
                except Exception: pass
        try: self.fh.close()
        except Exception: pass


def coherent(text):
    """Cheap garbage detector: real prose/code is mostly letters, spaces, punctuation,
    and doesn't repeat one short token forever."""
    if len(text) < 40:
        return False
    ok = sum(c.isalnum() or c.isspace() or c in ".,;:()[]{}'\"-_=+*/#<>!?`\n" for c in text)
    words = text.split()
    distinct = len(set(words)) / max(1, len(words))
    return ok / len(text) > 0.9 and distinct > 0.2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--configs", nargs="+", default=list(CONFIGS))
    a = ap.parse_args()

    for n in a.configs:
        b, m = CONFIGS[n]
        missing = [p for p in (b, m) if not p or not os.path.exists(p)]
        if missing:
            sys.exit(f"{n}: missing {missing}")
    if subprocess.run("ps -axo comm= | grep -q 'llama-server$'", shell=True).returncode == 0:
        sys.exit("another llama-server is running (./run.sh router?) - stop it first; "
                 "two 27B models won't fit in the 37 GiB Metal budget")

    cases = dict(PROMPTS); cases["deep"] = DEEP
    samples = {n: {c: [] for c in cases} for n in a.configs}
    pp = {n: [] for n in a.configs}
    mem, texts, flags = {}, {n: {} for n in a.configs}, []

    print(f"interleaved: {a.rounds} rounds x {len(a.configs)} configs, ctx 262144, "
          f"q8_0 KV, parallel 1, greedy\n", flush=True)
    for rnd in range(1, a.rounds + 1):
        for n in a.configs:
            srv = Server(n, *CONFIGS[n])
            try:
                srv.start()
                srv.complete("Hello.", 8)                    # warm the graphs
                row = []
                for c, (prompt, npred) in cases.items():
                    r = srv.complete(prompt, npred)
                    t = r["timings"]
                    samples[n][c].append(t["predicted_per_second"])
                    if c == "deep":
                        pp[n].append(t["prompt_per_second"])
                    texts[n].setdefault(c, r["content"])
                    row.append(f"{c} {t['predicted_per_second']:5.2f}")
                    if c == "deep":
                        row[-1] += f" (pp {t['prompt_per_second']:.0f}, {t['prompt_n']} tok)"
                if n not in mem:
                    mem[n] = srv.memory(); mem[n]["load_s"] = round(srv.load_s, 1)
                print(f"  r{rnd} {n:<13} " + " | ".join(row), flush=True)
            except Exception as e:
                print(f"  r{rnd} {n:<13} FAILED: {e}", flush=True)
                flags.append(f"{n} failed in round {rnd}")
            finally:
                srv.stop()

    print("\n=== decode tok/s (median) ===")
    base = "qwen38-q4kxl" if "qwen38-q4kxl" in a.configs else a.configs[0]
    hdr = f"  {'config':<13} " + " ".join(f"{c:>13}" for c in cases) + f" {'pp@8K':>8}"
    print(hdr)
    for n in a.configs:
        cells = []
        for c in cases:
            v = samples[n][c]
            if not v: cells.append(f"{'-':>13}"); continue
            m = statistics.median(v)
            bm = statistics.median(samples[base][c]) if samples[base][c] else None
            cells.append(f"{m:6.2f} ({m/bm:4.2f}x)" if bm else f"{m:13.2f}")
        ppm = f"{statistics.median(pp[n]):8.0f}" if pp[n] else f"{'-':>8}"
        print(f"  {n:<13} " + " ".join(cells) + " " + ppm)

    # engine effect: same Qwen file, Unsloth build vs PrismML fork
    # model effect: same PrismML fork, Qwen vs Bonsai
    def med(n, c):
        return statistics.median(samples[n][c]) if samples.get(n, {}).get(c) else None
    if "qwen38-q4kxl" in a.configs and "qwen38-prism" in a.configs:
        print("\n=== engine effect (Qwen on fork / Qwen on Unsloth) ===")
        for c in cases:
            x, y = med("qwen38-prism", c), med("qwen38-q4kxl", c)
            if x and y: print(f"  {c:<6} {x/y:5.2f}x")
    if "qwen38-prism" in a.configs:
        print("\n=== model effect, same engine (Bonsai on fork / Qwen on fork) ===")
        for n in ("bonsai2-ptq1", "bonsai2-pq2"):
            if n not in a.configs: continue
            for c in cases:
                x, y = med(n, c), med("qwen38-prism", c)
                if x and y: print(f"  {n:<13} {c:<6} {x/y:5.2f}x")

    print("\n=== memory & sanity ===")
    for n, m in mem.items():
        print(f"  {n:<13} load {m['load_s']}s  rss {m['rss_gib']:.2f} GiB  "
              f"gpu-weights {m['gpu_weights_mib']/1024:.2f}  cpu-weights "
              f"{m['cpu_weights_mib']/1024:.2f}  kv {m['kv_mib']/1024:.2f}  "
              f"compute {m['compute_mib']/1024:.2f} GiB  n_ctx {m['n_ctx']}  "
              f"tensor-api {m['tensor_api']}")
        if m["cpu_weights_mib"] > 2048:
            flags.append(f"{n}: {m['cpu_weights_mib']/1024:.1f} GiB of weights on CPU "
                         "-> likely silent CPU fallback")
        for l in m["spec"]:
            print(f"      spec: {l}")
    for n in a.configs:
        for c, t in texts[n].items():
            if not coherent(t):
                flags.append(f"{n}/{c}: output looks like garbage: {t[:80]!r}")
    if "bonsai2-ptq1" in texts and "bonsai2-pq2" in texts:
        for c in cases:
            x, y = texts["bonsai2-ptq1"].get(c), texts["bonsai2-pq2"].get(c)
            if x is None or y is None: continue
            same = x == y
            if not same:
                k = next((i for i, (p, q) in enumerate(zip(x, y)) if p != q), min(len(x), len(y)))
            print(f"  PTQ1_0 vs PQ2_0 greedy [{c}]: "
                  + ("identical" if same else f"DIFFER at char {k}"))

    print("\n=== output samples (first 160 chars) ===")
    for n in a.configs:
        for c in ("prose", "code"):
            t = texts[n].get(c, "")
            print(f"  {n}/{c}: {t[:160]!r}")

    print("\n=== flags ===")
    print("  none" if not flags else "\n".join(f"  ! {f}" for f in flags))

    out = os.path.join(HERE, "results", f"ab-{time.strftime('%Y%m%d-%H%M%S')}.json")
    with open(out, "w") as f:
        json.dump({"samples": samples, "pp": pp, "memory": mem, "texts": texts,
                   "flags": flags, "common_args": COMMON,
                   "configs": {n: CONFIGS[n] for n in a.configs}}, f, indent=2)
    print(f"\n  -> {out}")


if __name__ == "__main__":
    main()
