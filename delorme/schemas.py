"""Input / output data models for the Delorme CA message tool."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Scenario = Literal[
    "birthday_festive",
    "product_recommendation",
    "post_purchase",
    "reactivation",
    "event_invitation",
    "price_objection",
]

SCENARIO_LABELS = {
    "birthday_festive": "生日与节日祝福",
    "product_recommendation": "产品推荐",
    "post_purchase": "售后关怀",
    "reactivation": "沉睡客户唤醒",
    "event_invitation": "活动邀约",
    "price_objection": "价格异议",
}


class CAProfile(BaseModel):
    name: str
    gender: Literal["女", "男"] = "女"
    years_experience: int = 3
    store: str = "上海恒隆广场精品店"
    known_client_since: Optional[str] = None  # e.g. "2021-05"; None = 新接手/刚认识
    style: Literal["偏正式", "偏亲切", "适中"] = "适中"


class Purchase(BaseModel):
    date: str
    item: str  # product name or SKU
    for_whom: Optional[str] = None  # "自戴" / "送给母亲" ...
    note: Optional[str] = None


class SensitiveFlags(BaseModel):
    payer_not_wearer: bool = False  # 付款人与佩戴者不是同一人，需保密
    resale_risk: bool = False
    open_complaint: Optional[str] = None  # 未解决投诉的简述
    recent_bereavement: Optional[str] = None  # 近期家庭变故
    opted_out_marketing: bool = False  # 明确拒绝推销
    other: Optional[str] = None


class ClientProfile(BaseModel):
    # 基础
    surname: str
    given_name: Optional[str] = None
    gender: Literal["女", "男"]
    age_range: str  # "25-30"
    city: str
    occupation: Optional[str] = None
    # 关系
    client_since: Optional[str] = None  # "2019-03"; None = 新客
    spend_band: Literal["未购买", "5万以下", "5-30万", "30-100万", "100万以上"] = "未购买"
    stage: Literal["潜在客户", "入门", "核心", "晨星资格"] = "入门"
    last_visit: Optional[str] = None
    last_purchase: Optional[str] = None
    # 财富与动机（中性）
    wealth_source: Literal["家族传承", "创业", "职业收入", "不详"] = "不详"
    motivations: list[str] = Field(default_factory=list)  # 收藏/犒赏自己/社交场合/送礼/保值心态
    social_visibility: Literal["低调", "适中", "会公开分享"] = "适中"
    price_sensitivity: Literal["低", "中", "高"] = "中"
    # 品味
    style_preference: Optional[str] = None
    material_preference: Optional[str] = None
    owned_pieces: list[Purchase] = Field(default_factory=list)
    sizes: Optional[str] = None  # "戒圈 12 号"
    # 沟通偏好
    formality: Literal["正式", "适中", "随意"] = "适中"
    reply_habit: Optional[str] = None  # "很少回复" / "回复很快"
    recommendation_openness: Literal["欢迎", "一般", "反感"] = "一般"
    preferred_contact_time: Optional[str] = None
    # 重要日期与家人
    birthday: Optional[str] = None  # "11-12"
    important_dates: list[str] = Field(default_factory=list)
    family_notes: Optional[str] = None
    interests: list[str] = Field(default_factory=list)
    # 敏感
    flags: SensitiveFlags = Field(default_factory=SensitiveFlags)
    notes: Optional[str] = None  # CA 手记


class Message(BaseModel):
    sender: Literal["ca", "client"]
    time: str
    text: str


class CaseInput(BaseModel):
    case_id: str = "demo"
    scenario: Scenario
    today: str = "2026-11-05"
    occasion: Optional[str] = None  # 节日名 / 活动 id / 场景补充说明
    ca: CAProfile
    client: ClientProfile
    conversation_history: list[Message] = Field(default_factory=list)
    product_skus: list[str] = Field(default_factory=list)  # 场景相关的产品
    event_id: Optional[str] = None
    ca_request: Optional[str] = None  # CA 的额外要求，如“想约她来看珍珠展”
    # 可选：CA 想说的要点或草稿。礼物、时间承诺、名额、安排等“承诺性内容”只能来自这里或 ca_request
    ca_draft: Optional[str] = None
    # 测试元数据（persona / type / must / must_not）：只给评估用，不进入生成 prompt
    test_meta: Optional[dict] = None


class Candidate(BaseModel):
    text: str
    strategy: str
    note_for_ca: str


class RiskAssessment(BaseModel):
    level: Literal["ok", "caution", "hold"] = "ok"
    flags: list[str] = Field(default_factory=list)
    advice: str = ""


class ToolOutput(BaseModel):
    case_id: str
    version: str
    model: str
    risk: RiskAssessment
    candidates: list[Candidate]
    checks: list[dict] = Field(default_factory=list)  # rule-check results per candidate
    trace: dict = Field(default_factory=dict)
