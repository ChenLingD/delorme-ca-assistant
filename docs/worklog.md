# Work Log（持续更新）

> 每一步对应一行；截图由人工在关键节点截取，文件放在 `docs/screenshots/`，命名 `step-XX-*.png`。

| Step | What I did | Input | Output | Tool or agent used | Screenshots |
|---|---|---|---|---|---|
| 1 | 明确任务目标与产出 | 任务说明 | 任务理解摘要（6 场景、产出清单、重点、初步方案、时间表） | Claude Code（Claude Opus 5.5） | step-01-understanding.png |
| 2 | 与 AI 讨论方案：品类选择、是否做 demo、模型选择、架构方向、是否开 agent team | 任务理解 + 我的问题 | 4 个品类对比、v0/v1 架构、bake-off + 异族 judge 评估思路、10 个待决问题 | Claude Code | step-02-options.png |
| 3 | 逐条拍板：高级珠宝 / 对标顶级奢侈品配额文化 / 绝不打折 / 3 条候选“策略×篇幅”混合 / CA 备注仅内部可见 / 只做简体 | 10 个待决问题 | 决策清单（见 `docs/decisions.md`）；否决“完整话术 few-shot”（担心重复），改为短语级 do/don't + 重复度指标 | Claude Code | step-03-decisions.png |
| 4 | 设计客户画像：从 7 类真实客群（老钱、AI 新贵、新富、社交需要的上班族、网红、礼赠关系客户、富二代）出发，拆成中性可观察字段 | 我提出的客群类型 | 客户画像字段表 + 客群→字段映射；确立“系统内不出现贬义标签、不流露对客户身份的判断”原则 | Claude Code | step-04-profile.png |
| 5 | 品牌命名与查重；搭建 Python 环境；探测各家 API 可用模型 | 4 个候选品牌名 | 选定 Maison Delorme 德洛姆；uv venv；可用模型清单（OpenAI / Gemini / DeepSeek / Kimi） | Claude Code + WebSearch | step-05-setup.png |
| 6 | 编写品牌知识：顾问沟通手册、产品/活动/门店目录、可机检规则（禁用词、emoji、感叹号、长度、陈词） | 已定决策 | `brand/brand_book.md`、`brand/catalog.yaml`、`brand/rules.yaml` | Claude Code | step-06-brand.png |
| 7 | 编写六个场景的策略手册（目标 / 好做法 / 避免 / 三种默认切入角度） | 品牌手册 | `playbooks/scenarios.yaml` | Claude Code | step-07-playbook.png |
| 8 | 定义输入输出数据结构；实现 v0 单 prompt 基线与 v1 流水线（分析与风险判断 → 按 3 个角度生成 → 规则检查 + LLM 质检 → 定向改写） | 客户画像设计、手册 | `delorme/` 代码包 | Claude Code | step-08-code.png |
| 10 | 选定 bake-off 模型：兼顾前沿能力与性价比；实测 16 个候选模型连通性；验证 DeepSeek V4.1 Flash 的 API 名为 `deepseek-flash`（人工打开官方更新页确认） | 各家模型清单 | 参赛：gpt-6.1-terra / claude-sonnet-5-5 / gemini-3.8-flash / deepseek-flash / kimi-k3.1-pro | Claude Code + WebSearch + 人工核对 | step-10-models.png |
| 11 | 设计 50 条测试用例矩阵：6 场景 × 8 类客群 × 用例类型（core / risk / adversarial），每条写明 must / must_not 作为评估期望 | 客群设计、品牌规则 | `data/test_matrix.yaml` | Claude Code | step-11-matrix.png |
| 12 | 3 个子代理并行将矩阵扩写为完整输入（客户档案、CA、聊天记录、产品/活动）；自动校验 + 人工抽查；修正矩阵中除夕日期错误、去除重名客户 | 测试矩阵 | `data/cases/C01–C50.json`，50/50 通过校验 | Claude Code 子代理 ×3 + `scripts/validate_cases.py` | step-12-cases.png |
| 13 | Bake-off：10 条代表性用例 × 5 模型跑 v1；Kimi 触发 429（账户并发 1）与超长延迟，改串行补跑 | 10 条用例 | 4 个模型完整结果 + 自动指标（耗时、规则违规、改写率、长度、多样性） | `scripts/run_batch.py` | step-13-bakeoff.png |
| 14 | 双 judge（GPT / Claude）交叉评分；发现统计脚本把“无（但……）”误计为红线，改为三级严重度；发现自评偏差 | bake-off 输出 | `runs/bakeoff/summary.md`；GPT 领先，两 judge 均偏爱本家 | `scripts/judge_run.py`、`bakeoff_report.py` | step-14-judge.png |
| 15 | 制作可点选的盲评页面（A–D 匿名、逐条可发送性、组排名、自动保存）；模型对应表仅存本地；加入逐次调用审计日志（实际服务模型 / token / 推理 token） | bake-off 输出 | 盲评 artifact；`blind_key_artifact.json` | Claude Code + Artifact | step-15-blind.png |
| 16 | 人工盲评 v1 中途叫停：4 个模型都有“候选 2/3 雷同”“小礼物时有时无”“替团队表态”等问题 → 判断为设计问题；提出加入可选“CA 草稿”输入、错误类型标签 | v1 盲评 | 缺陷清单 D1–D11（`docs/defects.md`）；盲评页加入错误类型 | 人工 + Claude Code | step-16-v1-review.png |
| 17 | 实现 v2：固定“极简/走心/推进”三槽位、承诺性内容只来自 CA、日历由代码计算、风险分级标准、丧亲规则、开头结尾雷同检查；冒烟测试 4 轮迭代 | 缺陷清单 | `delorme/pipeline.py run_v2`、`prompts.py V2_*`、`calendar_cn.py` | Claude Code + gpt-6.1-terra | step-17-v2.png |
| 18 | v2 bake-off（10 例 × 4 模型）并更新盲评页面（第二轮，独立存储） | 10 条用例 | `runs/bakeoff_v2/`；规则违规 0；候选间相似度 0.04–0.12 | `run_batch.py` + Artifact | step-18-v2-blind.png |
| 19 | v2 人工盲评完成并揭晓：Gemini 2.10 ≈ GPT 2.20 > Claude 2.67 > DeepSeek 3.20；发现多数“全员翻车”源于我们的 prompt（“不用回复”指令、硬字数、炫耀“我记得”、无时间感） | 人工盲评 | 缺陷 D13–D17 | 人工 + Claude Code | step-19-v2-result.png |
| 20 | 人工 vs judge 一致率：两位 judge 与人工逐条可发送性一致仅 29%，整组相关 r≈-0.3（弱） | v2 人工标注 + 双 judge | 结论：judge 不能替代人工，只能在人工定标后做规模化 | Claude Code | step-20-agreement.png |
| 21 | 实现 v3：三类用途保留、取消硬字数；删除“不用回复”类指令并列为禁用语；日历工具增加“时间线（距今多久）”；恢复各场景“推进”指引 | 缺陷 D13–D16 | `run_v2(version="v3")`、`prompts.V3_*`、`knowledge.timeline` | Claude Code | step-21-v3.png |
| 22 | v3 跑 10 例 × GPT/Gemini，发布第三轮盲评（2 组） | 10 条用例 | `runs/bakeoff_v3/`，0 失败 | `run_batch.py` + Artifact | step-22-v3-blind.png |
| 23 | v3 盲评揭晓：Gemini 1.30 > GPT 1.60，直接可发 50/60；选定 Gemini 为主生成模型。发现差异化回落（D18）与投资型异议全军覆没（D19） | 第三轮盲评 | v3.1：三条各指定切入点与唯一信息点；“绕开无解问题”原则 | 人工 + Claude Code | step-23-v3-result.png |
| 24 | 全量 50 例 v0 vs v3.1（Gemini）+ GPT judge；修正 judge 缺目录、红线无严重度的问题后重评 | 50 条用例 | v3.1 规则违规 0/150（v0 19/150），judge 不可用 30 vs 47 | `run_batch.py`、`judge_run.py` | step-24-full-v31.png |
| 25 | 讨论 D20/D21（托辞 vs 坦诚）：结论是“取舍交给 CA”，三条候选的区分方向由模型按情境自行判断；唯一硬线是不替 CA 做承诺 → v4；补充目录工艺事实；judge 读取 CA 备注 | judge 发现的缺陷 | `run_v4`、`prompts.V4_*`、`catalog.yaml craft` | 人工 + Claude Code | step-25-v4.png |
| 26 | v4 vs v4.1（再加三处小补丁）盲选 8 例：差不多 5、v4.1 胜 2、v4 胜 1 → 差距已很小，停止打磨文本，冻结 v4 | 8 条用例 | 冻结版本 v4 | 人工盲选 + Artifact | step-26-freeze.png |
| 9 | 冒烟测试：“生日 + 未解决投诉”与“AI 创业者比价要折扣”两个样例。首次运行因 API 超时被 SDK 内部重试拖慢（约 40 分钟），加入逐次调用日志并关闭 SDK 隐式重试后单例约 30 秒 | 2 个样例 | v1 正确识别投诉风险（hold）并先致歉后祝福；价格异议守价且不评价代购。发现缺陷苗头：替 CA 承诺具体回复时间（“下午6点前”） | Claude Code + OpenAI gpt-5.5 | step-09-smoke.png |
