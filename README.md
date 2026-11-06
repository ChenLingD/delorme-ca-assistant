# Maison Delorme · CA 话术助手

为奢侈品客户顾问（CA）起草微信消息的工具：输入客户信息、场景、聊天记录与相关作品，输出 **三条可选的中文微信候选**，每条附一个情境化的策略标签和“给 CA 的备注”（取舍与风险），并在生成前给出时机与风险提醒。

品牌 **Maison Delorme 德洛姆** 及其产品、门店、客户、对话全部为虚构。

## 快速开始

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # macOS/Linux: .venv/bin/pip
echo GEMINI_API_KEY=... > .env                                            # 可选：OPENAI_API_KEY
streamlit run app.py                                                      # 网页 demo
python -m delorme.cli data/cases/C38.json --model gemini --version v4     # 命令行
```

## 它怎么工作（v4，冻结版本）

```
输入（客户档案 · 场景 · 聊天记录 · 作品/活动 · 可选的 CA 要点）
   │
   ├─ 事实工具层（代码计算，可信）：日历/节气/节日 · 时间线（距今多久） · 目录与品牌固定服务
   ▼
1. 分析：读懂客户与关系 → 风险分级（ok / caution / hold）→ 判断 CA 此刻真正要做的选择 → 规划三个不同方向
2. 写作：按三个方向各写一条，附标签与给 CA 的备注
3. 质检：规则检查（禁用词、擅自承诺、长度…）+ LLM 质检（承诺、红线、隐私、情境、语气、雷同）
4. 改写：只改不合格的那几条，最多 3 轮
   ▼
输出：风险提醒 + 三条候选（标签 · 正文 · 给 CA 的备注）
```

唯一的硬线：**不替 CA 做 CA 没做过的承诺**（礼物、预留、时间、名额、安排、价格让步；对作品/服务的说法只用资料里有的）。其余交给模型判断，取舍写进备注交给 CA。

## 目录

| 路径 | 内容 |
|---|---|
| `brand/` | 品牌手册、产品/活动/门店目录、可机检规则（`archive/` 为历史版本） |
| `playbooks/scenarios.yaml` | 六个场景的策略手册 |
| `delorme/` | 工具代码：`pipeline.py`（v0–v4）、`prompts.py`、`checks.py`、`calendar_cn.py`、`judge.py`、`llm.py`（多厂商） |
| `data/test_matrix.yaml` | 50 条测试用例的设计矩阵（含 must / must_not） |
| `data/cases/` | 50 条测试用例输入 |
| `runs/` | 各版本、各模型的输出与评分 |
| `scripts/` | 批量运行、judge、报告、导出 |
| `docs/` | 工作日志、关键决策、缺陷记录、进度 |
| `app.py` | Streamlit demo |

## 版本

| 版本 | 要点 |
|---|---|
| v0 | 单 prompt 基线（对照组） |
| v1 | 分析 → 三角度生成 → 规则 + LLM 质检 → 定向改写 |
| v2 | 固定“极简/走心/推进”、承诺只来自 CA、日历工具、风险分级 |
| v3 / v3.1 | 取消硬字数、禁“不用回复”类空话、时间线工具、绕开无解问题、内容层面差异化 |
| **v4** | 三条的区分方向由模型按情境判断；唯一硬线是不替 CA 承诺；备注写明取舍与风险 |

## 部署（Streamlit Community Cloud）

1. 把本仓库推到 GitHub（`.env` 已被 `.gitignore` 排除）。
2. 在 share.streamlit.io 新建 app，入口选 `app.py`。
3. Advanced settings → Secrets 填 `GEMINI_API_KEY`、`OPENAI_API_KEY`；Streamlit Cloud 上 Gemini 会返回 503，所以再加 `DEMO_DEFAULT_MODEL = "openai"`（可选 `DEMO_MAX_RUNS`）。
4. 部署后的链接无需登录即可访问；每个会话默认最多生成 20 次。
