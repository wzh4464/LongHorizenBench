#!/usr/bin/env python3
import csv, glob, os, sys
from collections import defaultdict
from statistics import mean, stdev
ROOT = "/Users/zihanwu/Public/codes/huawei-eval"
def args():
    p = o = None; it = iter(sys.argv[1:])
    for a in it:
        if a == "--csv": p = next(it, None)
        elif a == "--out": o = next(it, None)
    return p, o
def resolve(p):
    if p: return p
    for x in (ROOT + "/experiment_results_wide.csv", ROOT + "/reports/eval_results.csv"):
        if os.path.exists(x): return x
    hits = sorted({x for pat in (ROOT + "/**/*eval*.csv", ROOT + "/**/*results*.csv") for x in glob.glob(pat, recursive=True)})
    if not hits: raise SystemExit("No eval/results CSV found")
    return hits[0]
def val(row, h, *names):
    for n in names:
        c = h.get(n.lower())
        if c is not None: return (row.get(c) or "").strip()
    return ""
def num(x):
    try: return None if str(x).strip() == "" else float(x)
    except (TypeError, ValueError): return None
def add(row, h, recs, task, model, prompt, ev, verdict, pre=""):
    if not task or not model or str(verdict).strip() == "": return False
    scores = {s: num(val(row, h, *(([pre + "_" + s] if pre else []) + [s]))) for s in ("A", "B", "C")}
    keys = ([pre + "_composite", pre + "_score", pre + "_mean_score"] if pre else []) + ["composite", "score", "mean_score"]
    vals = [v for v in scores.values() if v is not None]; score = num(val(row, h, *keys))
    recs.append({"task": task, "model": model, "prompt": prompt, "evaluator": ev or "unknown", "verdict": str(verdict).strip(), "pass": str(verdict).strip().lower() in ("pass", "passed", "true", "1", "yes", "y"), "scores": scores, "score": score if score is not None else (mean(vals) if vals else None)})
    return True
def load(path):
    recs = []; skipped = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f); h = {x.lower(): x for x in (reader.fieldnames or [])}; wide = {}
        for low, orig in h.items():
            for suf in ("_verdict", "_passed", "_pass"):
                if low.endswith(suf) and low[:-len(suf)]: wide.setdefault(low[:-len(suf)], orig)
        for row in reader:
            task = val(row, h, "task", "task_id"); model = val(row, h, "model", "agent", "agent_config")
            prompt = val(row, h, "prompt", "prompt_type"); made = False
            if wide:
                for ev, col in sorted(wide.items()): made = add(row, h, recs, task, model, prompt, ev, row.get(col, ""), ev) or made
            else: made = add(row, h, recs, task, model, prompt, val(row, h, "evaluator", "judge"), val(row, h, "verdict", "passed", "pass"))
            skipped += 0 if made else 1
    return recs, skipped
def pct(n, d): return "-" if not d else f"{100 * n / d:.1f}%"
def render(path, recs, skipped):
    out = [f"Using CSV: {os.path.abspath(path)}", "", "## Overview", f"- total rows: {len(recs)}", f"- unique tasks: {len({r['task'] for r in recs})}", f"- unique models: {len({r['model'] for r in recs})}", f"- unique evaluators: {len({r['evaluator'] for r in recs})}", f"- unique (task, model, evaluator): {len({(r['task'], r['model'], r['evaluator']) for r in recs})}", "", "## Pass rate by model", "| model | n | pass% | avg_score |", "|---|---:|---:|---:|"]
    bym = defaultdict(list)
    for r in recs: bym[r["model"]].append(r)
    for m, rs in sorted(bym.items(), key=lambda kv: (-sum(r["pass"] for r in kv[1]) / len(kv[1]), kv[0])):
        sc = [r["score"] for r in rs if r["score"] is not None]; out.append(f"| {m} | {len(rs)} | {pct(sum(r['pass'] for r in rs), len(rs))} | {mean(sc):.2f} |" if sc else f"| {m} | {len(rs)} | {pct(sum(r['pass'] for r in rs), len(rs))} | - |")
    out += ["", "## Pass rate by task family", "| family | n | pass% |", "|---|---:|---:|"]; fam = defaultdict(list)
    for r in recs: fam[(r["task"][:1] or "?").upper()].append(r)
    for k in sorted(fam): out.append(f"| {k} | {len(fam[k])} | {pct(sum(r['pass'] for r in fam[k]), len(fam[k]))} |")
    out += ["", "## Score breakdown"]
    for s in [x for x in ("A", "B", "C") if any(r["scores"].get(x) is not None for r in recs)]:
        out += [f"### {s}", "| model | n | mean | stdev |", "|---|---:|---:|---:|"]
        for m, rs in sorted(bym.items()):
            xs = [r["scores"][s] for r in rs if r["scores"].get(s) is not None]; out.append(f"| {m} | {len(xs)} | {mean(xs):.2f} | {(stdev(xs) if len(xs) > 1 else 0):.2f} |" if xs else f"| {m} | 0 | - | - |")
    groups = defaultdict(list); agree = pairs = 0; outs = []
    for r in recs: groups[(r["task"], r["model"], r["prompt"])].append(r)
    for key, rs in groups.items():
        rs = list({r["evaluator"]: r for r in rs}.values())
        if len(rs) < 2: continue
        if len({r["pass"] for r in rs}) > 1: outs.append((key, rs))
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)): pairs += 1; agree += rs[i]["pass"] == rs[j]["pass"]
    out += ["", "## Evaluator agreement", f"- compared pairs: {pairs}", f"- overall agreement: {pct(agree, pairs)}", "", "## Outliers", "| task | model | evaluator verdicts |", "|---|---|---|"]
    for (t, m, p), rs in sorted(outs)[:10]: out.append(f"| {t} | {m + (' (' + p + ')' if p else '')} | {'; '.join(r['evaluator'] + '=' + r['verdict'] for r in rs)} |")
    if not outs: out.append("| - | - | - |")
    out += ["", f"skipped {skipped} rows"]; return "\n".join(out) + "\n"
def main():
    p, op = args(); p = resolve(p); text = render(p, *load(p))
    open(op, "w", encoding="utf-8").write(text) if op else sys.stdout.write(text)
if __name__ == "__main__": main()
