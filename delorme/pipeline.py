"""v0 (single prompt) and v1 (plan -> write -> check -> rewrite) generators."""
from __future__ import annotations

import json
import time

from . import prompts as P
from .checks import check_message, diversity, sameness
from .knowledge import brand_book, catalog_overview, render_case, render_playbook
from .llm import CALL_LOG, ModelSpec, chat_json
from .schemas import Candidate, CaseInput, RiskAssessment, ToolOutput


def _candidates(data: dict) -> list[Candidate]:
    return [Candidate(**{k: c.get(k, "") for k in ("text", "strategy", "note_for_ca")}) for c in data["candidates"]][:3]


def _rule_checks(cands: list[Candidate], scenario: str) -> list[dict]:
    return [check_message(c.text, scenario) for c in cands]


def run_v0(case: CaseInput, model: ModelSpec) -> ToolOutput:
    t0 = time.time()
    data = chat_json(model, P.V0_SYSTEM.format(brand_book=brand_book()), P.V0_USER.format(case=render_case(case)))
    cands = _candidates(data)
    return ToolOutput(
        case_id=case.case_id, version="v0", model=model.label, risk=RiskAssessment(),
        candidates=cands, checks=_rule_checks(cands, case.scenario),
        trace={"seconds": round(time.time() - t0, 1), "diversity_max_sim": diversity([c.text for c in cands])},
    )


def run_v1(case: CaseInput, model: ModelSpec, critic: ModelSpec | None = None, max_rounds: int = 2) -> ToolOutput:
    t0 = time.time()
    critic = critic or model
    case_txt = render_case(case)
    playbook = render_playbook(case.scenario)
    allocated = case.client.stage == "晨星资格" or any(s.startswith(("ETO", "NVD")) for s in case.product_skus)
    trace: dict = {"rounds": []}

    # 1. analyse & plan
    plan = chat_json(
        model,
        P.PLAN_SYSTEM.format(brand_book=brand_book(), playbook=playbook, catalog=catalog_overview(allocated)),
        P.PLAN_USER.format(case=case_txt),
    )
    trace["plan"] = plan
    plan_txt = json.dumps(plan, ensure_ascii=False, indent=1)

    # 2. write
    write_sys = P.WRITE_SYSTEM.format(brand_book=brand_book(), playbook=playbook)
    cands = _candidates(chat_json(model, write_sys, P.WRITE_USER.format(case=case_txt, plan=plan_txt)))
    trace["first_draft"] = [c.model_dump() for c in cands]

    # 3-4. check & rewrite loop
    critic_sys = P.CRITIC_SYSTEM.format(brand_book=brand_book(), playbook=playbook)
    for rnd in range(max_rounds):
        checks = _rule_checks(cands, case.scenario)
        drafts = "\n".join(f"{i+1}. {c.text}" for i, c in enumerate(cands))
        review = chat_json(
            critic, critic_sys,
            P.CRITIC_USER.format(case=case_txt, do_not_mention=json.dumps(plan.get("do_not_mention", []), ensure_ascii=False), drafts=drafts),
        )
        issues: dict[int, list[str]] = {}
        for i, chk in enumerate(checks):
            if not chk["pass"]:
                issues.setdefault(i, []).extend(chk["hard"])
        for r in review.get("reviews", []):
            i = int(r.get("index", 0)) - 1
            if 0 <= i < len(cands) and not r.get("pass", True):
                issues.setdefault(i, []).extend(r.get("issues", []))
        trace["rounds"].append({"rule_checks": checks, "critic": review, "to_fix": {i + 1: v for i, v in issues.items()}})
        if not issues:
            break
        bad = "\n".join(
            f"{i+1}. 原文：{cands[i].text}\n   角度：{cands[i].strategy}\n   问题：{'；'.join(v)}" for i, v in sorted(issues.items())
        )
        fixed = chat_json(model, write_sys, P.REWRITE_USER.format(case=case_txt, plan=plan_txt, drafts=bad))
        for c in fixed.get("candidates", []):
            i = int(c.get("index", 0)) - 1
            if 0 <= i < len(cands) and c.get("text"):
                cands[i] = Candidate(text=c["text"], strategy=c.get("strategy") or cands[i].strategy,
                                     note_for_ca=c.get("note_for_ca") or cands[i].note_for_ca)

    risk = plan.get("risk") or {}
    trace["seconds"] = round(time.time() - t0, 1)
    trace["diversity_max_sim"] = diversity([c.text for c in cands])
    return ToolOutput(
        case_id=case.case_id, version="v1", model=model.label,
        risk=RiskAssessment(level=risk.get("level", "ok") if risk.get("level") in ("ok", "caution", "hold") else "caution",
                            flags=risk.get("flags", []), advice=risk.get("advice", "")),
        candidates=cands, checks=_rule_checks(cands, case.scenario), trace=trace,
    )


SLOTS = ["极简", "走心", "推进"]
SLOT_RULES = {
    "极简": "≤30 字，只做一件事；删掉所有细节、数字、时间和安排，细节留给另外两条",
    "走心": "30–80 字，从一个真实的客户细节切入，不要和“推进”用同一个细节",
    "推进": "40–110 字，给一个具体、容易回应的下一步",
}
SLOT_RULES_V3 = {
    "极简": "这个情境下最短、但得体完整的版本；不为了短而生硬，不加可有可无的话",
    "走心": "把一个真实的客户细节自然地用进话里，不宣布“我记得”",
    "推进": "给一个具体、容易回应的下一步（只用资料里有的）",
}


def run_v2(case: CaseInput, model: ModelSpec, critic: ModelSpec | None = None, max_rounds: int = 3,
           version: str = "v2") -> ToolOutput:
    """v2: fixed slots, commitments only from CA input, grounded calendar, calibrated risk, sameness checks.
    v3 (same flow): the slots are intents, not length rules; meta-talk banned; timeline for recency."""
    V = version.upper().replace(".", "")
    prompt = lambda name: getattr(P, f"{V}_{name}")  # noqa: E731
    slot_rules = SLOT_RULES if version == "v2" else SLOT_RULES_V3
    t0 = time.time()
    critic = critic or model
    case_txt = render_case(case, calendar=True)
    playbook = render_playbook(case.scenario)
    allocated = case.client.stage == "晨星资格" or any(s.startswith(("ETO", "NVD")) for s in case.product_skus)
    ca_input = " ".join(filter(None, [case.ca_draft, case.ca_request, case.client.notes]))
    trace: dict = {"rounds": []}

    def checks_for(cands: list[Candidate]) -> list[dict]:
        # when the CA supplied points, every candidate must carry them, so the 极简 length rule is relaxed
        strict = version == "v2" and not (case.ca_draft or case.ca_request)
        return [check_message(c.text, case.scenario, ca_input, SLOTS[i] if strict and i < 3 else None) for i, c in enumerate(cands)]

    plan = chat_json(
        model,
        prompt("PLAN_SYSTEM").format(brand_book=brand_book(), playbook=playbook, catalog=catalog_overview(allocated)),
        prompt("PLAN_USER").format(case=case_txt),
    )
    trace["plan"] = plan
    plan_txt = json.dumps(plan, ensure_ascii=False, indent=1)

    write_sys = prompt("WRITE_SYSTEM").format(brand_book=brand_book(), playbook=playbook)
    cands = _candidates(chat_json(model, write_sys, prompt("WRITE_USER").format(case=case_txt, plan=plan_txt)))
    for i, c in enumerate(cands):  # slot names are fixed, whatever the model wrote
        c.strategy = SLOTS[i]
    trace["first_draft"] = [c.model_dump() for c in cands]

    critic_sys = prompt("CRITIC_SYSTEM").format(brand_book=brand_book(), playbook=playbook)
    for _ in range(max_rounds):
        checks = checks_for(cands)
        drafts = "\n".join(f"{i+1}.（{c.strategy}）{c.text}" for i, c in enumerate(cands))
        review = chat_json(critic, critic_sys, prompt("CRITIC_USER").format(
            case=case_txt,
            do_not_mention=json.dumps(plan.get("do_not_mention", []), ensure_ascii=False),
            commitments=json.dumps(plan.get("ca_commitments", []), ensure_ascii=False) or "无",
            drafts=drafts,
        ))
        issues: dict[int, list[str]] = {}
        for i, chk in enumerate(checks):
            if not chk["pass"]:
                issues.setdefault(i, []).extend(chk["hard"])
        for r in review.get("reviews", []):
            i = int(r.get("index", 0)) - 1
            if 0 <= i < len(cands) and not r.get("pass", True):
                issues.setdefault(i, []).extend(r.get("issues", []))
        same = sameness([c.text for c in cands]) if version == "v2" else []  # v3: sameness is judged semantically by the critic only
        set_issues = [s.get("issue", "") for s in review.get("set_issues", [])] + same
        # a sameness problem is fixed by rewriting the later candidate of each pair
        for s in review.get("set_issues", []):
            idx = [int(x) - 1 for x in s.get("indices", []) if 1 <= int(x) <= len(cands)]
            if len(idx) >= 2:
                issues.setdefault(max(idx), []).append("与其他候选雷同：" + s.get("issue", ""))
        for msg in same:
            j = int(msg.split("和 ")[1].split(" ")[0]) - 1
            issues.setdefault(j, []).append(msg)
        trace["rounds"].append({"rule_checks": checks, "critic": review, "set_issues": set_issues,
                                "to_fix": {i + 1: v for i, v in issues.items()}})
        if not issues:
            break
        bad = "\n".join(
            f"{i+1}.（{cands[i].strategy}）原文：{cands[i].text}\n   问题：{'；'.join(v)}\n   槽位要求：{slot_rules[cands[i].strategy]}"
            for i, v in sorted(issues.items())
        )
        fixed = chat_json(model, write_sys, prompt("REWRITE_USER").format(case=case_txt, plan=plan_txt, all_drafts=drafts, drafts=bad))
        for c in fixed.get("candidates", []):
            i = int(c.get("index", 0)) - 1
            if 0 <= i < len(cands) and c.get("text"):
                cands[i] = Candidate(text=c["text"], strategy=SLOTS[i], note_for_ca=c.get("note_for_ca") or cands[i].note_for_ca)

    risk = plan.get("risk") or {}
    trace["seconds"] = round(time.time() - t0, 1)
    trace["diversity_max_sim"] = diversity([c.text for c in cands])
    return ToolOutput(
        case_id=case.case_id, version=version, model=model.label,
        risk=RiskAssessment(level=risk.get("level") if risk.get("level") in ("ok", "caution", "hold") else "caution",
                            flags=risk.get("flags", []), advice=risk.get("advice", "")),
        candidates=cands, checks=checks_for(cands), trace=trace,
    )


LANG_NOTE = {
    "en": "\n\n（界面语言：英文）除消息正文 text 必须是简体中文外，其余给 CA 看的字段（label/strategy、note_for_ca、"
          "风险 flags 与 advice、key_choice、client_read、idea、tradeoff）一律用英文写。",
}


def run_v4(case: CaseInput, model: ModelSpec, critic: ModelSpec | None = None, max_rounds: int = 3,
           version: str = "v4", on_progress=None, note_lang: str = "zh") -> ToolOutput:
    """v4: the model reads the situation, picks the CA's real choice and three directions along it.
    The only hard line is commitments the CA did not make; everything else is judgement.
    v4.1 = same flow with three small prompt nudges.
    Demo-only options (defaults keep the frozen v4 prompts byte-identical):
      on_progress(stage, data) — called after "plan", "draft" and each "rewrite", so a UI can show drafts early;
      note_lang="en" — CA-facing notes/analysis in English, messages stay Chinese."""
    lang = LANG_NOTE.get(note_lang, "")
    emit = on_progress or (lambda *a: None)
    V = version.upper().replace(".", "")
    prompt = lambda name: getattr(P, f"{V}_{name}")  # noqa: E731
    t0 = time.time()
    critic = critic or model
    case_txt = render_case(case, calendar=True)
    playbook = render_playbook(case.scenario)
    allocated = case.client.stage == "晨星资格" or any(s.startswith(("ETO", "NVD")) for s in case.product_skus)
    ca_input = " ".join(filter(None, [case.ca_draft, case.ca_request, case.client.notes]))
    trace: dict = {"rounds": []}

    def checks_for(cands: list[Candidate]) -> list[dict]:
        return [check_message(c.text, case.scenario, ca_input) for c in cands]

    plan = chat_json(
        model,
        prompt("PLAN_SYSTEM").format(brand_book=brand_book(), playbook=playbook, catalog=catalog_overview(allocated)),
        prompt("PLAN_USER").format(case=case_txt) + lang,
    )
    trace["plan"] = plan
    emit("plan", plan)
    plan_txt = json.dumps(plan, ensure_ascii=False, indent=1)
    directions = plan.get("directions") or []

    write_sys = prompt("WRITE_SYSTEM").format(brand_book=brand_book(), playbook=playbook)
    cands = _candidates(chat_json(model, write_sys, prompt("WRITE_USER").format(case=case_txt, plan=plan_txt) + lang))
    trace["first_draft"] = [c.model_dump() for c in cands]
    emit("draft", list(cands))

    critic_sys = prompt("CRITIC_SYSTEM").format(brand_book=brand_book(), playbook=playbook)
    for _ in range(max_rounds):
        checks = checks_for(cands)
        drafts = "\n".join(f"{i+1}.（{c.strategy}）{c.text}\n   备注：{c.note_for_ca}" for i, c in enumerate(cands))
        review = chat_json(critic, critic_sys, prompt("CRITIC_USER").format(
            case=case_txt,
            do_not_mention=json.dumps(plan.get("do_not_mention", []), ensure_ascii=False),
            commitments=json.dumps(plan.get("ca_commitments", []), ensure_ascii=False) or "无",
            drafts=drafts,
        ))
        issues: dict[int, list[str]] = {}
        for i, chk in enumerate(checks):
            if not chk["pass"]:
                issues.setdefault(i, []).extend(chk["hard"])
        for r in review.get("reviews", []):
            i = int(r.get("index", 0)) - 1
            if 0 <= i < len(cands) and not r.get("pass", True):
                issues.setdefault(i, []).extend(r.get("issues", []))
        for s in review.get("set_issues", []):
            idx = [int(x) - 1 for x in s.get("indices", []) if 1 <= int(x) <= len(cands)]
            if len(idx) >= 2:
                issues.setdefault(max(idx), []).append("与其他候选雷同：" + s.get("issue", ""))
        trace["rounds"].append({"rule_checks": checks, "critic": review, "to_fix": {i + 1: v for i, v in issues.items()}})
        if not issues:
            break
        bad = "\n".join(
            f"{i+1}.（{cands[i].strategy}）原文：{cands[i].text}\n   问题：{'；'.join(v)}"
            + (f"\n   这条的方向：{directions[i].get('idea', '')}" if i < len(directions) else "")
            for i, v in sorted(issues.items())
        )
        fixed = chat_json(model, write_sys, prompt("REWRITE_USER").format(case=case_txt, plan=plan_txt, all_drafts=drafts, drafts=bad) + lang)
        for c in fixed.get("candidates", []):
            i = int(c.get("index", 0)) - 1
            if 0 <= i < len(cands) and c.get("text"):
                cands[i] = Candidate(text=c["text"], strategy=c.get("strategy") or cands[i].strategy,
                                     note_for_ca=c.get("note_for_ca") or cands[i].note_for_ca)
        emit("rewrite", {"round": len(trace["rounds"]), "fixed": sorted(issues), "candidates": list(cands)})

    risk = plan.get("risk") or {}
    trace["seconds"] = round(time.time() - t0, 1)
    trace["diversity_max_sim"] = diversity([c.text for c in cands])
    return ToolOutput(
        case_id=case.case_id, version=version, model=model.label,
        risk=RiskAssessment(level=risk.get("level") if risk.get("level") in ("ok", "caution", "hold") else "caution",
                            flags=risk.get("flags", []), advice=risk.get("advice", "")),
        candidates=cands, checks=checks_for(cands), trace=trace,
    )


RUNNERS = {"v0": lambda c, m, k: run_v0(c, m), "v1": run_v1, "v2": run_v2, "v4": run_v4,
           "v4.1": lambda c, m, k: run_v4(c, m, k, version="v4.1"),
           "v3": lambda c, m, k: run_v2(c, m, k, version="v3"),
           "v3.1": lambda c, m, k: run_v2(c, m, k, version="v3.1")}


def generate(case: CaseInput, model: ModelSpec, version: str = "v4", critic: ModelSpec | None = None,
             **demo_opts) -> ToolOutput:
    """demo_opts (on_progress, note_lang) are only understood by v4."""
    calls: list = []
    token = CALL_LOG.set(calls)
    try:
        out = run_v4(case, model, critic, **demo_opts) if demo_opts else RUNNERS[version](case, model, critic)
    finally:
        CALL_LOG.reset(token)
    out.trace["calls"] = calls
    return out
