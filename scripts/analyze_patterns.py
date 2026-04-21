#!/usr/bin/env python3
"""Summary statistics for the 3-agent × 62-task evaluation."""
import csv
from collections import Counter, defaultdict

CSV_PATH = "/Users/zihanwu/Public/codes/huawei-eval/reports/eval_scores_v2_wide.csv"

SUBJECTS = ["claude-opus-max", "codex-gpt-5_4", "cursor-composer2", "opencode-glm51"]
EVALUATORS = ["claude", "codex", "cursor", "glm"]

HW_LOW = {"C1", "C2", "M1", "K1"}
HW_MED = {"C3", "C4", "M2", "K2", "K3"}
HW_HIGH = {"C5", "M3", "K4"}

def tier(task):
    if task in HW_LOW: return "Low"
    if task in HW_MED: return "Med"
    if task in HW_HIGH: return "High"
    return None


def majority(row, evaluators=("claude","codex","cursor","glm")):
    """Return (verdict, n_votes) or (None, 0)."""
    votes = []
    for ev in evaluators:
        v = row.get(f"{ev}_verdict", "").strip().upper()
        if v in {"PASS","PARTIAL","FAIL"}:
            votes.append(v)
    if not votes:
        return None
    # majority; break ties toward lower
    from collections import Counter
    cnt = Counter(votes)
    m = cnt.most_common()
    top_count = m[0][1]
    top_verdicts = [v for v,n in m if n == top_count]
    order = {"FAIL":0,"PARTIAL":1,"PASS":2}
    return sorted(top_verdicts, key=lambda v: order[v])[0]


def score_mean(row, evaluators=("claude","codex","cursor","glm")):
    vals = []
    for ev in evaluators:
        try:
            a = float(row[f"{ev}_A"])
            b = float(row[f"{ev}_B"])
            c = float(row[f"{ev}_C"])
            vals.append(a+b+c)
        except (ValueError, KeyError):
            pass
    return sum(vals)/len(vals) if vals else None


def load():
    import csv
    with open(CSV_PATH) as f:
        rows = [r for r in csv.DictReader(f) if r.get("agent") in SUBJECTS]
    for r in rows:
        r["_v"] = majority_verdict(r)
        r["_s"] = mean_score(r)
    return rows


def table_overall(rows):
    print("\n## Overall pass rate by agent (all 62 tasks × 2 prompts = 124 runs)\n")
    print(f"| Agent | N | PASS | PARTIAL | FAIL | Pass% | MeanScore |")
    print(f"| --- | --- | --- | --- | --- | --- | --- |")
    for a in SUBJECTS:
        sub = [r for r in rows if r["agent"] == a]
        n = len(sub)
        c = Counter(r["_v"] for r in sub)
        nP = c.get("PASS",0); nX = c.get("PARTIAL",0); nF = c.get("FAIL",0)
        scores = [r["_s"] for r in sub if r["_s"] is not None]
        ms = sum(scores)/len(scores) if scores else 0
        label = a if a != "claude-opus-max" else f"{a} (refonly)"
        print(f"| {label} | {n} | {nP} | {nX} | {nF} | {100*nP/n:.1f}% | {ms:.2f} |")


def table_by_family(rows):
    print("\n## Per agent × task family\n")
    fams = [
        ("C (Huawei C++ / CANN)", lambda t: t.startswith("C")),
        ("M (MindSpeed)",        lambda t: t.startswith("M")),
        ("K (Kubernetes)",       lambda t: t.startswith("K")),
        ("T (CapBench OSS)",     lambda t: t.startswith("T")),
    ]
    for label, pred in families:
        print(f"\n### {label}")
        print("| Agent | N | PASS | PARTIAL | FAIL | PASS% |")
        print("| --- | --- | --- | --- | --- | --- |")
        for a in SUBJECTS:
            sub = [r for r in rows if r["agent"] == a and pred(r["task"])]
            if not sub: continue
            n = len(sub)
            c = Counter(r["_m"] for r in sub)
            p = c.get("PASS",0); pa = c.get("PARTIAL",0); f = c.get("FAIL",0)
            print(f"| {a} | {n} | {p} | {pa} | {f} | {100*p/n:.1f}% |")
