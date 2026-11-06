"""Maison Delorme · CA 话术助手 — Streamlit demo (style: WeChat workbench, UI zh/en).

Run locally:  streamlit run app.py
Secrets: GEMINI_API_KEY (required), OPENAI_API_KEY (optional, for the "GPT" option / free-text import).
WeChat messages are always Simplified Chinese; the UI language only changes labels, risk advice and CA notes.
"""
from __future__ import annotations

import html
import json
import os
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
# Streamlit Cloud puts secrets in st.secrets; mirror them into the environment for the SDK clients
try:
    for k, v in st.secrets.items():
        if isinstance(v, str):
            os.environ.setdefault(k, v)
except Exception:
    pass

os.environ.setdefault("MODEL_FALLBACK", "1")  # demo: if Gemini 3.8 is overloaded, retry on 3.7
from delorme.calendar_cn import ago  # noqa: E402
from delorme.knowledge import render_case  # noqa: E402
from delorme.llm import chat_json, parse_spec  # noqa: E402
from delorme.pipeline import generate  # noqa: E402
from delorme.schemas import SCENARIO_LABELS, CaseInput, Candidate  # noqa: E402

MAX_RUNS_PER_SESSION = int(os.environ.get("DEMO_MAX_RUNS", "20"))
MODELS = {"Gemini 3.8 Flash": "gemini", "GPT-6.1 Terra": "openai"}
KEY_ENV = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY"}

# ---------------- UI strings ----------------
T = {
    "zh": {
        "title": "德洛姆 CA 工作台",
        "subtitle": "虚构品牌 Maison Delorme · 为客户顾问起草三条可选的微信消息",
        "load_case": "从 50 条测试用例载入", "load_btn": "载入", "model": "生成模型", "recommended": "（评测所用）",
        "model_help": "50 条评测与人工盲评用的是 Gemini 3.8 Flash（人工评分第一）。GPT-6.1 Terra 在盲评中与它接近，也是评测里的 judge。",
        "runs": "本次会话已生成 {n} / {m} 次", "free_title": "用一段文字描述新客户",
        "free_ph": "例如：王女士，35 岁，上海律师，去年买过沧海耳钉；昨天她发消息说……",
        "free_btn": "整理成输入", "free_wait": "整理中…", "free_err": "整理失败：{e}",
        "client": "客户", "chat": "聊天记录", "no_chat": "（还没有聊天记录）", "since": "客户自 {d}",
        "owned": "已购", "interests": "兴趣", "notes": "CA 手记", "sensitive": "敏感",
        "compose": "这次要发什么", "scenario": "场景", "today": "今天日期", "occasion": "场景补充",
        "request": "CA 想达成什么", "request_ph": "可选，例如：想邀请她来看珍珠展",
        "request_help": "这次联系的目的。不填则由工具按场景判断。",
        "draft": "CA 要点 / 草稿",
        "draft_ph": "可选，例如：生日月来店里有一份小礼物，不用特意跑",
        "draft_help": "礼物、预留、具体时间、名额等承诺只能写在这里——工具不会替 CA 承诺 CA 没说过的事。",
        "json": "完整输入（可直接编辑 JSON）", "context": "工具实际看到的上下文（含系统计算的日历与时间线）",
        "bad_input": "输入格式有误：{e}",
        "candidates": "三条候选", "generate": "生成三条候选", "quota": "本次会话的生成次数已用完（演示站点限制调用量）。",
        "empty": "点「生成三条候选」：约 30 秒先出初稿，质检改写后自动替换为定稿。",
        "s_plan": "分析情境、判断风险、规划三个方向…", "s_draft": "初稿已出，正在质检…",
        "s_rewrite": "第 {r} 轮改写了第 {i} 条，继续质检…", "s_done": "用时 {s} 秒 · 初稿 {d} 秒",
        "s_fail": "生成失败", "subbed": " · 首选模型繁忙，部分步骤改用 {m}", "fallback": "首选模型暂时不可用，改用 {m} 重试…",
        "s_busy": "模型服务暂时繁忙（503/429），已自动重试仍失败。请过一两分钟再试，或在侧边栏切换模型。", "draft_badge": "初稿 · 质检中", "final_badge": "定稿",
        "risk": {"ok": "可以发", "caution": "注意写法", "hold": "建议先处理别的事"}, "risk_more": "风险与建议",
        "risk_flags": "风险点", "key_choice": "这次 CA 要做的选择", "option": "方案 {i}",
        "note": "给 CA", "copy": "复制", "rule": "规则检查：{x}", "send_as": "{ca} 发给 {client}",
        "process": "分析与质检过程", "advanced": "更多输入",
        "profile_more": "完整档案", "habit": "沟通", "family": "家人", "plan": "计划", "rounds": "质检轮次", "calls": "调用记录",
        "msg_lang": "消息为简体中文", "switch": "EN",
    },
    "en": {
        "title": "Delorme CA Workbench",
        "subtitle": "Fictional brand Maison Delorme · drafts three WeChat messages a Client Advisor can choose from",
        "load_case": "Load one of the 50 test cases", "load_btn": "Load", "model": "Model", "recommended": " (used in evaluation)",
        "model_help": "The 50-case evaluation and human blind reviews used Gemini 3.8 Flash (ranked first by humans). GPT-6.1 Terra was close in blind review and is the evaluation judge.",
        "runs": "Generations this session: {n} / {m}", "free_title": "Describe a new client in plain words",
        "free_ph": "e.g. Ms Wang, 35, lawyer in Shanghai, bought Canghai earrings last year; yesterday she wrote…",
        "free_btn": "Turn into input", "free_wait": "Structuring…", "free_err": "Could not structure: {e}",
        "client": "Client", "chat": "Conversation", "no_chat": "(no messages yet)", "since": "client since {d}",
        "owned": "Owns", "interests": "Interests", "notes": "CA notes", "sensitive": "Sensitive",
        "compose": "What to send", "scenario": "Scenario", "today": "Today", "occasion": "Occasion detail",
        "request": "What the CA wants", "request_ph": "Optional, e.g. invite her to the pearl exhibition",
        "request_help": "The purpose of this message. Leave empty to let the tool decide from the scenario.",
        "draft": "CA points / draft",
        "draft_ph": "Optional, e.g. a small birthday-month gift in store",
        "draft_help": "Gifts, holds, specific times or places can only come from here — the tool never promises what the CA did not.",
        "json": "Full input (editable JSON)", "context": "Exact context the tool sees (with computed calendar & timeline)",
        "bad_input": "Input is not valid: {e}",
        "candidates": "Three candidates", "generate": "Generate three candidates", "quota": "This session has used its generation quota (demo limit).",
        "empty": "Press Generate: first drafts in ~30 s, replaced by checked final versions when done.",
        "s_plan": "Reading the situation, assessing risk, planning three directions…", "s_draft": "First drafts ready, checking…",
        "s_rewrite": "Round {r}: rewrote option {i}, checking again…", "s_done": "{s} s · first drafts at {d} s",
        "s_fail": "Generation failed", "subbed": " · preferred model busy, some steps used {m}", "fallback": "Preferred model unavailable, retrying with {m}…",
        "s_busy": "The model service is busy (503/429) and retries did not help. Try again in a minute or switch model in the sidebar.", "draft_badge": "draft · checking", "final_badge": "final",
        "risk": {"ok": "OK to send", "caution": "Mind the wording", "hold": "Handle something else first"}, "risk_more": "risks & advice",
        "risk_flags": "Risks", "key_choice": "The CA's real choice here", "option": "Option {i}",
        "note": "For the CA", "copy": "Copy", "rule": "Rule check: {x}", "send_as": "{ca} → {client}",
        "process": "Analysis & checking trace", "advanced": "More input",
        "profile_more": "Full profile", "habit": "Style", "family": "Family", "plan": "Plan", "rounds": "Check rounds", "calls": "Call log",
        "msg_lang": "messages in Simplified Chinese", "switch": "中文",
    },
}
SCENARIO_EN = {
    "birthday_festive": "Birthday & festive", "product_recommendation": "Product recommendation",
    "post_purchase": "Post-purchase care", "reactivation": "Reactivation",
    "event_invitation": "Event invitation", "price_objection": "Price objection",
}

st.set_page_config(page_title="Delorme CA Workbench", page_icon="💬", layout="wide")
st.markdown(
    """<style>
    .block-container {padding-top: 3rem; max-width: 1400px}
    [data-testid="stSidebarCollapseButton"] {display:flex !important; visibility:visible !important}
    [data-testid="stSidebarCollapseButton"] button, [data-testid="stExpandSidebarButton"] {opacity:1 !important}
    .topbar {display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;padding:2px 0}
    .topbar b {font-size:20px;color:#191919;letter-spacing:.5px} .topbar span {font-size:12.5px;color:#999}
    .panel-h {font-size:13px;color:#7a8288;font-weight:600;letter-spacing:.5px;margin:4px 0 6px}
    .ccard {background:#fff;border:1px solid #e5e5e5;border-radius:10px;padding:10px 12px;margin:6px 0 4px}
    .ccard .row {display:flex;gap:12px;align-items:center}
    .avatar {width:44px;height:44px;border-radius:6px;background:#07c160;color:#fff;font-size:20px;font-weight:600;
             display:flex;align-items:center;justify-content:center;flex:none}
    .avatar.ca {background:#576b95}
    .cname {font-size:16px;font-weight:600;color:#191919} .cmeta {font-size:12.5px;color:#888}
    .kv {font-size:12.5px;color:#555;margin-top:6px;line-height:1.6} .kv b {color:#191919;font-weight:600}
    .tag {display:inline-block;background:#f2f2f2;color:#555;border-radius:4px;padding:0 6px;margin:2px 3px 0 0;font-size:12px}
    .tag.warn {background:#fdecea;color:#c0392b}
    .chatbox {background:#ededed;border-radius:10px;padding:10px 10px 4px;max-height:340px;overflow-y:auto;margin-bottom:10px}
    .tstamp {text-align:center;font-size:11.5px;color:#9a9a9a;margin:6px 0}
    .bline {display:flex;margin:6px 0;gap:8px;align-items:flex-start} .bline.me {flex-direction:row-reverse}
    .bline .avatar {width:32px;height:32px;font-size:14px;border-radius:4px}
    .bub {max-width:78%;padding:8px 11px;border-radius:6px;font-size:14px;line-height:1.55;color:#191919;
          background:#fff;white-space:pre-wrap;word-break:break-word}
    .bline.me .bub {background:#95ec69}
    .risk {border-radius:8px;padding:10px 14px;margin:4px 0 10px;font-size:14px;line-height:1.6}
    .risk.ok {background:#e9f7ef;border-left:4px solid #07c160} .risk.caution {background:#fff6e0;border-left:4px solid #f0a020}
    .risk.hold {background:#fdecea;border-left:4px solid #e64340}
    .kc {font-size:13px;color:#576b95;margin-top:6px}
    .cand {background:#fff;border:1px solid #e5e5e5;border-radius:10px;padding:12px 14px 4px;margin-bottom:6px}
    .cand.draft {border-style:dashed;opacity:.82}
    .cand-h {display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
    .opt {font-size:12px;color:#999} .lbl {display:inline-block;background:#e7f8ee;color:#06ad56;border-radius:4px;
          padding:1px 8px;font-size:13px;font-weight:600;margin-left:6px}
    .badge {font-size:11.5px;color:#999;border:1px solid #ddd;border-radius:999px;padding:0 8px}
    .badge.final {color:#06ad56;border-color:#b9e8cc}
    .preview {background:#ededed;border-radius:8px;padding:8px}
    .note {color:#666;font-size:13px;line-height:1.55;margin:8px 0 6px;padding-left:8px;border-left:2px solid #d9d9d9}
    .ctx {font-size:13px;line-height:1.65;color:#444;white-space:pre-wrap}
    .ctx-h {font-weight:600;color:#191919;margin-top:8px} .ctx-h2 {font-weight:600;color:#576b95;margin-top:10px}
    .empty {background:#f7f7f7;border:1px dashed #ddd;border-radius:10px;padding:28px 18px;color:#888;font-size:14px;text-align:center}
    </style>""",
    unsafe_allow_html=True,
)

esc = html.escape


@st.cache_data
def load_cases() -> dict[str, dict]:
    out = {}
    for f in sorted((ROOT / "data/cases").glob("C*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        d.pop("test_meta", None)  # evaluation-only
        out[f.stem] = d
    return out


IMPORT_PROMPT = """你把 CA 用自然语言写的客户情况，整理成下面 JSON 结构（只输出 JSON）。
不知道的字段省略；不要编造输入中没有的信息。scenario 只能是：{scenarios}。
日期格式 YYYY-MM-DD；聊天记录 sender 只能是 ca 或 client。
参考结构（字段含义见注释，不要输出注释）：
{example}"""


def import_from_text(text: str) -> dict:
    example = json.dumps(load_cases()["C10"], ensure_ascii=False, indent=1)
    spec = parse_spec("openai" if os.environ.get("OPENAI_API_KEY") else "gemini")
    return chat_json(spec, IMPORT_PROMPT.format(scenarios=", ".join(SCENARIO_LABELS), example=example), text)


def context_html(txt: str) -> str:
    """The prompt context is plain text with '#'/'##' section markers; show those as headings, not raw symbols."""
    out = []
    for line in txt.splitlines():
        s = line.strip()
        if s.startswith("## "):
            out.append(f'<div class="ctx-h2">{esc(s[3:])}</div>')
        elif s.startswith("# "):
            out.append(f'<div class="ctx-h">{esc(s[2:])}</div>')
        elif s:
            out.append(f"<div>{esc(line)}</div>")
    return '<div class="ctx">' + "".join(out) + "</div>"


def refill(case_dict: dict) -> None:
    st.session_state["case_json"] = json.dumps(case_dict, ensure_ascii=False, indent=2)
    st.session_state["ver"] = st.session_state.get("ver", 0) + 1  # fresh widget keys -> fields refill
    st.session_state.pop("result", None)


# ---------------- language (top-right of main, so it works with the sidebar collapsed) ----------------
cases = load_cases()
head_l, head_r = st.columns([8, 1], vertical_alignment="center")
lang = st.session_state.setdefault("lang", "zh")
if head_r.button(T[lang]["switch"], icon=":material/translate:", type="tertiary", help="中文 / English"):
    st.session_state["lang"] = "en" if lang == "zh" else "zh"
    st.rerun()  # redraw the button with the other label
t = T[lang]
scen_label = (lambda s: SCENARIO_EN[s]) if lang == "en" else (lambda s: SCENARIO_LABELS[s])


def honorific(c: dict) -> str:
    if lang == "en":
        return f"{'Ms' if c.get('gender') == '女' else 'Mr'} {c.get('surname', '')}"
    return f"{c.get('surname', '')}{'女士' if c.get('gender') == '女' else '先生'}"


# ---------------- sidebar (collapsible: « at its top-right, » to reopen) ----------------
with st.sidebar:
    st.caption(t["subtitle"])
    pick = st.selectbox(t["load_case"], list(cases), index=list(cases).index("C38"),
                        format_func=lambda k: f"{k} · {scen_label(cases[k]['scenario'])} · {honorific(cases[k]['client'])}")
    if st.button(t["load_btn"], use_container_width=True):
        refill(cases[pick])
    # DEMO_DEFAULT_MODEL (secret/env): which provider is pre-selected. On Streamlit Cloud Gemini returns 503
    # from that network while OpenAI works, so the hosted demo sets it to "openai"; locally Gemini stays default.
    default_p = os.environ.get("DEMO_DEFAULT_MODEL", "gemini")
    model_label = st.radio(t["model"], list(MODELS), index=list(MODELS.values()).index(default_p) if default_p in MODELS.values() else 0,
                           format_func=lambda m: m + (t["recommended"] if MODELS[m] == "gemini" else ""),
                           help=t["model_help"])
    run_counter = st.empty()
    with st.expander(t["free_title"]):
        free = st.text_area(t["free_ph"], height=150, label_visibility="collapsed", placeholder=t["free_ph"])
        if st.button(t["free_btn"], disabled=not free.strip()):
            with st.spinner(t["free_wait"]):
                try:
                    refill(import_from_text(free))
                except Exception as e:  # show, don't crash the demo
                    st.error(t["free_err"].format(e=e))

if "case_json" not in st.session_state:
    st.session_state["case_json"] = json.dumps(cases["C38"], ensure_ascii=False, indent=2)
try:
    base = json.loads(st.session_state["case_json"])
except json.JSONDecodeError:
    base = cases["C38"]
v = st.session_state.get("ver", 0)

head_l.markdown(
    f'<div class="topbar"><b>{t["title"]}</b><span>v4 · {esc(model_label)} · {t["msg_lang"]}</span></div>',
    unsafe_allow_html=True,
)

left, right = st.columns([1, 1.25], gap="large")

# ---------------- left: client, chat, compose ----------------
with left:
    card_ph = st.container()   # filled after the (folded) JSON editor below is read
    chat_ph = st.container()

    st.markdown(f'<div class="panel-h">{t["compose"]}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.4, 1])
    scen_keys = list(SCENARIO_LABELS)
    scenario_ph, today_ph = c1.empty(), c2.empty()
    ca_request = st.text_input(t["request"], base.get("ca_request") or "", placeholder=t["request_ph"], help=t["request_help"], key=f"req{v}")
    ca_draft = st.text_area(t["draft"], base.get("ca_draft") or "", height=68, placeholder=t["draft_ph"], help=t["draft_help"], key=f"draft{v}")
    with st.expander(t["advanced"]):
        occasion = st.text_input(t["occasion"], base.get("occasion") or "", key=f"occasion{v}")
        st.caption(t["json"])
        raw = st.text_area("case JSON", st.session_state["case_json"], height=360, label_visibility="collapsed", key=f"raw{v}")
        ctx_ph = st.empty()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = base
    cl, ca = data.get("client", {}) or {}, data.get("ca", {}) or {}
    today_default = data.get("today", "2026-11-06")
    scenario = scenario_ph.selectbox(t["scenario"], scen_keys,
                                     index=scen_keys.index(data.get("scenario", "birthday_festive")),
                                     format_func=scen_label, key=f"scenario{v}")
    today = today_ph.text_input(t["today"], today_default, key=f"today{v}")

    # compact client card; the long fields fold away
    if cl:
        meta = " · ".join(filter(None, [cl.get("age_range"), cl.get("city"), cl.get("occupation")]))
        tags = [cl.get("stage"), cl.get("spend_band"), t["since"].format(d=cl["client_since"]) if cl.get("client_since") else None]
        warn = [k for k, val in (cl.get("flags") or {}).items() if val]
        tag_html = "".join('<span class="tag">' + esc(str(x)) + "</span>" for x in tags if x)
        tag_html += "".join('<span class="tag warn">' + t["sensitive"] + ": " + esc(k) + "</span>" for k in warn)
        full = cl.get("surname", "") + (cl.get("given_name") or "")
        with card_ph:
            st.markdown(
                f'<div class="ccard"><div class="row"><div class="avatar">{esc(cl.get("surname", "?"))}</div><div>'
                f'<div class="cname">{esc(honorific(cl))} <span class="cmeta">{esc(full)}</span></div>'
                f'<div class="cmeta">{esc(meta)}</div><div>{tag_html}</div></div></div></div>',
                unsafe_allow_html=True,
            )
            owned = "；".join(f"{p.get('item')}（{p.get('date')}{'，' + p['for_whom'] if p.get('for_whom') else ''}）"
                             for p in cl.get("owned_pieces", []))
            details = [(t["owned"], owned), (t["interests"], "、".join(cl.get("interests", []))),
                       (t["habit"], "，".join(filter(None, [cl.get("formality"), cl.get("reply_habit")]))),
                       (t["family"], cl.get("family_notes")), (t["notes"], cl.get("notes"))]
            with st.expander(t["profile_more"]):
                st.markdown("".join(f'<div class="kv"><b>{k}</b>　{esc(val)}</div>' for k, val in details if val),
                            unsafe_allow_html=True)

    # chat history, WeChat style
    rows, last_day = [], None
    for m in data.get("conversation_history", []):
        day = m.get("time", "")[:10]
        if day != last_day:
            try:
                rel = f" · {ago(today, day)}"
            except Exception:
                rel = ""
            rows.append(f'<div class="tstamp">{esc(m.get("time", ""))}{esc(rel)}</div>')
            last_day = day
        me = m.get("sender") == "ca"
        av = (ca.get("name") or "CA")[:1] if me else cl.get("surname", "?")
        rows.append(f'<div class="bline{" me" if me else ""}"><div class="avatar{" ca" if me else ""}">{esc(av)}</div>'
                    f'<div class="bub">{esc(m.get("text", ""))}</div></div>')
    chat_ph.markdown('<div class="chatbox">' + ("".join(rows) or f'<div class="tstamp">{t["no_chat"]}</div>') + "</div>",
                     unsafe_allow_html=True)

    case_err = None
    try:
        data = dict(data)
        data.update(scenario=scenario, today=today, occasion=occasion or None, ca_request=ca_request or None, ca_draft=ca_draft or None)
        case = CaseInput.model_validate(data)
    except Exception as e:
        case, case_err = None, str(e)
    if case:
        with ctx_ph.container():
            st.caption(t["context"])
            st.markdown(context_html(render_case(case, calendar=True)), unsafe_allow_html=True)
    else:
        st.error(t["bad_input"].format(e=case_err))


# ---------------- right: candidates ----------------
def render_candidates(cands: list[Candidate], checks: list[dict] | None, final: bool, ca_name: str, client_name: str) -> None:
    for i, c in enumerate(cands, 1):
        badge = "" if final else f'<span class="badge">{t["draft_badge"]}</span>'
        st.markdown(
            f'<div class="cand{"" if final else " draft"}"><div class="cand-h"><div><span class="opt">{t["option"].format(i=i)}</span>'
            f'<span class="lbl">{esc(c.strategy)}</span></div>{badge}</div>'
            f'<div class="preview"><div class="bline me"><div class="avatar ca">{esc(ca_name[:1])}</div>'
            f'<div class="bub">{esc(c.text)}</div></div></div>'
            f'<div class="note"><b>{t["note"]}</b>：{esc(c.note_for_ca)}</div></div>',
            unsafe_allow_html=True,
        )
        if final:
            with st.popover(t["copy"], icon=":material/content_copy:"):
                st.code(c.text, language=None, wrap_lines=True)  # st.code has a copy button
            chk = (checks or [{}])[i - 1] if checks and i - 1 < len(checks) else {}
            if chk and not chk.get("pass", True):
                st.warning(t["rule"].format(x="；".join(chk.get("hard", []))))


def render_risk(level: str, flags: list[str], advice: str, key_choice: str | None) -> None:
    lv = level if level in t["risk"] else "caution"
    color = {"ok": "green", "caution": "orange", "hold": "red"}[lv]
    icon = {"ok": ":material/check_circle:", "caution": ":material/warning:", "hold": ":material/block:"}[lv]
    with st.expander(f":{color}[**{t['risk'][lv]}**] · {t['risk_more']}", icon=icon, expanded=lv == "hold"):
        if advice:
            st.markdown(advice)
        if flags:
            st.caption(f"{t['risk_flags']}：{'；'.join(flags)}")
        if key_choice:
            st.caption(f"{t['key_choice']}：{key_choice}")


with right:
    runs = st.session_state.get("runs", 0)
    go = st.button(t["generate"], type="primary", use_container_width=True,
                   disabled=case is None or runs >= MAX_RUNS_PER_SESSION)
    if runs >= MAX_RUNS_PER_SESSION:
        st.info(t["quota"])
    status_ph, out_ph = st.empty(), st.empty()
    ca_name = (case.ca.name if case else ca.get("name")) or "CA"
    client_name = honorific(cl) if cl else ""

    if go and case:
        st.session_state.pop("result", None)
        t0, marks, live = time.time(), {}, {"plan": {}}
        status_ph.caption(":material/hourglass_top: " + t["s_plan"])

        def on_progress(stage: str, payload) -> None:
            if stage == "plan":
                live["plan"] = payload
                return
            cands = payload if stage == "draft" else payload["candidates"]
            if stage == "draft":
                marks["draft"] = round(time.time() - t0, 1)
                status_ph.caption(":material/hourglass_top: " + t["s_draft"] + f"（{marks['draft']} s）")
            else:
                status_ph.caption(":material/hourglass_top: " + t["s_rewrite"].format(r=payload["round"], i="、".join(str(x + 1) for x in payload["fixed"])))
            r = live["plan"].get("risk") or {}
            with out_ph.container():
                render_risk(r.get("level", "caution"), r.get("flags", []), r.get("advice", ""), live["plan"].get("key_choice"))
                render_candidates(cands, None, False, ca_name, client_name)

        # if the chosen provider is down (e.g. Gemini 503 "overloaded"), fall back to the other one when its key exists
        primary = MODELS[model_label]
        order = [primary] + [p for p in MODELS.values() if p != primary and os.environ.get(KEY_ENV[p])]
        err = None
        for n, provider in enumerate(order):
            if n:
                t0 = time.time()
                status_ph.caption(":material/swap_horiz: " + t["fallback"].format(m=provider))
            try:
                res = generate(case, parse_spec(provider), "v4", on_progress=on_progress, note_lang=lang)
                res.trace["first_draft_seconds"] = marks.get("draft")
                res.trace["fallback_from"] = primary if n else None
                st.session_state["result"] = res
                st.session_state["runs"] = runs + 1
                err = None
                break
            except Exception as e:
                err = e
        if err:
            busy = any(f"Error code: {c}" in str(err) for c in (429, 500, 502, 503, 504))
            status_ph.error(t["s_busy"] if busy else f"{t['s_fail']}：{err}")

    res = st.session_state.get("result")
    if res:
        subs = sorted({c.get("served") for c in res.trace.get("calls", []) if c.get("served") and c.get("served") != c.get("requested")})
        status_ph.caption(":material/schedule: " + t["s_done"].format(s=res.trace.get("seconds"), d=res.trace.get("first_draft_seconds") or "—")
                          + (t["subbed"].format(m="、".join(subs)) if subs else ""))
        plan = res.trace.get("plan", {})
        with out_ph.container():
            render_risk(res.risk.level, res.risk.flags, res.risk.advice, plan.get("key_choice"))
            render_candidates(res.candidates, res.checks, True, ca_name, client_name)
            with st.expander(t["process"]):
                st.json({t["plan"]: plan,
                         t["rounds"]: [{"to_fix": r.get("to_fix")} for r in res.trace.get("rounds", [])],
                         t["calls"]: res.trace.get("calls")}, expanded=False)
    elif not go:
        out_ph.markdown(f'<div class="empty">{t["empty"]}</div>', unsafe_allow_html=True)

run_counter.caption(t["runs"].format(n=st.session_state.get("runs", 0), m=MAX_RUNS_PER_SESSION))
