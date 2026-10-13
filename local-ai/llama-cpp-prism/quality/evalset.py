"""Quality eval set: Qwen3.8 27B vs Ternary Bonsai 2 27B.

Every task but one is graded by CODE, not by opinion:
  - math/reasoning: ground truth is COMPUTED here (simulation, itertools, datetime),
    never hand-typed; the logic puzzle's uniqueness is brute-forced at import time
  - code: model output is executed against test suites in a no-network Docker sandbox
  - structured / tool calls / instruction following: parsed and checked field by field
The one subjective task (idempotency explainer) only gets an automatic word-limit check;
its content is rubric-graded by hand and reported as such.

Each task: dict(id, area, messages, [tools], grade(msg) -> (passed: bool, detail: str)).
`msg` is the OpenAI-style assistant message: content, reasoning_content, tool_calls.
"""
import datetime as dt
import itertools
import json
import math
import random
import re

ANS = "\n\nEnd your reply with the final answer on its own line in exactly this form:\nANSWER: <answer>"


def answer_line(text):
    m = re.findall(r"^\s*\**ANSWER\**\s*:\s*(.+?)\s*$", text or "", re.M | re.I)
    return m[-1].strip().strip("*`").strip() if m else None


def num(s):
    if s is None:
        return None
    m = re.search(r"-?\d[\d,\s]*\.?\d*", s.replace("−", "-"))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "").replace(" ", ""))
    except ValueError:
        return None


# ------------------------------------------------------------------ ground truths
def _m1_truth():
    """Crates ship at the END of each full hour; rate decided by the day the hour starts in."""
    t = dt.datetime(2026, 9, 25, 9, 0)  # a Friday
    assert t.strftime("%A") == "Friday"
    total = 0
    while total < 300:
        rate = 5 if t.weekday() >= 5 else 3
        t += dt.timedelta(hours=1)
        total += rate
    return t.strftime("%A"), t.strftime("%H:%M")


M1_DAY, M1_TIME = _m1_truth()
M2_TRUTH = round((1.20 * 0.75 * 1.10 * 0.92 - 1) * 100, 2)            # net % change
M3_TRUTH = math.factorial(11) // (math.factorial(4) ** 2 * math.factorial(2))  # MISSISSIPPI
M5_DATE = dt.date(2026, 1, 31) + dt.timedelta(days=150)
M6_TRUTH = 1.2e9 / (34 * 1024 ** 2)                                    # GB (10^9) / MiB/s


def _m4_solutions():
    people = ["Ada", "Ben", "Cy", "Dee", "Eli"]
    sols = []
    for perm in itertools.permutations(people):
        d = {p: i for i, p in enumerate(perm)}           # 0 = Monday
        if (d["Ada"] > d["Ben"] and d["Cy"] == 2 and d["Eli"] == d["Dee"] + 1
                and d["Ben"] != 0 and d["Eli"] < d["Ada"]):
            sols.append(list(perm))
    return sols


_M4 = _m4_solutions()
assert len(_M4) == 1, f"puzzle must have exactly one solution, has {len(_M4)}"
M4_TRUTH = _M4[0]


# ------------------------------------------------------------------ graders
def g_m1(msg):
    a = answer_line(msg["content"])
    if not a:
        return False, "no ANSWER line"
    ok = M1_DAY.lower() in a.lower() and M1_TIME in a.replace(".", ":")
    return ok, f"got {a!r}, want {M1_DAY} {M1_TIME}"


def g_m2(msg):
    a = answer_line(msg["content"]); v = num(a)
    ok = v is not None and abs(v - M2_TRUTH) <= 0.01
    return ok, f"got {a!r}, want {M2_TRUTH}%"


def g_m3(msg):
    a = answer_line(msg["content"]); v = num(a)
    return v == M3_TRUTH, f"got {a!r}, want {M3_TRUTH}"


def g_m4(msg):
    a = answer_line(msg["content"])
    if not a:
        return False, "no ANSWER line"
    names = re.findall(r"\b(Ada|Ben|Cy|Dee|Eli)\b", a)
    return names == M4_TRUTH, f"got {names}, want {M4_TRUTH}"


def g_m5(msg):
    a = answer_line(msg["content"])
    if not a:
        return False, "no ANSWER line"
    ok = M5_DATE.isoformat() in a and M5_DATE.strftime("%A").lower() in a.lower()
    return ok, f"got {a!r}, want {M5_DATE.isoformat()} {M5_DATE.strftime('%A')}"


def g_m6(msg):
    a = answer_line(msg["content"]); v = num(a)
    ok = v is not None and abs(v - M6_TRUTH) <= 0.06
    return ok, f"got {a!r}, want {M6_TRUTH:.2f}s (~{M6_TRUTH:.1f})"


# ------------------------------------------------------------------ code tasks
CODE_FMT = ("\n\nReturn only the complete function in a single ```python code block. "
            "Standard library only.")

C1_TESTS = """
from solution import merge_intervals as f
def n(x): return [list(i) for i in x]
T = [
  ([], []),
  ([[1,3],[2,6],[8,10],[15,18]], [[1,6],[8,10],[15,18]]),
  ([[1,4],[4,5]], [[1,5]]),
  ([[5,7],[1,2]], [[1,2],[5,7]]),
  ([[1,10],[2,3],[4,8]], [[1,10]]),
  ([[1,1]], [[1,1]]),
  ([[3,4],[1,2],[2,3]], [[1,4]]),
  ([[-5,-1],[-3,2],[10,11]], [[-5,2],[10,11]]),
]
"""

C2_TESTS = """
from solution import parse_duration as f
T = [("1h30m15s",5415),("45s",45),("2h",7200),("1h5s",3605),("90m",5400),("0s",0),("10h0m1s",36001)]
BAD = ["", "5x", "h1", "1h1h", "30s1m", "1.5h", " 1h", "1h ", "-1s", "1H"]
"""

C3_BUGGY = '''def rolling_max(values, k):
    """Return the maximum of every window of k consecutive values.

    rolling_max([1, 3, 2, 5, 4], 2) == [3, 3, 5, 5]
    Raises ValueError if k < 1 or k > len(values).
    """
    if k <= 0 or k > len(values):
        raise ValueError("bad k")
    out = []
    for i in range(len(values) - k):
        out.append(max(values[i:i + k]))
    return out'''

C3_TESTS = """
from solution import rolling_max as f
T = [(([1,3,2,5,4],2),[3,3,5,5]), (([1,3,2,5,4],1),[1,3,2,5,4]), (([1,3,2,5,4],5),[5]),
     (([4,4,4],2),[4,4]), (([-1,-3,-2],2),[-1,-2]), (([7],1),[7]), (([2,9,1,8,3,7],3),[9,9,8,8])]
BAD = [([1,2],0), ([1,2],3), ([],1), ([1],-1)]
"""


def _code_grade(tests, mode):
    def grade(msg, sandbox=None):
        blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", msg["content"] or "", re.S)
        if not blocks:
            return False, "no python code block"
        return sandbox(blocks[-1], tests, mode)
    grade.needs_sandbox = True
    return grade


# ------------------------------------------------------------------ structured / tools
INVOICE = ("INVOICE FV/2026/09/0412, issued 12 September 2026 by Nordwind Logistics Sp. z o.o. "
           "to Maslanka IO. Items: 3 x pallet storage (one month) at 180.00 PLN each; "
           "1 x customs handling at 450.00 PLN; 2 x express courier at 75.50 PLN each. "
           "Net total 1,141.00 PLN. VAT 23%. Gross total 1,403.43 PLN. "
           "Payment due 26 September 2026.")
S1_SCHEMA = ('{"invoice_number": string, "issue_date": "YYYY-MM-DD", "due_date": "YYYY-MM-DD", '
             '"vendor": string, "currency": ISO 4217 code, "vat_rate_percent": number, '
             '"net_total": number, "gross_total": number, '
             '"line_items": [{"description": string, "quantity": integer, "unit_price": number}]}')


def g_s1(msg):
    txt = (msg["content"] or "").strip()
    txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt, flags=re.S).strip()
    try:
        d = json.loads(txt)
    except Exception as e:
        return False, f"not valid JSON: {e}"
    checks = {
        "invoice_number": d.get("invoice_number") == "FV/2026/09/0412",
        "issue_date": d.get("issue_date") == "2026-09-12",
        "due_date": d.get("due_date") == "2026-09-26",
        "vendor": "nordwind" in str(d.get("vendor", "")).lower(),
        "currency": d.get("currency") == "PLN",
        "vat": d.get("vat_rate_percent") in (23, 23.0),
        "net": d.get("net_total") in (1141, 1141.0),
        "gross": d.get("gross_total") == 1403.43,
    }
    items = d.get("line_items") or []
    want = [(3, 180.0, "pallet"), (1, 450.0, "customs"), (2, 75.5, "courier")]
    got = sorted([(i.get("quantity"), float(i.get("unit_price", -1)),
                   str(i.get("description", "")).lower()) for i in items if isinstance(i, dict)],
                 key=lambda x: x[1])
    checks["line_items"] = len(got) == 3 and all(
        g[0] == w[0] and g[1] == w[1] and w[2] in g[2]
        for g, w in zip(got, sorted(want, key=lambda x: x[1])))
    bad = [k for k, v in checks.items() if not v]
    return not bad, "all fields correct" if not bad else f"wrong: {bad}"


TOOLS = [
    {"type": "function", "function": {
        "name": "get_weather", "description": "Current weather for a city.",
        "parameters": {"type": "object", "properties": {
            "city": {"type": "string"},
            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}},
            "required": ["city", "unit"]}}},
    {"type": "function", "function": {
        "name": "convert_currency", "description": "Convert an amount between currencies.",
        "parameters": {"type": "object", "properties": {
            "amount": {"type": "number"},
            "from_currency": {"type": "string", "description": "ISO 4217 code"},
            "to_currency": {"type": "string", "description": "ISO 4217 code"}},
            "required": ["amount", "from_currency", "to_currency"]}}},
]


def _calls(msg):
    out = []
    for c in msg.get("tool_calls") or []:
        f = c.get("function", {})
        try:
            args = json.loads(f.get("arguments") or "{}")
        except Exception:
            args = "MALFORMED:" + str(f.get("arguments"))[:60]
        out.append((f.get("name"), args))
    return out


def g_s2(msg):
    calls = _calls(msg)
    if len(calls) != 1:
        return False, f"want 1 call, got {calls}"
    name, a = calls[0]
    ok = (name == "convert_currency" and isinstance(a, dict) and a.get("amount") in (250, 250.0)
          and str(a.get("from_currency", "")).upper() == "EUR"
          and str(a.get("to_currency", "")).upper() == "PLN")
    return ok, f"got {calls}"


def g_s3(msg):
    calls = _calls(msg)
    def norm(s): return str(s).lower().replace("ń", "n")
    cities = sorted(norm(a.get("city")) for n, a in calls
                    if n == "get_weather" and isinstance(a, dict) and a.get("unit") == "celsius")
    ok = len(calls) == 2 and cities == ["gdansk", "warsaw"]
    return ok, f"got {calls}"


# ------------------------------------------------------------------ instruction following
def g_i1(msg):
    lines = [l for l in (msg["content"] or "").strip().splitlines() if l.strip()]
    bul = [l for l in lines if l.startswith("- ")]
    wc = [len(l[2:].split()) for l in bul]
    probs = []
    if len(lines) != 4 or len(bul) != 4:
        probs.append(f"{len(bul)} bullets / {len(lines)} lines")
    if any(not 6 <= w <= 12 for w in wc):
        probs.append(f"word counts {wc}")
    if "q" in (msg["content"] or "").lower():
        probs.append("contains 'q'")
    return not probs, "ok" if not probs else "; ".join(probs)


PL_STOP = {"i", "w", "na", "się", "jest", "to", "że", "nie", "do", "z", "oraz", "dla", "ponieważ", "są"}
EN_STOP = {"the", "and", "is", "are", "of", "to", "because", "with", "for"}


PL_DIACRITIC = re.compile(r"[ąćęłńóśźż]")


def g_i2(msg):
    # v2 (2026-09-25): v1 required >=3 hits from a short stopword list and falsely failed
    # correct Polish that happened to use few of them. Diacritic-bearing words are a far
    # stronger Polish signal; English leakage is still checked separately.
    t = (msg["content"] or "").strip()
    sents = [s for s in re.split(r"(?<=[.!?])\s+", t) if s.strip()]
    words = re.findall(r"\w+", t.lower())
    pl = sum(w in PL_STOP for w in words) + sum(bool(PL_DIACRITIC.search(w)) for w in words)
    en = sum(w in EN_STOP for w in words)
    probs = []
    if len(sents) != 2: probs.append(f"{len(sents)} sentences")
    if "izolacj" not in t.lower(): probs.append("missing 'izolacja'")
    if pl < 3 or en > 1: probs.append(f"language check pl={pl} en={en}")
    return not probs, "ok" if not probs else "; ".join(probs)


# ------------------------------------------------------------------ long context
def _haystack(n_sentences=4200, seed=7):
    r = random.Random(seed)
    adj = ["quiet", "northern", "regional", "legacy", "primary", "shared", "temporary", "annual"]
    noun = ["team", "warehouse", "committee", "service", "pipeline", "office", "archive", "fleet"]
    verb = ["reviewed", "migrated", "audited", "scheduled", "rebuilt", "documented", "paused"]
    obj = ["the backlog", "the budget", "the rollout", "the inventory", "the contract",
           "the roadmap", "the incident report", "the vendor list"]
    when = ["on Monday", "last quarter", "before the audit", "after lunch", "in March",
            "during the freeze", "this week"]
    s = [f"The {r.choice(adj)} {r.choice(noun)} {r.choice(verb)} {r.choice(obj)} {r.choice(when)}."
         for _ in range(n_sentences)]
    s[int(n_sentences * 0.15)] = "For reference, the override code for the Lisbon cluster is TIDE-2290-HERON."
    s[int(n_sentences * 0.42)] = ("Note for the auditors: the override code for the Dublin cluster "
                                   "is RIVER-4417-KESTREL.")
    s[int(n_sentences * 0.71)] = "The Dublin office phone extension was changed to 5518 in June."
    return " ".join(s)


def g_l1(msg):
    a = answer_line(msg["content"]) or ""
    return "RIVER-4417-KESTREL" in a.upper(), f"got {a!r}"


# ------------------------------------------------------------------ subjective
def g_q1(msg):
    n = len((msg["content"] or "").split())
    return n <= 250, f"{n} words (limit 250); content graded by rubric"


# ------------------------------------------------------------------ the set
def u(text):
    return [{"role": "user", "content": text}]


TASKS = [
    dict(id="M1-schedule", area="reasoning", grade=g_m1, messages=u(
        "A warehouse ships crates at the END of every full hour. The number shipped in an hour "
        "depends on the day that hour STARTS in: 3 crates per hour Monday-Friday, 5 crates per "
        "hour on Saturday and Sunday. Counting starts on a Friday at 09:00 with 0 crates shipped. "
        "At what day and time does the cumulative total first reach at least 300 crates?"
        + ANS.replace("<answer>", "<weekday> <HH:MM>"))),
    dict(id="M2-percent", area="reasoning", grade=g_m2, messages=u(
        "A price rises 20%, then falls 25%, then rises 10%, then falls 8%. What is the total "
        "percentage change from the original price, to two decimal places?"
        + ANS.replace("<answer>", "<number>%"))),
    dict(id="M3-combinatorics", area="reasoning", grade=g_m3, messages=u(
        "How many distinct arrangements of the letters of the word MISSISSIPPI are there?" + ANS)),
    dict(id="M4-logic", area="reasoning", grade=g_m4, messages=u(
        "Five developers - Ada, Ben, Cy, Dee and Eli - each deploy exactly once, one per day, "
        "Monday to Friday. Ada deploys after Ben. Cy deploys on Wednesday. Dee deploys the day "
        "immediately before Eli. Ben does not deploy on Monday. Eli deploys before Ada. "
        "Who deploys on each day?"
        + ANS.replace("<answer>", "<names Monday to Friday, comma-separated>"))),
    dict(id="M5-dates", area="reasoning", grade=g_m5, messages=u(
        "What is the date 150 days after 31 January 2026, and what day of the week is it?"
        + ANS.replace("<answer>", "<YYYY-MM-DD> <weekday>"))),
    dict(id="M6-units", area="reasoning", grade=g_m6, messages=u(
        "A 1.2 GB file (1 GB = 10^9 bytes) downloads at a steady 34 MiB/s (1 MiB = 2^20 bytes). "
        "How many seconds does the download take, to one decimal place?"
        + ANS.replace("<answer>", "<seconds>"))),
    dict(id="C1-merge", area="code", grade=_code_grade(C1_TESTS, "eq"), messages=u(
        "Write a Python function merge_intervals(intervals) that takes a list of [start, end] "
        "integer pairs (start <= end, in any order) and returns a new list of merged, "
        "non-overlapping intervals sorted by start. Intervals that touch (e.g. [1,4] and [4,5]) "
        "must be merged." + CODE_FMT)),
    dict(id="C2-parse", area="code", grade=_code_grade(C2_TESTS, "eq+bad"), messages=u(
        "Write a Python function parse_duration(s) that converts strings like '1h30m15s', '45s', "
        "'2h' or '1h5s' into a total number of seconds (int). Rules: units are lowercase h, m, s; "
        "each appears at most once and in that order; each value is a non-negative integer; no "
        "spaces or other characters are allowed; the string must not be empty. Raise ValueError "
        "for anything invalid." + CODE_FMT)),
    dict(id="C3-debug", area="code", grade=_code_grade(C3_TESTS, "eq+bad"), messages=u(
        "This function has a bug. Find it and return the complete corrected function.\n\n"
        "```python\n" + C3_BUGGY + "\n```" + CODE_FMT)),
    dict(id="S1-invoice-json", area="structured", grade=g_s1, messages=u(
        "Extract the data from this invoice into JSON matching this schema exactly:\n"
        + S1_SCHEMA + "\n\nInvoice:\n" + INVOICE +
        "\n\nReply with the JSON object only - no prose, no code fences.")),
    dict(id="S2-tool-single", area="tools", grade=g_s2, tools=TOOLS, messages=u(
        "How much is 250 euro in Polish zloty?")),
    dict(id="S3-tool-parallel", area="tools", grade=g_s3, tools=TOOLS, messages=u(
        "What's the weather right now in Warsaw and in Gdansk? Use celsius.")),
    dict(id="I1-format", area="instructions", grade=g_i1, messages=u(
        "List exactly 4 benefits of unit testing. Rules: each line must start with '- ', each "
        "bullet must be 6 to 12 words long, do not use the letter q anywhere, and write nothing "
        "except the 4 bullets.")),
    # I2-polish removed 2026-09-25: Polish is out of scope for Qwen/Bonsai (that's Bielik's job)
    dict(id="L1-needle-60k", area="long-context", grade=g_l1, messages=u(
        _haystack() + "\n\nQuestion: according to the text above, what is the override code for "
        "the Dublin cluster?" + ANS.replace("<answer>", "<code>"))),
    dict(id="Q1-explain", area="subjective", grade=g_q1, messages=u(
        "Explain to a junior backend engineer what idempotency means for an HTTP API, why it "
        "matters for payment endpoints, and how to implement it with an Idempotency-Key header. "
        "Maximum 250 words.")),
]

RUBRIC_Q1 = [
    "defines idempotency correctly (same request repeated -> same effect/result, not 'no side effects')",
    "notes GET/PUT/DELETE are idempotent by HTTP semantics while POST is not",
    "payments: retries after timeouts/network errors must not double-charge",
    "key flow: client sends unique key; server stores key -> result; replays return the stored result",
    "covers an edge case: concurrent duplicates (lock/unique constraint), key expiry, or same key + different body",
    "accurate throughout (no wrong claims), clear, within 250 words",
]
