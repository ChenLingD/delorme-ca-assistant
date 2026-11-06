"""Deterministic rule checks on a single candidate message, plus a cross-candidate similarity check."""
from __future__ import annotations

import re

from .knowledge import rules

_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF⭐‼⁉]"
)


def char_len(text: str) -> int:
    return len(re.sub(r"\s", "", text))


# v2: “承诺性内容”只能来自 CA 输入（要点 / 额外要求）
_COMMIT_PATTERNS = [
    (re.compile(r"小礼物|礼遇|伴手礼|(为您|给您|帮您)(准备|备)|备了一份|一份心意|一点心意|小心意"), "礼物/礼遇"),
    (re.compile(r"(为|帮|给)您(预)?留(了|着)?(一份|一个|一只|一条|名额|位置)|留了一份|留着一份|预留"), "预留"),
    (re.compile(r"\d{1,2}\s*[点:：]\s*\d{0,2}\s*分?\s*(前|之前)|今天之内|今晚之前|今晚前|明天(上午|下午)?(前|之前)"), "具体时间承诺"),
    (re.compile(r"名额|座位|位置给您|排上|排到"), "名额/排位"),
]
SLOT_MAX = {"极简": 35}


def check_message(text: str, scenario: str, ca_input: str | None = None, slot: str | None = None) -> dict:
    r = rules()
    hard: list[str] = []
    soft: list[str] = []

    for group, terms in r["banned_terms"].items():
        hits = [t for t in terms if t in text]
        if hits:
            hard.append(f"禁用词[{group}]：{'、'.join(hits)}")

    emojis = _EMOJI_RE.findall(text)
    bad_emoji = [e for e in emojis if e in r["banned_emoji"]]
    if bad_emoji:
        hard.append(f"营销类 emoji：{''.join(bad_emoji)}")
    if emojis and scenario not in r["emoji_allowed_scenarios"]:
        hard.append(f"该场景不应使用 emoji：{''.join(emojis)}")
    elif len(emojis) > r["max_emoji"]:
        hard.append(f"emoji 超过 {r['max_emoji']} 个")

    excl = text.count("！") + text.count("!")
    if excl > r["max_exclamation"]:
        hard.append(f"感叹号 {excl} 个（上限 {r['max_exclamation']}）")
    punct = [p for p in r["forbidden_punct"] if p in text]
    if punct:
        hard.append(f"禁用标点/排版：{' '.join(punct)}")

    lim = r["length"].get(scenario, r["length"]["default"])
    n = char_len(text)
    if n > lim["max"]:
        hard.append(f"过长：{n} 字（上限 {lim['max']}）")
    if n < lim["min"]:
        hard.append(f"过短：{n} 字")

    if ca_input is not None:  # v2 only
        for pat, label in _COMMIT_PATTERNS:
            m = pat.search(text)
            if m and not pat.search(ca_input):
                hard.append(f"擅自承诺（{label}）：“{m.group(0)}”不在 CA 提供的信息中")
    if slot in SLOT_MAX and n > SLOT_MAX[slot]:
        hard.append(f"“{slot}”应不超过 {SLOT_MAX[slot]} 字，现为 {n} 字")
    if slot == "极简" and re.search(r"\d", text):
        hard.append("“极简”不应包含数字、时间或价格等细节")

    cl = [c for c in r["cliches"] if c in text]
    if cl:
        soft.append(f"陈词：{'、'.join(cl)}")

    return {"pass": not hard, "hard": hard, "soft": soft, "length": n}


def _ngrams(text: str, n: int = 3) -> set[str]:
    t = re.sub(r"[\s，。、！？：；“”‘’（）,.!?]", "", text)
    return {t[i : i + n] for i in range(len(t) - n + 1)}


def jaccard(a: str, b: str, n: int = 3) -> float:
    A, B = _ngrams(a, n), _ngrams(b, n)
    return len(A & B) / len(A | B) if A and B else 0.0


def diversity(texts: list[str]) -> float:
    """Max pairwise char-trigram Jaccard among candidates (lower = more diverse)."""
    sims = [jaccard(texts[i], texts[j]) for i in range(len(texts)) for j in range(i + 1, len(texts))]
    return max(sims) if sims else 0.0


_SALUTE = re.compile(r"^[一-龥A-Za-z]{1,4}(女士|先生)[，,、 ]*")


def sameness(texts: list[str]) -> list[str]:
    """v2: flag candidates that share an opening or a closing — the structural sameness CAs notice first."""
    issues = []
    heads = [_SALUTE.sub("", t.strip())[:4] for t in texts]  # compare what follows the salutation
    tails = [re.sub(r"[。！？!?.，,\s]+$", "", t.strip())[-5:] for t in texts]
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if heads[i] and heads[i] == heads[j]:
                issues.append(f"候选 {i+1} 和 {j+1} 开头相同（“{heads[i]}”）")
            if tails[i] and tails[i] == tails[j]:
                issues.append(f"候选 {i+1} 和 {j+1} 结尾相同（“{tails[i]}”）")
    return issues
