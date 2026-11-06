"""Grounded calendar context (solar terms, festivals) so the model never guesses seasons or weather.

Dates are Beijing time for 2026-09 .. 2027-03, the window the test set uses.
"""
from __future__ import annotations

from datetime import date

SOLAR_TERMS = [
    ("2026-09-07", "白露"), ("2026-09-23", "秋分"), ("2026-10-08", "寒露"), ("2026-10-23", "霜降"),
    ("2026-11-07", "立冬"), ("2026-11-22", "小雪"), ("2026-12-07", "大雪"), ("2026-12-22", "冬至"),
    ("2027-01-05", "小寒"), ("2027-01-20", "大寒"), ("2027-02-04", "立春"), ("2027-02-19", "雨水"),
    ("2027-03-06", "惊蛰"), ("2027-03-21", "春分"),
]
FESTIVALS = [
    ("2026-09-25", "中秋节"), ("2026-10-01", "国庆节"), ("2026-10-18", "重阳节"),
    ("2026-12-24", "平安夜"), ("2026-12-25", "圣诞节"), ("2027-01-01", "元旦"),
    ("2027-02-05", "除夕"), ("2027-02-06", "春节（农历正月初一）"), ("2027-02-14", "情人节"),
    ("2027-02-20", "元宵节"), ("2027-03-08", "妇女节"),
]
_WEEK = "一二三四五六日"


def _d(s: str) -> date:
    return date.fromisoformat(s)


def context(today: str) -> str:
    t = _d(today)
    lines = [f"今天：{today}（星期{_WEEK[t.weekday()]}）"]
    past = [(d, n) for d, n in SOLAR_TERMS if _d(d) <= t]
    nxt = next(((d, n) for d, n in SOLAR_TERMS if _d(d) > t), None)
    if past:
        d, n = past[-1]
        gap = (t - _d(d)).days
        lines.append(f"节气：今天是{n}" if gap == 0 else f"节气：{n}（{d[5:]}）后第 {gap} 天")
    if nxt:
        lines.append(f"下一个节气：{nxt[1]}，{nxt[0][5:]}（{(_d(nxt[0]) - t).days} 天后）")
    near = [(d, n) for d, n in FESTIVALS if 0 <= (_d(d) - t).days <= 21]
    if near:
        lines.append("近期节日：" + "；".join(f"{n} {d[5:]}" + ("（今天）" if _d(d) == t else f"（{(_d(d) - t).days} 天后）") for d, n in near))
    lines.append("注意：节气是历法概念，不代表天气；不要描述具体天气或气温。")
    return "\n".join(lines)


def ago(today: str, when: str | None) -> str | None:
    """'2026-06-14 17:20' / '2026-06' -> '157 天前（约 5 个月）'."""
    if not when:
        return None
    s = when.strip()[:10]
    if len(s) == 7:  # YYYY-MM
        s += "-15"
    try:
        days = (_d(today) - _d(s)).days
    except ValueError:
        return None
    if days < 0:
        return None
    if days < 45:
        return f"{days} 天前"
    months = round(days / 30.4)
    return f"约 {months} 个月前" if months < 24 else f"约 {days / 365:.1f} 年前"
