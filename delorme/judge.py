"""LLM-as-judge: scores one tool output (risk + 3 candidates) against the case and its test expectations."""
from __future__ import annotations

from .knowledge import brand_book, catalog_overview, render_case, render_playbook
from .llm import ModelSpec, chat_json
from .schemas import CaseInput, ToolOutput

JUDGE_SYSTEM = """你是奢侈品客户关系领域的资深评审，熟悉中国高端客户的微信沟通。你要评估一个工具为客户顾问（CA）起草的 3 条微信候选消息。
评审要严格、具体、一致；不要因为文字华丽就给高分，真人 CA 在微信上通常说得简短自然。

# 品牌手册（评估依据）
{brand_book}

# 本场景策略
{playbook}

# 作品目录（工具可用的全部作品）
{catalog}
"""

JUDGE_USER = """{case}

# 本用例的评估期望（工具看不到这部分）
- 应做到（must）：{must}
- 绝不能（must_not）：{must_not}

# 工具输出
风险判断：{risk}
{candidates}

请逐条评估 3 条候选，然后评估整体。输出 JSON：
{{
  "candidates": [
    {{
      "index": 1,
      "red_flags": {{
        "brand_violation": "无 / 具体描述（折扣或让价暗示、稀缺紧迫、保值升值、配额门槛、贬低竞品或代购、营销腔 emoji 等）",
        "privacy_violation": "无 / 具体描述（提及付款人、消费金额或等级、他人信息、评价外貌身份等）",
        "fabrication": "无 / 具体描述（编造了输入中没有的事实、政策、时间承诺、产品或活动细节）",
        "context_failure": "无 / 具体描述（无视投诉/拒绝推销/丧亲等情境，没回答客户的问题，与聊天记录脱节）",
        "must_not_hit": "无 / 触犯了哪条 must_not"
      }},
      "scores": {{
        "personalization": 1-5,   // 是否用到这位客户的真实信息，且用得自然
        "brand_voice": 1-5,       // 是否克制、具体、得体，符合德洛姆的说话方式
        "naturalness": 1-5,       // 读起来像真人 CA 发的微信，而不是模板/广告/公文
        "effectiveness": 1-5      // 是否达成本场景目标、推进关系，且 must 项做到了多少
      }},
      "sendability": "直接可发 | 小改可发 | 不可用",
      "comment": "一句话点评"
    }}, ... 共 3 条
  ],
  "set": {{
    "diversity": 1-5,              // 3 条在切入角度、篇幅、语气上是否真正不同（不是同义改写）
    "risk_judgement": "正确 | 偏松 | 偏紧 | 不适用",  // 工具的风险等级与提醒是否恰当
    "best_index": 1-3,
    "must_coverage": "做到的 must 条目 / 总数，如 2/3",
    "summary": "两句话总体评价，指出最主要的问题"
  }}
}}
判断“编造”时：聊天记录里 CA 自己说过的话、目录里的工艺说明、系列故事、日历与时间线都算有依据。
委婉或不完全属实的社交说法，如果已在“给 CA 的备注”里点明，属于 CA 的知情选择，不算编造；没有点明才算。
red_flags 每一项必须以“无”“轻微：”或“严重：”开头。只有 CA 不能发送、或会伤害客户关系/品牌/合规的问题才算“严重”；用词偏多、略显空泛这类风格问题写进 comment，不算红线。
评分锚点：5 = 资深 CA 会写出的水平；3 = 能用但平淡或有小问题；1 = 明显不合格。
任何 red_flags 不为“无”的候选，sendability 不能是“直接可发”。"""


def judge(case: CaseInput, out: ToolOutput, model: ModelSpec) -> dict:
    meta = case.test_meta or {}
    cands = "\n".join(
        f"候选 {i}（策略：{c.strategy}）：{c.text}\n   给 CA 的备注（客户看不到）：{c.note_for_ca}"
        for i, c in enumerate(out.candidates, 1)
    )
    risk = f"{out.risk.level}；{('、'.join(out.risk.flags)) or '无'}；{out.risk.advice or ''}"
    return chat_json(
        model,
        JUDGE_SYSTEM.format(brand_book=brand_book(), playbook=render_playbook(case.scenario), catalog=catalog_overview(True)),
        JUDGE_USER.format(
            case=render_case(case, calendar=True),  # the judge always gets the ground-truth calendar and timeline
            must="；".join(meta.get("must", [])) or "无",
            must_not="；".join(meta.get("must_not", [])) or "无",
            risk=risk,
            candidates=cands,
        ),
    )


def flatten(j: dict) -> dict:
    """Aggregate a judge result into per-output numbers."""
    cands = j.get("candidates", [])
    dims = ["personalization", "brand_voice", "naturalness", "effectiveness"]
    def severity(v) -> int:  # 0 none, 1 minor, 2 major — judges often write "无（但……）" or "轻微：……"
        s = str(v).strip()
        if not s or s.startswith(("无", "None", "否")):
            return 0
        if s.startswith("严重"):
            return 2
        return 1  # "轻微：" and anything not explicitly marked severe

    sev = [max((severity(v) for v in c.get("red_flags", {}).values()), default=0) for c in cands]
    red = sum(s == 2 for s in sev)
    minor = sum(s == 1 for s in sev)
    send = [c.get("sendability", "") for c in cands]
    row = {d: sum(c.get("scores", {}).get(d, 0) for c in cands) / max(len(cands), 1) for d in dims}
    row.update(
        red_flag_candidates=red,
        minor_flag_candidates=minor,
        direct_send=send.count("直接可发"),
        minor_edit=send.count("小改可发"),
        unusable=send.count("不可用"),
        diversity=j.get("set", {}).get("diversity"),
        risk_judgement=j.get("set", {}).get("risk_judgement"),
        must_coverage=j.get("set", {}).get("must_coverage"),
    )
    return row

