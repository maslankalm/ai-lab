#!/usr/bin/env python3
"""Re-grade saved responses (raw.jsonl) with the CURRENT graders -- no model calls.

Used when a grader is found to be wrong mid-run: the fix is applied to every saved
response from every model, so no model gets a correction the other didn't.

  python3 quality/regrade.py results/quality-<stamp>
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import evalset as E   # noqa: E402
import run            # noqa: E402  (sandbox)

d = sys.argv[1]
tasks = {t["id"]: t for t in E.TASKS}
rows, changed = [], []
for line in open(os.path.join(d, "raw.jsonl")):
    r = json.loads(line)
    if r["task"] not in tasks:          # task dropped from the set -> excluded from scoring
        continue
    msg = {"content": r["content"], "tool_calls": r["tool_calls"]}
    g = tasks[r["task"]]["grade"]
    ok, detail = (g(msg, sandbox=run.sandbox) if getattr(g, "needs_sandbox", False) else g(msg))
    if bool(ok) != r["passed"]:
        changed.append(f"  {r['model']:<12} r{r['round']} {r['task']:<17} "
                       f"{'FAIL->PASS' if ok else 'PASS->FAIL'}  ({r['detail']} -> {detail})")
    r.update(passed=bool(ok), detail=detail)
    rows.append({k: v for k, v in r.items() if k not in ("content", "tool_calls", "reasoning")})
json.dump(rows, open(os.path.join(d, "graded.json"), "w"), indent=2)
print(f"re-graded {len(rows)} responses; {len(changed)} verdicts changed")
print("\n".join(changed) if changed else "  (none)")
