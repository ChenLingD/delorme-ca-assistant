"""Aggregate a multi-model run: automatic metrics, judge scores, self-preference, and a blind sheet for human review.

Usage: python scripts/bakeoff_report.py --run bakeoff
Writes runs/<run>/summary.md, runs/<run>/blind_review.xlsx, runs/<run>/blind_key.json
"""
import argparse
import json
import random
import statistics as st
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from delorme.checks import jaccard  # noqa: E402
from delorme.judge import flatten  # noqa: E402

DIMS = ["personalization", "brand_voice", "naturalness", "effectiveness"]


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    a = ap.parse_args()
    run = ROOT / "runs" / a.run
    matrix = {c["id"]: c for c in yaml.safe_load((ROOT / "data/test_matrix.yaml").read_text(encoding="utf-8"))["cases"]}
    gens = sorted(d.name for d in run.iterdir() if d.is_dir() and not d.name.startswith("judge_"))
    judges = sorted(d.name.removeprefix("judge_") for d in run.iterdir() if d.is_dir() and d.name.startswith("judge_"))
    outs = {g: {p.stem: load(p) for p in sorted((run / g).glob("C*.json"))} for g in gens}

    # ---- automatic metrics per generator
    auto = []
    for g in gens:
        o = list(outs[g].values())
        texts = [c["text"] for r in o for c in r["candidates"]]
        lens = [chk["length"] for r in o for chk in r["checks"]]
        # cross-case repetition: mean max trigram-jaccard of each message vs messages from other cases
        cross = []
        for r in o:
            others = [c["text"] for r2 in o if r2["case_id"] != r["case_id"] for c in r2["candidates"]]
            for c in r["candidates"]:
                cross.append(max((jaccard(c["text"], t) for t in others), default=0))
        auto.append({
            "generator": g, "model": o[0]["model"], "n_cases": len(o),
            "sec_per_case": round(st.mean(r["trace"].get("seconds", 0) for r in o), 1),
            "rule_fail_msgs": sum(not chk["pass"] for r in o for chk in r["checks"]),
            "rewrite_needed_cases": sum(bool(r["trace"].get("rounds") and r["trace"]["rounds"][0]["to_fix"]) for r in o),
            "median_len": st.median(lens), "max_len": max(lens),
            "within_set_sim": round(st.mean(r["trace"].get("diversity_max_sim", 0) for r in o), 3),
            "cross_case_sim": round(st.mean(cross), 3),
            "risk_levels": "/".join(f"{lv}:{sum(r['risk']['level'] == lv for r in o)}" for lv in ("ok", "caution", "hold")),
            "n_msgs": len(texts),
        })
    auto_df = pd.DataFrame(auto)

    # ---- judge scores
    rows = []
    for j in judges:
        for g in gens:
            for p in sorted((run / f"judge_{j}" / g).glob("C*.json")):
                rows.append({"judge": j, "generator": g, "case": p.stem, **flatten(load(p))})
    jdf = pd.DataFrame(rows)
    lines = [f"# Run `{a.run}` summary\n", "## Automatic metrics\n", auto_df.to_markdown(index=False), ""]
    if not jdf.empty:
        jdf["overall"] = jdf[DIMS].mean(axis=1)
        agg = jdf.groupby(["generator", "judge"]).agg(
            overall=("overall", "mean"), **{d: (d, "mean") for d in DIMS},
            red_flag_msgs=("red_flag_candidates", "sum"), minor_flag_msgs=("minor_flag_candidates", "sum"), direct_send=("direct_send", "sum"),
            minor_edit=("minor_edit", "sum"), unusable=("unusable", "sum"), diversity=("diversity", "mean"),
        ).round(2).reset_index()
        pivot = jdf.pivot_table(index="generator", columns="judge", values="overall", aggfunc="mean").round(2)
        pivot["mean"] = pivot.mean(axis=1).round(2)
        risk = jdf.groupby("generator")["risk_judgement"].value_counts().unstack(fill_value=0)
        lines += ["## Judge scores (per generator × judge)\n", agg.to_markdown(index=False), "",
                  "## Overall score matrix — read rows for quality, columns for judge leniency / self-preference\n",
                  pivot.to_markdown(), "", "## Risk judgement (judge view, all judges)\n", risk.to_markdown(), ""]
        jdf.to_csv(run / "judge_rows.csv", index=False, encoding="utf-8-sig")
    (run / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

    # ---- blind sheet for human review
    rnd = random.Random(20261105)
    key, blind = {}, []
    for cid in sorted(outs[gens[0]]):
        order = gens[:]
        rnd.shuffle(order)
        key[cid] = {chr(65 + i): g for i, g in enumerate(order)}
        m = matrix[cid]
        blind.append({"用例": cid, "组": "—", "场景/情境": f"[{m['scenario']}] {m['situation']}",
                      "应做到": "；".join(m.get("must", [])), "绝不能": "；".join(m.get("must_not", []))})
        for i, g in enumerate(order):
            r = outs[g].get(cid)
            if not r:
                continue
            row = {"用例": cid, "组": chr(65 + i), "风险判断": f"{r['risk']['level']}：{r['risk']['advice']}"}
            for k, c in enumerate(r["candidates"], 1):
                row[f"候选{k}"] = c["text"]
            row.update({"你的排名(1=最好)": "", "可直接发送的条数(0-3)": "", "备注": ""})
            blind.append(row)
    pd.DataFrame(blind).to_excel(run / "blind_review.xlsx", index=False)
    (run / "blind_key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
