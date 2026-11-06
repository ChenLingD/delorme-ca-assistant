"""Loads the brand knowledge (brand book, rules, catalog, playbooks) and renders a case into prompt text."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from .calendar_cn import ago, context as calendar_context
from .schemas import SCENARIO_LABELS, CaseInput

ROOT = Path(__file__).resolve().parent.parent


@lru_cache
def brand_book() -> str:
    return (ROOT / "brand" / "brand_book.md").read_text(encoding="utf-8")


@lru_cache
def rules() -> dict:
    return yaml.safe_load((ROOT / "brand" / "rules.yaml").read_text(encoding="utf-8"))


@lru_cache
def catalog() -> dict:
    return yaml.safe_load((ROOT / "brand" / "catalog.yaml").read_text(encoding="utf-8"))


@lru_cache
def playbooks() -> dict:
    return yaml.safe_load((ROOT / "playbooks" / "scenarios.yaml").read_text(encoding="utf-8"))


def product(sku: str) -> dict | None:
    return next((p for p in catalog()["products"] if p["sku"] == sku), None)


def event(event_id: str) -> dict | None:
    return next((e for e in catalog()["events"] if e["id"] == event_id), None)


def render_product(p: dict) -> str:
    col = catalog()["collections"][p["collection"]]
    craft = f"｜工艺：{p['craft']}" if p.get("craft") else ""
    return f"- [{p['sku']}] {p['name']}｜¥{p['price']:,}｜系列：{col['name']}（{col['tier']}）｜{p['details']}{craft}"


def render_playbook(scenario: str) -> str:
    pb = playbooks()[scenario]
    lines = [f"场景：{pb['name']}", f"目标：{pb['goal']}", "好的做法："]
    lines += [f"  - {x}" for x in pb["do"]]
    lines.append("避免：")
    lines += [f"  - {x}" for x in pb["avoid"]]
    lines.append("常用的三种切入角度（可参考，可调整）：")
    lines += [f"  - {x}" for x in pb["angles"]]
    return "\n".join(lines)


def catalog_overview(include_allocated: bool) -> str:
    """Product list the model may draw on for recommendations."""
    out = []
    for p in catalog()["products"]:
        if not include_allocated and p["collection"] in ("etoile", "nuits_vendome"):
            continue
        out.append(render_product(p))
    return "\n".join(out)


def _kv(label: str, value) -> str | None:
    if value in (None, "", [], False):
        return None
    if isinstance(value, list):
        value = "、".join(str(v) for v in value)
    return f"- {label}：{value}"


def render_case(case: CaseInput, calendar: bool = False) -> str:
    c, ca, f = case.client, case.ca, case.client.flags
    name = c.surname + ("女士" if c.gender == "女" else "先生")
    parts = [f"# 今天日期：{case.today}", f"# 场景：{SCENARIO_LABELS[case.scenario]}"]
    if case.occasion:
        parts.append(f"# 场景补充：{case.occasion}")
    if case.ca_request:
        parts.append(f"# CA 的额外要求：{case.ca_request}")
    if case.ca_draft:
        parts.append(f"# CA 想说的要点 / 草稿（以此为准）：{case.ca_draft}")
    if calendar:
        parts.append("\n## 日历（由系统计算，可信）\n" + calendar_context(case.today))
        parts.append("\n## 时间线（由系统计算，距今多久）\n" + timeline(case))

    parts.append("\n## CA（发消息的人）")
    parts += filter(None, [
        _kv("姓名", ca.name), _kv("性别", ca.gender), _kv("从业年限", f"{ca.years_experience} 年"),
        _kv("门店", ca.store),
        _kv("与该客户认识自", ca.known_client_since or "刚接手 / 尚未建立联系"),
        _kv("个人说话风格", ca.style),
    ])

    parts.append("\n## 客户档案")
    owned = [f"{p.date} {p.item}" + (f"（{p.for_whom}）" if p.for_whom else "") + (f"，{p.note}" if p.note else "")
             for p in c.owned_pieces]
    parts += filter(None, [
        _kv("称呼", name + (f"（名：{c.given_name}）" if c.given_name else "")),
        _kv("年龄段", c.age_range), _kv("城市", c.city), _kv("职业/行业", c.occupation),
        _kv("成为客户自", c.client_since or "尚未购买"), _kv("累计消费区间（内部，勿提及）", c.spend_band),
        _kv("进阶阶段（内部，勿提及）", c.stage), _kv("最近到店", c.last_visit), _kv("最近购买", c.last_purchase),
        _kv("财富来源（内部）", c.wealth_source), _kv("购买动机", c.motivations),
        _kv("社交曝光度", c.social_visibility), _kv("价格敏感度", c.price_sensitivity),
        _kv("审美偏好", c.style_preference), _kv("材质偏好", c.material_preference),
        _kv("已有作品", owned), _kv("尺寸", c.sizes),
        _kv("沟通正式度", c.formality), _kv("回复习惯", c.reply_habit),
        _kv("对推荐的接受度", c.recommendation_openness), _kv("方便联系的时段", c.preferred_contact_time),
        _kv("生日", c.birthday), _kv("重要日期", c.important_dates), _kv("家人", c.family_notes),
        _kv("兴趣", c.interests), _kv("CA 手记", c.notes),
    ])
    sens = list(filter(None, [
        "付款人与佩戴者不是同一人（礼赠关系，严格保密，消息中绝不提及付款人）" if f.payer_not_wearer else None,
        "存在转售风险（配额作品需谨慎）" if f.resale_risk else None,
        f"未解决的投诉：{f.open_complaint}" if f.open_complaint else None,
        f"近期家庭变故：{f.recent_bereavement}" if f.recent_bereavement else None,
        "客户已明确表示不希望收到推销信息" if f.opted_out_marketing else None,
        f.other,
    ]))
    if sens:
        parts.append("\n## 敏感标记（内部）")
        parts += [f"- {s}" for s in sens]

    parts.append("\n## 聊天记录（由早到晚）")
    if case.conversation_history:
        for m in case.conversation_history:
            who = f"CA {ca.name}" if m.sender == "ca" else name
            parts.append(f"[{m.time}] {who}：{m.text}")
    else:
        parts.append("（无聊天记录）")

    if case.product_skus:
        parts.append("\n## 本次相关作品")
        for sku in case.product_skus:
            p = product(sku)
            parts.append(render_product(p) if p else f"- {sku}（目录中未找到）")
    if case.event_id:
        e = event(case.event_id)
        if e:
            parts.append("\n## 活动资料")
            parts.append(f"- {e['name']}｜{e['date']}｜{e['place']}｜{e['content']}")
    return "\n".join(parts)


def timeline(case: CaseInput) -> str:
    """Elapsed time for the things a message might follow up on, so the model knows what is recent."""
    t, c = case.today, case.client
    hist = case.conversation_history
    rows = []
    if hist:
        rows.append(f"- 上一条聊天消息：{hist[-1].time[:10]}，{ago(t, hist[-1].time)}")
        last_client = next((m for m in reversed(hist) if m.sender == "client"), None)
        if last_client:
            rows.append(f"- 客户最后一次发消息：{last_client.time[:10]}，{ago(t, last_client.time)}")
    for label, v in (("最近到店", c.last_visit), ("最近购买", c.last_purchase)):
        if v and ago(t, v):
            rows.append(f"- {label}：{v}，{ago(t, v)}")
    for p in c.owned_pieces:
        if ago(t, p.date):
            rows.append(f"- {p.item}：{p.date} 购入，{ago(t, p.date)}" + (f"（{p.note}）" if p.note else ""))
    rows.append("提示：超过 1 个月的事，不要当作“刚发生”去追问感受。")
    return "\n".join(rows)
