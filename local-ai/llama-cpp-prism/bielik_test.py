#!/usr/bin/env python3
"""Standalone test of Bielik-11B-v3.0-Instruct (Q8_0) on the PrismML llama.cpp fork.

Not a comparison with Qwen/Bonsai -- Bielik is for Polish-language work, so it is
judged on its own: does it run, how fast, and what its Polish looks like.

  - loads at its full native context (32768), q8_0 KV, parallel 1
  - speed: decode on chat prompts; prefill at ~8K and near the 32K limit
  - Polish samples through the model's own chat template, written to a markdown file
    for a human to judge (no automated quality score -- that would be made up)
"""
import json, os, statistics, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ab  # Server + memory/log parsing

MODEL = os.path.join(HERE, "models", "Bielik-11B-v3.0-Instruct.Q8_0.gguf")
ab.COMMON = ["-c", "32768", "--parallel", "1", "-ngl", "999", "-ctk", "q8_0", "-ctv", "q8_0",
             "-fa", "on", "--jinja", "--metrics", "-lv", "5"]

SYSTEM = "Jesteś pomocnym asystentem. Odpowiadasz po polsku, rzeczowo i poprawnie językowo."
SAMPLES = [
    ("wyjaśnienie",
     "Wyjaśnij prostym językiem, czym jest inflacja i jak podwyżka stóp procentowych "
     "przez NBP ma ją ograniczać."),
    ("korekta",
     "Popraw błędy językowe w tym tekście i krótko wyjaśnij każdą poprawkę: "
     "\"Wogóle nie wiem dla czego on to zrobił, bo przecież mówiłem mu żeby tego nie "
     "robić. Poszłem do sklepu i kupiłem dwa kilo jabłków, ale okazało się że one są "
     "niedobre.\""),
    ("e-mail formalny",
     "Napisz krótki, formalny e-mail do dostawcy z prośbą o przesunięcie terminu "
     "dostawy o dwa tygodnie z powodu opóźnień w naszym magazynie."),
    ("tłumaczenie EN→PL",
     "Przetłumacz na naturalny polski: \"The deployment pipeline failed because the "
     "container image was built against an outdated base layer, so we rolled back and "
     "pinned the dependency until the upstream fix lands.\""),
    ("streszczenie",
     "Streść w trzech zdaniach: Konstytucja 3 maja, uchwalona w 1791 roku, była pierwszą "
     "w Europie i drugą na świecie nowoczesną, spisaną konstytucją. Wprowadzała "
     "trójpodział władzy, znosiła liberum veto i ograniczała przywileje magnaterii. "
     "Obowiązywała jednak krótko, ponieważ jej przeciwnicy zawiązali konfederację "
     "targowicką, a interwencja Rosji doprowadziła do drugiego rozbioru Polski."),
    ("wiedza (sprawdź fakty!)",
     "Jakie są obecnie podstawowe stawki VAT w Polsce i do jakich kategorii towarów lub "
     "usług się odnoszą?"),
]

FILLER = ("Rada nadzorcza spółki zebrała się w celu omówienia wyników kwartalnych, "
          "planów inwestycyjnych oraz zmian w strukturze zatrudnienia w oddziałach "
          "regionalnych. ")


def chat(srv, user, max_tokens=700):
    body = json.dumps({"messages": [{"role": "system", "content": SYSTEM},
                                    {"role": "user", "content": user}],
                       "max_tokens": max_tokens, "temperature": 0.1, "seed": 1234}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{srv.port}/v1/chat/completions",
                                 data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.loads(r.read())


def tokens(srv, text):
    req = urllib.request.Request(f"http://127.0.0.1:{srv.port}/tokenize",
                                 data=json.dumps({"content": text}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return len(json.loads(r.read())["tokens"])


def main():
    if not os.path.exists(MODEL):
        sys.exit(f"missing {MODEL} - run ./download_models.sh bielik")
    if os.system("ps -axo comm= | grep -q 'llama-server$'") == 0:
        sys.exit("another llama-server is running - stop it first")

    srv = ab.Server("bielik-11b-q8", ab.PRISM_SERVER, MODEL)
    srv.start()
    try:
        mem = srv.memory()
        print(f"loaded in {srv.load_s:.1f}s  n_ctx {mem['n_ctx']}  rss {mem['rss_gib']:.2f} GiB  "
              f"gpu-weights {mem['gpu_weights_mib']/1024:.2f}  cpu-weights "
              f"{mem['cpu_weights_mib']/1024:.2f}  kv {mem['kv_mib']/1024:.2f} GiB", flush=True)
        chat(srv, "Cześć!", 8)  # warm up

        # --- Polish samples + decode speed --------------------------------------
        rows, tg = [], []
        for name, prompt in SAMPLES:
            r = chat(srv, prompt)
            t = r.get("timings", {})
            text = r["choices"][0]["message"].get("content") or ""
            tg.append(t.get("predicted_per_second", 0))
            rows.append((name, prompt, text, t))
            print(f"  {name:<22} {t.get('predicted_n', 0):4d} tok  "
                  f"{t.get('predicted_per_second', 0):6.2f} tok/s  "
                  f"finish={r['choices'][0].get('finish_reason')}", flush=True)

        # --- prefill at depth ----------------------------------------------------
        unit = tokens(srv, FILLER)
        depth = {}
        for target in (8000, 30000):
            text = FILLER * max(1, target // unit)
            r = srv.complete(text + "\n\nPodsumuj powyższy tekst jednym zdaniem.\n", 64)
            t = r["timings"]
            depth[target] = t
            print(f"  prefill ~{target//1000}K: {t['prompt_n']} tok at "
                  f"{t['prompt_per_second']:.0f} tok/s, then decode "
                  f"{t['predicted_per_second']:.2f} tok/s", flush=True)
    finally:
        srv.stop()

    stamp = time.strftime("%Y%m%d-%H%M%S")
    md = os.path.join(HERE, "results", f"bielik-samples-{stamp}.md")
    with open(md, "w") as f:
        f.write(f"# Bielik-11B-v3.0-Instruct Q8_0 — Polish samples ({stamp})\n\n")
        f.write(f"PrismML fork b10735, ctx 32768, q8_0 KV, temperature 0.1, seed 1234.\n"
                f"System prompt: *{SYSTEM}*\n\n")
        f.write(f"Median decode: **{statistics.median(tg):.2f} tok/s**. "
                + " · ".join(f"prefill @{d['prompt_n']} tok: {d['prompt_per_second']:.0f} tok/s"
                             for d in depth.values()) + "\n\n")
        for name, prompt, text, t in rows:
            f.write(f"## {name}\n\n**Prompt:** {prompt}\n\n{text}\n\n"
                    f"*{t.get('predicted_n', 0)} tokens, "
                    f"{t.get('predicted_per_second', 0):.2f} tok/s*\n\n---\n\n")
    print(f"\n  median decode {statistics.median(tg):.2f} tok/s")
    print(f"  samples -> {md}")
    json.dump({"memory": mem, "samples": [(n, p, x, t) for n, p, x, t in rows],
               "depth": depth}, open(md.replace(".md", ".json"), "w"), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
