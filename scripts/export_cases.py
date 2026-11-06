"""Export the 50 test cases + outputs to the C-section spreadsheet.

Usage: python scripts/export_cases.py --run main_v31 [--baseline main_v0] [--judge openai]
Writes deliverables/C_test_cases.xlsx:
  1. "Test cases"  — the main case table (fixed columns)
  2. "Details"     — version, model, risk check, slot labels, CA notes, rule checks, judge scores
  3. "Baseline v0" — the single-prompt baseline on the same inputs, for comparison
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from delorme.calendar_cn import context as calendar_context  # noqa: E402
from delorme.knowledge import event, product, render_product  # noqa: E402
from delorme.schemas import SCENARIO_LABELS, CaseInput  # noqa: E402


def client_info(case: CaseInput) -> str:
    c, ca, f = case.client, case.ca, case.client.flags
    name = c.surname + ("女士" if c.gender == "女" else "先生")
    owned = "；".join(f"{p.date} {p.item}" + (f"（{p.for_whom}）" if p.for_whom else "") + (f"，{p.note}" if p.note else "")
                     for p in c.owned_pieces) or "无"
    rows = [
        f"称呼：{name}" + (f"（{c.given_name}）" if c.given_name else ""),
        f"{c.gender}｜{c.age_range} 岁｜{c.city}｜{c.occupation or '—'}",
        f"客户自 {c.client_since or '—'}｜消费区间 {c.spend_band}｜阶段 {c.stage}",
        f"最近到店 {c.last_visit or '—'}｜最近购买 {c.last_purchase or '—'}",
        f"财富来源 {c.wealth_source}｜动机 {'、'.join(c.motivations) or '—'}｜曝光 {c.social_visibility}｜价格敏感 {c.price_sensitivity}",
        f"偏好：{c.style_preference or '—'}；材质 {c.material_preference or '—'}；尺寸 {c.sizes or '—'}",
        f"已有作品：{owned}",
        f"沟通：{c.formality}；{c.reply_habit or '—'}；对推荐 {c.recommendation_openness}；联系时段 {c.preferred_contact_time or '—'}",
        f"生日 {c.birthday or '—'}；重要日期 {'、'.join(c.important_dates) or '—'}；家人 {c.family_notes or '—'}",
        f"兴趣：{'、'.join(c.interests) or '—'}",
    ]
    if c.notes:
        rows.append(f"CA 手记：{c.notes}")
    sens = [s for s in [
        "礼赠关系（付款人另有其人，需保密）" if f.payer_not_wearer else "",
        "转售风险" if f.resale_risk else "",
        f"未解决投诉：{f.open_complaint}" if f.open_complaint else "",
        f"近期家庭变故：{f.recent_bereavement}" if f.recent_bereavement else "",
        "已明确拒绝推销" if f.opted_out_marketing else "",
        f.other or "",
    ] if s]
    if sens:
        rows.append("敏感标记：" + "；".join(sens))
    rows.append(f"—— CA：{ca.name}（{ca.gender}，{ca.years_experience} 年，{ca.store}，认识自 {ca.known_client_since or '刚接手'}，{ca.style}）")
    return "\n".join(rows)


def scenario_info(case: CaseInput) -> str:
    rows = [f"{SCENARIO_LABELS[case.scenario]}（{case.scenario}）", f"日期：{case.today}"]
    if case.occasion:
        rows.append(f"补充：{case.occasion}")
    if case.ca_request:
        rows.append(f"CA 要求：{case.ca_request}")
    if case.ca_draft:
        rows.append(f"CA 要点/草稿：{case.ca_draft}")
    return "\n".join(rows)


def history(case: CaseInput) -> str:
    name = case.client.surname + ("女士" if case.client.gender == "女" else "先生")
    return "\n".join(f"[{m.time}] {'CA ' + case.ca.name if m.sender == 'ca' else name}：{m.text}"
                     for m in case.conversation_history) or "（无）"


def product_info(case: CaseInput) -> str:
    rows = [render_product(product(s)).lstrip("- ") for s in case.product_skus if product(s)]
    if case.event_id and event(case.event_id):
        e = event(case.event_id)
        rows.append(f"活动：{e['name']}｜{e['date']}｜{e['place']}｜{e['content']}")
    return "\n".join(rows) or "—"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--provider", default="gemini")
    ap.add_argument("--baseline", default=None)
    ap.add_argument("--judge", default=None)
    ap.add_argument("--out", default="deliverables/C_test_cases.xlsx")
    a = ap.parse_args()

    main_rows, detail_rows, base_rows = [], [], []
    for f in sorted((ROOT / "data/cases").glob("C*.json")):
        case = CaseInput.model_validate_json(f.read_text(encoding="utf-8"))
        out = json.loads((ROOT / "runs" / a.run / a.provider / f.name).read_text(encoding="utf-8"))
        cands = out["candidates"]
        main_rows.append({
            "Case ID": case.case_id, "Scenario": scenario_info(case), "Client information": client_info(case),
            "Conversation history": history(case), "Product information": product_info(case),
            **{f"Output {i}": f"【{c['strategy']}】{c['text']}" for i, c in enumerate(cands, 1)},
        })
        meta = case.test_meta or {}
        d = {
            "Case ID": case.case_id, "Version": out["version"], "Model": out["model"],
            "Persona (test dim.)": meta.get("persona"), "Case type": meta.get("type"),
            "Must": "；".join(meta.get("must", [])), "Must not": "；".join(meta.get("must_not", [])),
            "Calendar given to tool": calendar_context(case.today),
            "Risk level": out["risk"]["level"], "Risk flags": "；".join(out["risk"]["flags"]), "Advice to CA": out["risk"]["advice"],
            **{f"CA note {i}": c["note_for_ca"] for i, c in enumerate(cands, 1)},
            "Rule checks": "；".join(h for chk in out["checks"] for h in chk["hard"]) or "全部通过",
            "Rewrite rounds": len(out["trace"].get("rounds", [])), "Seconds": out["trace"].get("seconds"),
        }
        if a.judge:
            jp = ROOT / "runs" / a.run / f"judge_{a.judge}" / a.provider / f.name
            if jp.exists():
                j = json.loads(jp.read_text(encoding="utf-8"))
                for i, c in enumerate(j.get("candidates", []), 1):
                    d[f"Judge {i} sendability"] = c.get("sendability")
                    d[f"Judge {i} avg score"] = round(sum(c.get("scores", {}).values()) / 4, 2)
                d["Judge summary"] = j.get("set", {}).get("summary")
        detail_rows.append(d)
        if a.baseline:
            bp = ROOT / "runs" / a.baseline / a.provider / f.name
            if bp.exists():
                b = json.loads(bp.read_text(encoding="utf-8"))
                base_rows.append({"Case ID": case.case_id, "Version": b["version"], "Model": b["model"],
                                  **{f"Output {i}": c["text"] for i, c in enumerate(b["candidates"], 1)}})

    dest = ROOT / a.out
    dest.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(dest, engine="openpyxl") as xw:
        for name, rows in (("Test cases", main_rows), ("Details", detail_rows), ("Baseline v0", base_rows)):
            if not rows:
                continue
            pd.DataFrame(rows).to_excel(xw, sheet_name=name, index=False)
            ws = xw.sheets[name]
            ws.freeze_panes = "B2"
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="0F5B5C")
            for col in ws.columns:
                header = str(col[0].value)
                width = 12 if header in ("Case ID", "Version", "Risk level", "Seconds", "Rewrite rounds") else 40
                ws.column_dimensions[col[0].column_letter].width = width
                for cell in col:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
    print(f"wrote {dest} ({len(main_rows)} cases)")


if __name__ == "__main__":
    main()
