# Quality eval: Qwen3.8 27B vs Ternary Bonsai 2 27B (2026-09-25)

Router: PrismML llama.cpp fork, both models at ctx 262144, q8_0 KV, parallel 1.
Identical settings for both: temp 1.0, top_p 0.95, top_k 20, min_p 0.05, thinking on at
reasoning_effort=medium, max_tokens 8192. 2 rounds (seeds 1, 2), order alternated.
English only; the Polish task was dropped as out of scope for these models.

## Result

| area | Qwen3.8 27B | Bonsai 2 27B |
|---|---|---|
| reasoning (6 tasks) | 12/12 | 12/12 |
| code, sandbox-tested (3) | 6/6 | 6/6 |
| structured JSON (1) | 2/2 | 2/2 |
| tool calls, single + parallel (2) | 4/4 | 4/4 |
| instruction following (1) | 2/2 | 2/2 |
| long context, ~60K tokens (1) | 2/2 | 2/2 |
| explainer, word limit (1) | 1/2 | 2/2 |
| **total** | **29/30** | **30/30** |
| explainer content, rubric (hand-graded) | 11/12 | 11.5/12 |

No validity problems in any of 64 responses: 0 truncated, 0 empty, 0 looping.

Speed (long-context task excluded -- a round-2 prompt-cache hit skews it):
Bonsai median 35 s/task vs Qwen 66 s (1.9x); total 24.3 vs 34.3 min; decode 22.0 vs
12.5 tok/s. Thinking length is similar (median 762 vs 818 completion tokens), so Bonsai
is not getting its speed by reasoning less.

## Every failure and error, verified by hand

- **Qwen, Polish task, r1** -- grader bug (stopword threshold too strict for correct,
  fluent Polish). Grader fixed; task later dropped from scope. Re-grading all saved
  responses with the fixed graders changed 0 other verdicts.
- **Qwen, explainer, r2** -- genuine but trivial: 251 words excluding markdown symbols
  (256 raw) against a 250 limit. Content otherwise strong (best concurrency answer of the
  four: explicitly relies on SETNX / unique-index atomicity).
- **Bonsai, explainer, r1** -- passed the automatic check, but contains a real factual
  slip: "$49.99 becomes $149.88" (3 x 49.99 = 149.97). Docked 0.5 on the rubric.

## What this does and doesn't show

It rules out Bonsai being broken or noticeably worse on standard single-shot tasks --
including the two areas an independent review flagged (fixing a planted bug; tool calls).

It does NOT prove parity on hard work: both models scored ~100%, so the test is at its
ceiling and cannot separate them. Untested: multi-turn agentic tool loops (where
PrismML's own KNOWN_ISSUES reports malformed/looping tool calls), long debugging sessions,
competition-level reasoning.

Files: `raw.jsonl` (every response, including reasoning), `graded.json` (verdicts).
Harness: `quality/evalset.py` (tasks + graders), `quality/run.py`, `quality/regrade.py`.
