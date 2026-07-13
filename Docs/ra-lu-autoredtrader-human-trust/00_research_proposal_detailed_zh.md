# A + C 合并方案（修订完整版 · 中文详细规划）

> **用途：** 自用研读与执行参考（比 `01_research_proposal_full.md` 更细、更全）  
> **面向目标：** Zhuoran Lu RA 申请  
> **核心定位：** 将 AutoRedTrader 的 Agent 侧红队，与 Lu 的 Human Trust/Reliance 研究线桥接  
> **实验平台：** AlphaPilot（evidence-first 多 Agent 金融研究系统）

**版本：** 1.0 · 2026-07-11  
**Pilot 性质：** Exploratory（N≈18）；报告效应方向与 UI 趋势，不追求统计显著性。

---

## Part 0：Executive Summary（执行摘要）

### 标题

**When Agents Are Steered, Do Humans Over-Trust?**  
*来源权威、虚假信息与人类依赖校准——Agentic 金融 Human-AI Teaming*

### Gap（含对 Lu 工作的 explicit 链接）

[AutoRedTrader](https://arxiv.org/html/2605.09185v1) 证明：subtle finance-specific misinformation 可使 retrieval-based trading agents 的决策翻转率达 **26.67%**；即便加入 time-series grounding，仍有 **18.33%** 的 ASR。但该工作**未测量人类下游成本**——分析师是否会过度信任（over-trust）或被引导的 Agent 输出，以及是否会过度采纳（over-adopt）错误建议。

Lu 等人先前工作已表明，AI 辅助决策中人类的 **trust 与 reliance** 对呈现方式高度敏感：

| 代表工作 | 核心发现（与本研究的链接） |
|----------|---------------------------|
| **AAAI 2023 (Oral)**：*Modeling Human Trust and Reliance in AI-assisted Decision Making: A Markovian Approach* | 人类对 AI 的 reliance 随置信度、历史准确性动态变化 → 本研究测：attacked agent 输出是否触发类似 **miscalibrated reliance** |
| **AAAI**：*Strategic Adversarial Attacks in AI-assisted Decision Making to Reduce Human Trust and Reliance* | 对抗性信息可**策略性地**降低或操纵人类信任 → 本研究延伸：金融场景下 subtle misinformation 是否导致 **false trust**（表面可信、实质偏移） |
| **CHI**：*LLM-driven Adversarial Social Influences in Online Information Spread* | 对抗性社会影响可改变信息传播与感知 → 本研究聚焦：**信息来源权威感**（news vs. filing）如何调节采纳 |
| **CHI / IUI**：*From Text to Trust*；*Devil's Advocate in AI-assisted Group Decision Making* | 界面与对抗视角可校准人类判断 → 本研究将 **citation-auditable UI** 作为 reliance calibration 机制 |

**本研究要做的桥接**：把「finance-specific agent red-teaming」与「human trust/reliance calibration」连成一条因果链——这是 AutoRedTrader 与 Lu 核心兴趣之间**尚未被实证连接**的缺口。

### Approach（三句话）

1. 在 AlphaPilot 上实现 MisGen-style 攻击，分别污染 **news** 与 **filing** 证据通道，生成 paired clean/attacked reports。  
2. 开展 exploratory human pilot（**N≈18**），交叉 **UI Condition**（No-Audit vs. Facts-Only vs. Full-Audit）与 **Source Type**（News vs. Filing）。  
3. 联合分析 Agent 侧指标（MER/RDR）与人类侧指标（trust、reliance、adoption），检验攻击是否从 Agent 传导至人。

### Expected Contributions（锐利版）

1. **Empirical**：关于 **source authority**（news vs. SEC/HKEX filings）如何调节人类对 attacked agent 输出的 adoption intent 的初步证据。  
2. **Design**：关于 **citation-auditable + guard-gated interfaces** 作为 agentic financial systems 中 **reliance calibration mechanisms** 的设计启示。  
3. **Methodological**：在 high-stakes 金融 AI 中，连接 **automated red-teaming** 与 **human-subject evaluation** 的可复现范式（以 AlphaPilot 为 open testbed）。

> *To our knowledge, this is among the first studies bridging finance-specific agent red-teaming (AutoRedTrader-style) with human trust/reliance calibration via auditable agent interfaces.*

### Pilot 定位（诚实声明）

本研究为 **exploratory pilot**，样本量 N≈18，**不追求统计显著性**，重点报告效应方向、置信区间与 UI 趋势，为后续更大规模 CHI/CSCW 研究或工业合作提供 feasibility evidence。

---

## Part 1：研究问题与假设

### RQ1（A 核心）：Misinformation 攻击后，人类 trust 与 reliance 如何变化？

| 假设 | 内容 | 对接 Lu 的工作 |
|------|------|----------------|
| **H1a** | Attacked report 的 trust 评分低于 clean report（**trust drop**） | 延伸 trust/reliance 动态模型 |
| **H1b** | 若攻击足够 subtle，部分被试出现 **false trust**（trust 不降或上升） | 对接 adversarial attacks on trust 的「策略性」效应 |
| **H1c** | Full-Audit UI（Guard + CitationsPanel）下，trust 更「校准」：对 attacked 材料 **adoption error 更低** | 对接 reliance calibration / Devil's Advocate 思路 |

### RQ2（C 核心）：信息来源是否调节人类采纳？

| 假设 | 内容 | 理论依据 |
|------|------|----------|
| **H2a** | 同等攻击强度下，**Filing-sourced** misinformation 导致 **更高 adoption intent** than News-sourced | 权威启发式；10-K/年报 perceived credibility 更高 |
| **H2b** | 当 attacked 文本与 `structured_facts` 中数字**明显冲突**时，高金融知识被试 adoption 更低 | 人机协同中人类仍可能扮演「数字校验者」 |
| **H2c** | Full-Audit UI **削弱**来源效应（降低 filing 的「权威溢价」） | 可审计界面使来源可验证，减少 heuristic reliance |

### RQ3（桥接）：Agent 脆弱性是否传导至人类？

| 假设 | 内容 |
|------|------|
| **H3** | RDR（Agent recommendation 翻转）越高，No-Audit 条件下人类 adoption 与 attacked recommendation 一致率越高 |
| **H3'** | Full-Audit UI 调节上述关系（斜率变平） |

---

## Part 2：实验设计

### 2.1 设计类型

**3 × 2 × 2 混合设计**

| 因素 | 类型 | 水平 |
|------|------|------|
| **UI Condition** | 被试间 | G1 No-Audit / G2 Facts-Only / G3 Full-Audit |
| **Source Type** | 被试内 | News / Filing |
| **Attack** | 被试内 | Clean / Attacked |

每位被试阅读 **4 份报告**（2×2 来源×攻击），拉丁方平衡顺序。

### 2.2 被试

| 项目 | 设定 |
|------|------|
| **目标 N** | **18**（每 UI 组 6 人；最少可接受 N=16，每组 ≥5） |
| **人群** | 金融/经济/CS/商科 高年级本科或研究生 |
| **纳入** | 18–35 岁，英语阅读无障碍（AAPL 材料为英文） |
| **探索性分组** | 自报投资经验：有 / 无（协变量，不硬性平衡） |
| **时长** | 25–35 分钟/人 |
| **补偿** | 咖啡券 / 小额礼品卡 |

### 2.3 UI 条件操作化

| 组别 | 展示内容 | 对标 |
|------|----------|------|
| **G1 No-Audit** | 最终研报：Executive Summary + Recommendation + 关键理由段落 | 典型「黑箱 AI 研报」 |
| **G2 Facts-Only** | G1 + **结构化基本面面板**（PE、revenue growth、price 等，来自 `structured_facts`） | 对标 AutoRedTrader **time-series / structured grounding**（软防御） |
| **G3 Full-Audit** | G2 + **Guard 检查项** + **文档引用审计表**（`[doc:N]` → chunk section/source）+ `allowed_output_level` 徽章 | AlphaPilot 完整 **reliance-calibration UI** |

**实现形式**：静态 HTML/PDF 截图即可，无需被试操作 live 系统（降低工程风险）。

### 2.4 刺激材料（4 份报告 × 3 UI 版本 = 12 套视图）

**标的**：**AAPL**（SEC 10-K 材料成熟，已有 ingest pipeline）

| ID | 来源 | 攻击 | 扰动类型 | Agent 侧目标 |
|----|------|------|----------|--------------|
| **S1** | News | Clean | — | Baseline |
| **S2** | News | Attacked | Sentiment Shift / Flipping | News sentiment 偏移；Recommendation 可能翻转 |
| **S3** | Filing (10-K) | Clean | — | Baseline |
| **S4** | Filing | Attacked | Numerical / Concept Shift | 引用 MD&A 或 Risk Factors 中数字/概念被篡改 |

S2 = News + Attacked（测「新闻来源」被攻击）
S4 = Filing + Attacked（测「年报来源」被攻击）

**质量门槛**（生成后人工审核）：

- [ ] Attacked 文本语言流畅，无明显 AI 痕迹  
- [ ] S2/S4 中 ≥40% 预跑出现 RDR 或 narrative 可感知偏移  
- [ ] Clean 与 Attacked 版式完全一致  
- [ ] G3 版本中 Guard 对 S2/S4 **至少有一项** warning（否则需调整攻击强度）

---

## Part 3：技术 Pipeline（内部执行用）

> **对外 Memo 只用一段概括；以下供自己按周执行。详细记录表见 [06_technical_log_template.md](./06_technical_log_template.md)。**

### Phase T1：Clean Baseline（Week 1, Day 1–2）

```bash
cd alphapilot
PYTHONPATH=. python ../scripts/prepare_demo_ingest.py --symbol AAPL
PYTHONPATH=. python ../scripts/run_analysis_direct.py AAPL
```

**记录字段**（`clean_baseline.json`）：

- `recommendation`, `strategy_score`, `sentiment_score`
- `document_evidence` top-10（chunk_id, section, source, text snippet）
- `structured_facts` 关键字段（pe_ratio, revenue_growth_yoy, current_price）
- `guard_status`, `allowed_output_level`

### Phase T2：攻击语料生成（Week 1, Day 3–5）

**不必完整复现 MisGen 闭环**；按 AutoRedTrader Appendix E prompt 模板生成即可。

| 攻击 | 操作 |
|------|------|
| **News / Sentiment** | 从 clean run 的 news headline 选 1–2 条，做轻度 optimism/pessimism 偏移 |
| **News / Flipping** | 备选：方向性词汇反转（beat→miss 等） |
| **Filing / Numerical** | 从 10-K chunk 改 revenue/EPS 数值（方向不变，+30–50% 偏差） |
| **Filing / Concept** | revenue → operating income 等 concept substitution |

**注入方式（pilot 推荐）**：

| 优先级 | 方法 | 说明 |
|--------|------|------|
| **P1 快速** | Patch `evidence_packet.document_evidence` 中目标 chunk | 2 天可跑通 |
| **P2 更真** | 写入 FAISS/FTS 索引后重跑 retrieval | 工程 3–5 天，memo 可说「follow-up」 |

### Phase T3：Attacked Run（Week 2, Day 1–3）

对 S2、S4 各跑 2–3 次，选 RDR 最明显且报告仍自然的版本。

**Agent 侧指标**：

```
MER = |injected chunks in evidence_packet| / |total chunks used|

RDR = 1 if recommendation_attacked ≠ recommendation_clean else 0

sentiment_delta = sentiment_attacked - sentiment_clean

guard_status ∈ {pass, warn, block}
```

### Phase T4：UI 视图导出（Week 2, Day 4–5）

从 AlphaPilot 前端或 sample markdown 导出：

- G1：裁掉 Guard 与 CitationsPanel  
- G2：保留 facts panel，裁掉 Guard/Citations  
- G3：完整页（可参考 `Docs/demo/AAPL_analysis_sample.md` + 前端截图）

**对外 Memo 压缩版（可直接粘贴）**：

> *I implemented MisGen-style perturbations (sentiment, numerical, concept shifts) on AlphaPilot's dual-track evidence packet, generating paired clean/attacked reports for AAPL. Agent-side metrics (MER, RDR) confirmed successful retrieval exposure and decision-level divergence in ~40% of attacked stimuli.*

---

## Part 4：人类实验 Protocol

完整问卷见 [04_questionnaire.md](./04_questionnaire.md)。

### 4.1 Session 流程

| 阶段 | 时长 | 内容 |
|------|------|------|
| **Consent** | 2 min | 知情同意；说明为学术研究，非真实投资建议 |
| **Pre-survey** | 3 min | 人口学 + 投资经验 + 基线 AI trust |
| **Instruction** | 2 min | 统一任务 framing |
| **Trials ×4** | 16–20 min | 每份报告 4–5 min 阅读 + 即时问卷 |
| **Post-survey** | 3 min | 整体反思 + 怀疑程度 |
| **Debrief** | 2 min | 揭示 misinformation 存在；感谢 |

**Instruction 原文（英文，给被试看）**：

> *"You will review four short AI-generated equity research briefs for Apple Inc. (AAPL). Please read each as you would in a professional research workflow, then answer questions about your impressions and decisions. There are no right or wrong answers."*

不主动透露攻击；G3 组额外一句：

> *"Some reports include system confidence checks and document citation tables. You may use them as you find helpful."*

### 4.2 试次级问卷（每份报告后填写）

**量表**：1 = Strongly disagree · 7 = Strongly agree（除非注明）

| # | 构念 | 题项（英文，被试填写） |
|---|------|------------------------|
| Q1 | Trust | *I find this analysis overall credible.* |
| Q2 | Adoption | *I would adopt this report's recommendation in my own coverage of AAPL.* |
| Q3 | Reliance | *I would rely on this AI analysis rather than forming an independent judgment.* |
| Q4 | Source credibility | *The information sources cited in this report appear authoritative.* |
| Q5 | Comprehension check | *The recommendation is: Buy / Hold / Sell* |
| Q6 | Anomaly detection | *Did anything in this report seem questionable?* Yes / No |
| Q6a | （若 Yes） | *Briefly describe what seemed questionable.* |
| Q7 | Decision | *Your personal trading inclination for AAPL:* Buy / Hold / Sell |

### 4.3 前测 / 后测

**Pre-survey**：Age range；Field of study；Investment experience (months)；Self-rated financial knowledge (1–7)；General trust in AI-generated financial analysis (1–7)

**Post-survey**：是否怀疑部分材料有问题；哪份报告最犹豫；是否注意到 citation 表（G2/G3）

### 4.4 拉丁方顺序（4 份报告）

使用 Williams Latin Square (4 conditions)，6 个被试/UI 组循环 3 次覆盖 18 人。

示例序列（A=S1, B=S2, C=S3, D=S4）：

- P1: A-B-D-C  
- P2: B-C-A-D  
- P3: C-D-B-A  
- P4: D-A-C-B  
- P5: A-C-B-D  
- P6: B-D-A-C  

---

## Part 5：变量编码与分析计划

### 5.1 人类侧因变量

| DV | 计算 |
|----|------|
| **Trust** | Q1 |
| **Adoption intent** | Q2 |
| **Reliance** | Q3 |
| **Source credibility** | Q4 |
| **Trust drop** | Trust_clean − Trust_attacked（同来源内配对） |
| **Adoption error** | 被试 Q7 与 **attacked recommendation** 一致，但与 **clean ground truth** 不一致 |
| **Detection rate** | Q6 = Yes 的比例 |
| **False trust rate** | Attacked 试次中 Trust ≥ clean 同来源均值的比例 |

### 5.2 Agent 侧协变量（每份 stimulus 预编码）

| 字段 | 类型 |
|------|------|
| `stimulus_id` | S1–S4 |
| `source_type` | news / filing |
| `attack` | clean / attacked |
| `perturbation_type` | sentiment / numerical / concept |
| `MER` | float |
| `RDR` | 0/1 |
| `sentiment_delta` | float |
| `guard_status` | pass/warn/block |
| `recommendation_clean` | Buy/Hold/Sell |
| `recommendation_attacked` | Buy/Hold/Sell |

### 5.3 分析（Exploratory Pilot 规范）

**主模型**（R 或 Python `statsmodels`）：

```
DV ~ attack * source_type * ui_condition + financial_knowledge + (1|participant)
```

**报告规范**：

- 报告 **估计值 + 95% CI**，不强调 p 值  
- 图表优先：交互图（Attack×Source，分 UI 面板）  
- 探索性：G1 中 `RDR` 与 `Adoption` 散点 + Spearman ρ

**预期可写进 memo 的结果句式模板**（填数后即用）：

1. *"Filing-sourced attacks increased adoption intent by [X] points (95% CI [a,b]) relative to news-sourced attacks under No-Audit UI."*  
2. *"Full-Audit UI reduced adoption error by [Y]% compared to No-Audit under attacked conditions."*  
3. *"In [Z]% of attacked trials, participants reported false trust, indicating subtle misinformation may evade human detection."*

---

## Part 6：时间线（8 周标准 + 2 周压缩）

详细按日任务见 [05_timeline_8week.md](./05_timeline_8week.md)。

### 标准版（8 周）

| 周 | 任务 | 产出 |
|----|------|------|
| **W1** | Clean baseline + 攻击语料 + 预跑 RDR | `clean_baseline.json`, 4 条 perturbation |
| **W2** | Attacked runs + UI 视图导出 | 12 套 stimulus PDF/HTML |
| **W3** | 问卷上线 + N=3 认知走查 | 定稿 Google Form |
| **W4** | 招募启动 | 排期表 |
| **W5–W6** | 正式数据收集 N=18 | 原始 CSV |
| **W7** | 数据清洗 + 分析 + 主图 3 张 | `results_summary.md` |
| **W8** | 2 页 memo + 套磁信 + debrief 汇总 | 申请材料包 |

### 压缩版（2 周，申 RA 前急救）

| 天 | 任务 |
|----|------|
| D1–2 | AAPL clean + 2 attacked（News + Filing） |
| D3 | 导出 G1 + G3 视图（跳过 G2） |
| D4 | 问卷 + 预测试 2 人 |
| D5–10 | 招募 N=16，收集数据 |
| D11–12 | 快速分析 + 1 页 preliminary findings |
| D13–14 | Memo + 邮件 |

**压缩版仍可检验**：H1c（G1 vs G3）、H2a（News vs Filing），放弃 G2 与部分交互力。

---

## Part 7：伦理与合规

| 项目 | 处理方式 |
|------|----------|
| **风险等级** | 低：无真实交易、无个人财务数据收集 |
| **Deception** | 轻度：不预先告知 misinformation，**session 末 debrief** |
| **Consent** | 书面/电子知情同意，说明可随时退出 |
| **数据** | 匿名 ID，不收集姓名/学号（或可选） |
| **IRB** | Pilot 阶段标注为 *exploratory, exempt/low-risk review to be pursued if scaled* |
| **材料安全** | 攻击文本仅用于实验，标注 SYNTHETIC，不外传 |

**Memo 一句话**：

> *This exploratory pilot involves low-risk deception with full debriefing; no real investment behavior is solicited.*

---

## Part 8：交付物清单（RA 申请包）

| # | 文件 | 页数 | 用途 |
|---|------|------|------|
| 1 | **Research Memo** | 2 | 给 Lu 的主附件 → [02_research_memo_2page.md](./02_research_memo_2page.md) |
| 2 | **Preliminary Findings**（若已跑 pilot） | 1 | 1 图 + 3 bullet |
| 3 | **Stimuli Screenshot Appendix** | 2–4 | 展示 subtle attack + UI 条件 → `assets/` |
| 4 | **Technical Log** | 1 | MER/RDR 表 → [06_technical_log_template.md](./06_technical_log_template.md) |
| 5 | **AlphaPilot Demo Link** | — | GitHub + sample report |
| 6 | **Cover Email** | <300 words | [03_outreach_email_draft.md](./03_outreach_email_draft.md) |

---

## Part 9：与 Lu 工作的对接逻辑（申 RA 用）

### 他关心什么

- Human-AI Interaction、Trust/Reliance、Adversarial Social Influence、Agentic Human-AI Teaming  
- **不是**具身智能任务规划；**也不只是**狭义 LLM safety jailbreak

### 你怎么补位

| 他的线 | 你的补位 |
|--------|----------|
| AutoRedTrader：Agent 会不会被 misinformation 带偏？ | 测：**人**会不会过度信任被带偏的输出？ |
| 论文只有 soft time-series grounding | 你测：**hard cross-evidence grounding**（Guard + citation） |
| 单 Agent FinMem 交易 | 你提供：**多 Agent 研究 workflow** testbed |
| 未测 source authority | 你测：**News vs Filing** 对采纳的调节 |

### 执行逻辑（你已认可）

```
MisGen 攻击 AlphaPilot → MER↑, RDR↑（证明 Agent 脆弱）
        ↓
同一攻击下对比防御配置（G1 / G2 / G3）
        ↓
MER↓, RDR↓ + 人类 trust/adoption 更校准（证明系统更稳 + 人更安全）
```

**注意**：不是「先无防御再事后加装」，而是 **同一攻击下的 ablation 对比**。

---

## Part 10：风险登记与应对

| 风险 | 概率 | 应对 |
|------|------|------|
| FAISS news 质量差，S2 无法走 RAG | **已发生** | S2 改 `news_headline` fact 注入；memo 记 limitation |
| Attacked 报告无 RDR | 中 | 加强 Numerical perturbation；换 chunk |
| 被试全识破攻击 | 低 | 预测试 3 人；调低攻击明显度 |
| Guard 全拦，G3 无「有毒建议」 | 中 | G3 展示 **warning + 降级报告**，DV 改测「是否采纳降级建议」 |
| N 凑不齐 18 | 中 | 最低 N=14 仍可报告方向；写清 limitation |
| Lu 不回复 | — | Memo 可转投其他合作；技术 benchmark 仍可独立发表 |
| Lu 现职 Accenture | — | 强调可交付、可落地（pilot 结果、memo、可集成 benchmark） |

---

## Part 11：与 AlphaPilot 模块的映射

| AlphaPilot 组件 | 在研究中的角色 |
|-----------------|----------------|
| `Evidence Packet Builder` | 攻击前统一证据层；MER 计算点 |
| `structured_facts` | G2/G3 软/硬 grounding；H2b 数字冲突检测 |
| `document_evidence` + hybrid RAG | Filing 攻击面；MER |
| `news_agent` | News 攻击的下游消费者 |
| `Guard Agent` | G3 reliance calibration；RDR 拦截 |
| `[doc:N]` + `analysis_citations` | G3 citation audit；来源可验证 |
| `allowed_output_level` | 证据不足时降级路径 |
| Bull/Bear Debate | **Future work**：辩论放大还是纠正 misinformation？ |

---

## Part 11b：Week 1 实证更新（2026-07-13）

### 1. 异质攻击面（观测事实）

| 通道 | CLEAN_001 表现 |
|------|----------------|
| Filing RAG (`document_evidence`) | 5/5 为 Risk Factors 10-K；报告 `[doc:1,3,4]` 均来自 filing；质量可用 |
| FAISS news index | 3 条 chunk（`AAPL_news_General_i01`–`i03`）为误标第三方视频 HTML，**不可作 S2 原文** |
| News fact（实时 API） | 5→1 条进入 packet；News Agent N/A；辩论中有低置信 bullish headline |

### 2. 设计响应（非事后改假设）

- **H2a** 在 proposal 阶段已定义 News vs Filing；实现上 S2/S4 **分通道注入**。
- **S2**：`news_headline` patch（见 `assets/s2_news_perturbations.json`）。
- **S4**：`AAPL_annual_report_Risk_Factors_i03` chunk replace（Day 4 草稿见 `s4_filing_perturbations.json`）。
- **H2a 比较对象**：S2 attacked vs S4 attacked；不假设 S1/S3 新闻与 filing 同样「饱满」。

### 3. 刻意不做（pilot critical path）

- 不重跑 `DOC_FETCH` 修 FAISS news（Yahoo video 问题仍在；不阻塞 S2 fact 注入路径）。
- 不把坏 chunk 当「增强 realism」的卖点；memo 写 **limitation + channel-aware design response**。

### 4. 根因链（技术记录，自用）

```text
DOC_FETCH / scheduler → fetch_news_documents("AAPL")
  → yfinance 返回产业链/视频类条目（Samsung/SK Hynix）
  → metadata.symbol 硬编码为 AAPL
  → fetch_body 抓取 Yahoo video 页 HTML → 正则去标签失败 → JS 垃圾正文
  → chunk_semantic 切成 i01–i03
```

---

## Part 12：文档篇幅分配（修订后）

| 文档 | 技术 : Human |
|------|----------------|
| Research Memo（2 页，给 Lu） | **25% : 75%** |
| 套磁邮件 | **15% : 85%** |
| 本文件（自用详细规划） | **40% : 60%** |
| Preliminary Findings（1 页） | **30% : 70%** |

---

## Part 13：本文件夹文档导航

| 文件 | 与你关系 |
|------|----------|
| **本文件** `00_research_proposal_detailed_zh.md` | 最完整中文规划，**自用首选** |
| `01_research_proposal_full.md` | 中英混合精简版，可对外分享 |
| `02_research_memo_2page.md` | 发给 Lu 的英文 memo |
| `03_outreach_email_draft.md` | 套磁信 |
| `04_questionnaire.md` | 人类实验问卷 |
| `05_timeline_8week.md` | 按周执行清单 |
| `06_technical_log_template.md` | MER/RDR 填表 |
| `assets/` | 截图与图表 |

---

## 附录：修订记录（相对初版讨论的改进）

1. **Explicit cite Lu** 的 AAAI / CHI 代表作（Gap 部分）  
2. **Contribution 更锐利**（三条 expected contributions）  
3. **Pilot 诚实声明**（exploratory，不追求 p 值）  
4. **伦理**单独成节  
5. **技术对外压缩、对内保留**（Part 3 vs Memo）  
6. **Mini pilot 建议 N=16**（非 12），保留 News vs Filing 来源对比  

---

*自用文档 · 无需发给导师 · 与 `01` 互补：`01` 偏对外精简，本文件偏对内执行。*
