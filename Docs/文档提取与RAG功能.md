# AlphaPilot 文档感知 RAG 增强方案 Proposal (v2)

## 1. 背景与目标

### 1.1 当前系统现状

AlphaPilot 采用 **Evidence Packet 中心化 + 多层防幻觉体系** 的架构：

| Layer | 职责 |
|-------|------|
| Layer 0 | Evidence Packet Builder 统一构造证据 |
| Layer 1 | 字段级 `Fact` Schema（含 source、as_of_date、confidence） |
| Layer 2 | 输出等级门控（full / limited / data_summary / insufficient） |
| Layer 3 | Agent 仅消费 Evidence Packet（`tools=[]`） |
| Layer 4 | Guard Agent 硬规则校验 |

当前 Evidence Packet 以**结构化字段级事实**为主，对非结构化长文档（年报、电话会议记录、研报）的支持不足，无法满足复杂基本面分析和定性洞察需求。

### 1.2 目标

为 AlphaPilot 引入**文档感知 RAG** 能力，实现：

- 支持用户上传或系统自动摄取的长文档（年报、财报电话会议、券商研报等）
- 将文档内容结构化地纳入 Evidence Packet，形成 **structured_facts + document_evidence** 双轨证据体系
- 在保持现有松耦合架构和多层防幻觉能力的前提下，提升系统对非结构化信息的利用能力
- 符合香港 SFC 对 GenAI 用于投资研究的合规要求（可审计、可解释、证据 grounding）

## 2. 整体架构愿景

采用 **Evidence Packet 作为唯一事实来源** 的松耦合设计：

```text
用户查询 (symbol + query)
    ↓
Orchestrator
    ↓
Evidence Packet Builder (Layer 0)
├── 结构化数据采集 (yfinance / HKEX API)
└── 文档感知 RAG 检索（新增）
    ↓
Evidence Packet（双轨）
├── structured_facts: list[Fact]
└── document_evidence: list[DocumentChunk]   ← 新增
    ↓
各 Specialist Agent（Market / Fundamental / Risk / Strategy 等）
└── tools=[]，仅消费 Evidence Packet
    ↓
Guard Agent (Layer 4)
    ↓
最终输出（带来源引用 + confidence + output_level）
```

**核心设计原则**：

- RAG 模块只负责**证据召回与结构化**，不直接参与推理
- 所有 Agent 严格通过 Evidence Packet 获取信息（松耦合）
- 文档证据与结构化事实并行管理，便于 Guard 做来源追溯和一致性校验

## 3. 技术方案

### 3.1 文档类型与处理策略

| 文档类型 | 来源 | 处理策略 | 优先级 |
|----------|------|----------|--------|
| 公司年报/半年报 | HKEX / 用户上传 | 结构感知分块 + 表格提取 | 高 |
| 财报电话会议记录 | 用户上传 / 公开 | 角色感知分块（Q&A） | 高 |
| 券商研报 | 用户上传 | 语义分块 | 中 |
| 新闻与公告 | 自动化采集 | 固定大小 + 实体过滤 | 中 |

### 3.2 文档解析与分块策略

采用 **Layout-aware + Structure-aware** 混合分块：

| 文档类型 | 分块策略 | 参数 | 说明 |
|----------|----------|------|------|
| 年报类 | 结构感知切块 | chunk_size=1200, overlap=200 | 按 `#` `##` 标题层级切章节，表格单独 chunk |
| 电话会议记录 | 角色感知切块 | chunk_size=1000, overlap=100 | 按说话人 + Q&A 轮次切块 |
| 通用/研报 | 语义切块 | chunk_size=800, overlap=150 | 先按标题切章节，再按段落语义合并 |

解析工具选型：优先使用 `MarkItDown` + `Unstructured.io`，复杂表格辅以布局模型。

### 3.3 元数据与 Evidence Schema 扩展

新增 `DocumentChunk` 类型，与原有 `Fact` 并行：

```json
{
  "chunk_id": "0700.HK_annual_2024_RiskFactors_p45",
  "content": "...",
  "source": "HKEX",
  "doc_id": "0700.HK_annual_2024",
  "doc_type": "annual_report",
  "section": "Risk Factors > Regulatory Risk",
  "page": "45-47",
  "publish_date": "2025-03-20",
  "report_period": "2024-12-31",
  "symbol": "0700.HK",
  "contains_table": true,
  "language": "zh"
}
```

Evidence Packet 扩展为双轨结构：

```
structured_facts:   list[Fact]
document_evidence:  list[DocumentChunk]
```

### 3.4 检索与混合排序

```text
1. 元数据预过滤（symbol + doc_type + report_period）
2. 向量检索（BGE-large-zh-v1.5 / all-MiniLM-L6-v2）
3. 全文检索（FTS5）
4. RRF 融合 + 时效性加权（近 90 天权重最高，超过 1 年显著衰减）
5. 返回 Top-N chunk 写入 document_evidence
```

### 3.5 与现有防幻觉体系的集成

| Layer | 变更 |
|-------|------|
| Layer 0 | Evidence Packet Builder 新增文档 RAG 路径 |
| Layer 2 | 输出等级判断同时考虑结构化字段完整度和文档覆盖度 |
| Layer 3 | Agent prompt 明确区分两种证据的使用方式 |
| Layer 4 (Guard) | 新增文档来源 grounding 检查（定性结论必须 traceable 到 chunk_id） |

## 4. 用户上传文档处理策略

为降低风险，采用分层管控：

| 层级 | 策略 |
|------|------|
| 公开知识库 | 仅收录已公开披露的 HKEX/SEC 文件，自动化定时更新 |
| 用户上传 | 默认仅在当前 session / 当前用户私有空间生效，不持久化进入共享知识库 |
| 上传校验 | 强制提取元数据并进行基础敏感信息扫描 |
| 来源标记 | 用户上传内容标记为 `source: user_uploaded`，Guard 对其赋予较低置信度权重 |

## 5. 风险分析与应对

### 5.1 监管与合规风险（SFC）

**风险**：使用 GenAI 生成投资研究属于 SFC 定义的 high-risk use case。

**应对**：
- 所有输出强制带来源引用（`structured_facts` + `document_evidence`）
- 实现完整 audit trail（记录每次回答引用的 chunk_id 和 Fact）
- 输出等级门控 + Guard 硬规则，证据不足时自动降级或拒答
- 在产品界面和报告中加入明确免责声明

### 5.2 时效性与数据质量风险

**风险**：年报、研报过期导致分析基于旧数据。

**应对**：
- 元数据强制包含 `publish_date` 和 `report_period`，检索时应用时效性加权
- 冲突文档自动标记 `superseded` 版本

### 5.3 上下文窗口与性能风险

**风险**：向量库膨胀、上下文窗口超限、查询延迟增加。

**应对**：
- 两级检索（元数据过滤 → 向量召回）
- 设置每 symbol 文档 chunk 上限
- 优先返回高置信度 chunk

### 5.4 用户上传带来的额外风险

**风险**：用户上传可能包含内幕信息、个人隐私或未经核实的内容。

**应对**：
- 默认 session 隔离 + 来源标记 + 降低置信度权重
- 用户需确认内容合法性

## 6. 实施路线图

| 阶段 | 内容 | 周期 |
|------|------|------|
| Phase 1 (MVP) | 单 PDF 上传解析 + 基础结构感知分块 + 写入 document_evidence | 2 周 |
| Phase 2 | Evidence Packet 双轨 Schema 落地 + Guard 文档 grounding 增强 | +2 周 |
| Phase 3 | 公开文档自动化摄取（HKEX 年报）+ 时效性加权 + RRF 混合检索 | +2 周 |
| Phase 4 | 用户上传私有空间隔离 + 输出等级与文档覆盖度联动 + A/B 测试框架 | +2 周 |

## 7. 成功指标

| 指标 | 目标值 | 测量方式 |
|------|--------|----------|
| 文档检索 Recall@15 | ≥ 82% | 人工标注测试集 |
| 关键章节覆盖率（年报） | ≥ 85% | 人工评估 MD&A / Risk Factors |
| Guard 拦截未 grounding 结论 | ≥ 90% | 人工抽检 |
| 单次查询 P95 延迟 | ≤ 4s | 监控 |
| 输出带来源引用比例 | 100% | 自动统计 |

## 8. 预期收益

1. 显著提升系统对定性信息（风险、战略、管理层观点）的理解能力
2. 在保持现有强防幻觉体系的前提下，扩展证据来源
3. 为后续多 Agent 深度协作和更复杂的投资研究场景打下基础
4. 符合 fintech 岗位对生产级 RAG + 合规意识的要求

## 9. 详细实现计划

### Phase 1 — MVP：单文档上传 + 基础分块 + 写入向量库 + 检索

#### 9.1 新增 DocumentChunk Schema

**文件**：`alphapilot/schemas/evidence_packet.py`

在 `Fact` 同级新增：

```python
class DocumentChunk(BaseModel):
    chunk_id: str          # "0700.HK_annual_2024_RiskFactors_p45"
    content: str           # chunk 文本
    source: str            # "HKEX" / "user_uploaded"
    doc_id: str            # 所属文档唯一 ID
    doc_type: str          # "annual_report" / "earnings_call" / "research_report" / "news"
    section: str = ""
    page: str = ""
    publish_date: str = "" # "2025-03-20"
    report_period: str = ""# "2024-12-31"
    symbol: str = ""
    contains_table: bool = False
    language: str = ""
```

在 `EvidencePacket` 新增：

```python
document_evidence: list[DocumentChunk] = []
```

在 `Coverage` 新增：

```python
document_evidence: str = "missing"
```

#### 9.2 新增 DocumentChunker 模块

**文件**：`alphapilot/knowledge/document_chunker.py`（新建）

| 函数 | 说明 |
|------|------|
| `chunk_by_headings(text)` | 按 `#` / `##` 标题层级切分章节，返回 `[{section, content}]` |
| `chunk_semantic(text, chunk_size=800, overlap=150)` | 基于段落 + token 计数合并，返回 `list[str]` |
| `chunk_with_metadata(doc_type, text, metadata)` | 根据 doc_type 选择分块策略，附加元数据 |

#### 9.3 新增 PDFParser 模块

**文件**：`alphapilot/knowledge/pdf_parser.py`（新建）

| 函数 | 说明 |
|------|------|
| `parse_pdf(file_path)` | 调用 `markitdown` 或 `pymupdf`(fitz) 提取文本；pymupdf 输出自动推断章节标题 |
| `extract_tables(file_path)` | **pdfplumber 优先**（轻量免 Java），camelot 回退；表格按页码归属对应章节 |
| `parse_and_chunk(file_path, metadata)` | 解析 + 表格注入章节 + 分块一站式，返回 `list[dict]` |

依赖：

```
# requirements.txt（必需 — PDF 文本提取 + 表格提取）
markitdown>=0.0.1a3
pymupdf>=1.24.0
pdfplumber>=0.11.0       # 默认表格后端（M1 起从 optional 升级）

# requirements-optional.txt（可选 — 复杂表格/扫描件）
camelot-py[cv]>=0.11.0   # 需 Java + Ghostscript，pdfplumber 不可用时自动回退
```

环境检查：`knowledge/pdf_env.py` → `check_pdf_parse_dependencies()` / `require_text_extraction()`。  
API 启动时打印能力摘要；`POST /api/upload/document` 上传 PDF 前校验文本提取后端。

#### 9.4 扩展 VectorStore 支持 DocumentChunk

**文件**：`alphapilot/rag/retriever.py`

| 方法 | 说明 |
|------|------|
| `add_document_chunks(chunks)` | 批量写入 chunk（含全量元数据 `_type=document_chunk`），返回成功计数 |
| `retrieve_doc_chunks(query, symbol, k=10)` | over-fetch 语义检索 + Python 后过滤 symbol/session，返回 `list[dict]` |

#### 9.5 集成到 EvidencePacket Builder

**文件**：`alphapilot/graph/workflow.py` → `evidence_packet_builder()`  
**辅助模块**：`alphapilot/graph/document_evidence.py` → `attach_document_evidence()`

在现有结构化数据采集后新增：
1. 调用 `attach_document_evidence(packet, symbol, query, k=5)`（内部 `retrieve_doc_chunks`）
2. 将返回的 chunk 转为 `DocumentChunk` 对象并写入 `packet.document_evidence`
3. 有结果时设置 `coverage.document_evidence = "available"`

#### 9.6 Agent Prompt 适配

**文件**：各 Agent（`fundamental_agent.py` / `news_agent.py` 等）；`market_agent.py` **明确忽略** Document Evidence（仅用 Verified Facts 做技术面分析）

在 `render_packet_for_agent` 中追加 `document_evidence` 的 Markdown 渲染，并为每条 chunk 分配 **`[doc:N]`** 序号（N 为 `document_evidence` 列表下标，从 1 起）：

```markdown
### Document Evidence
[doc:1] [source: 0700.HK_annual_2024, section: Risk Factors, page: 45]
...chunk content...
```

Agent 引用文档结论时应标注 `[doc:N]`；存储层 `chunk_id`（如 `0700.HK_annual_2024_RiskFactors_p45`）用于入库与 audit，Guard Level 1 校验的是 **`[doc:N]` ↔ 列表下标**，而非在输出中手写 `chunk_id` 字符串。

### Phase 2 — 双轨 Schema 落地 + Guard 增强

#### 9.7 Guard 文档 Grounding 检查

**文件**：`alphapilot/agents/guard_agent.py`

`_find_ungrounded_doc_claims(final_output_text, ep)` 返回 `(issues, warnings)`：

| 层级 | 机制 | 严重度 |
|------|------|--------|
| **Level 1** | 输出中 `[doc:N]` 必须在 `document_evidence[N-1]` 范围内 | `issues`（阻断） |
| **Level 2** | 疑似文档引用段落与 chunk 内容 embedding 相似度 ≥ 0.45；段落内已有合法 `[doc:N]` 则跳过 | `issues`（阻断） |
| **Level 3** | 中英文文档引用句式模式粗检 | `warnings`；`document_evidence` 为空时升为 `issues` |

**输出等级联动**：
- `FULL_ANALYSIS`：Level 1/2 的 `doc_grounding_issues` **降级为** `grounding_warnings`（前缀 `[FULL_ANALYSIS-downgraded]`），不阻断
- 其他等级：ungrounded doc claims 进入阻断列表

`chunk_id` 仍作为向量库主键与 audit trail；Guard 不要求 Agent 在正文中粘贴 `chunk_id`，而通过 **`[doc:N]` + 语义匹配** 建立可追溯性。

#### 9.8 输出等级联动

**文件**：`alphapilot/schemas/evidence_packet.py` → `determine_output_level()`

`coverage.document_evidence` 联动评分：
- `"available"` → evidence_score +5
- `"missing"` → 不扣分（保持原有行为不变）

### Phase 3 — 自动化文档摄取

#### 9.9 数据源适配器

**文件夹**：`alphapilot/knowledge/fetchers/`（新建）

| 文件 | 功能 |
|------|------|
| `hkex_fetcher.py` | 解析 `activestock_*.json` 得 `stockId`，从 `titlesearch.xhtml` HTML 提取年报 PDF 并入库 |
| `sec_fetcher.py` | 扩展现有 SEC API，增加定时调度 |
| `news_fetcher.py` | 扩展 `tools/news_tools.py` 中 `_fetch_news_list`，标题 + 正文全量入库 |

#### 9.10 定时调度

**文件**：`alphapilot/knowledge/scheduler.py`（新建）

- 使用 `apscheduler` 或 `asyncio.create_task` 定时拉取
- 每 symbol 最多保留 20 份文档（按 `publish_date` 淘汰旧文档）

#### 9.11 时效性加权

**文件**：`alphapilot/rag/retriever.py` → `retrieve_doc_chunks()`

```python
days = (today - publish_date).days
weight = 1.0 if days <= 90 else 0.7 if days <= 365 else 0.3
score = similarity * weight
```

#### 9.12 RRF 混合检索

**文件**：`alphapilot/rag/retriever.py` → `hybrid_retrieve()`；`alphapilot/rag/chunk_fts.py`（FTS5）

- 向量检索 Top-20 + `sqlite3` FTS5 全文检索 Top-20
- Reciprocal Rank Fusion (k=60) 合并 → 取 Top-k（默认 10）
- `graph/document_evidence.py` 在 workflow 中调用 `hybrid_retrieve`

**Phase 3 实现状态**：✅ 9.9–9.12 已落地

| 模块 | 路径 |
|------|------|
| HKEX fetcher | `knowledge/fetchers/hkex_fetcher.py` |
| SEC fetcher | `knowledge/fetchers/sec_fetcher.py` |
| News fetcher | `knowledge/fetchers/news_fetcher.py` |
| 调度器 | `knowledge/scheduler.py`（`DOC_FETCH_ENABLED=true` 启用） |
| 统一入库 | `knowledge/document_ingest.py` |
| 文档保留 | `rag/doc_registry.py`（每 symbol 最多 20 份） |

环境变量：
- `DOC_FETCH_ENABLED=true` — 启动定时抓取
- `DOC_FETCH_SYMBOLS=TSLA,AAPL,0700.HK` — 监控标的
- `DOC_FETCH_INTERVAL_HOURS=6` — 抓取间隔（小时）

### Phase 4 — 用户上传 + 私有空间

#### 9.13 上传 API

**文件**：`alphapilot/api/upload.py`（新建）

- `POST /api/upload/document`：接收 PDF/Word/HTML，存入临时目录
- 调用 `pdf_parser.parse_and_chunk()` 分块
- 写入 `vectorstore` 带 `source: user_uploaded` + `user_session_id`
- 标记 `confidence_tier: user_submitted`

#### 9.14 Session 隔离

**文件**：`alphapilot/rag/retriever.py` → `retrieve_doc_chunks()`

- 检索时增加可选 `user_session_id` 过滤参数
- 公开知识库 chunk + 用户私有 chunk 混合返回

#### 9.15 敏感信息扫描

**文件**：`alphapilot/knowledge/sensitive_scanner.py`（新建）

- `scan(text)` → 正则匹配身份证号 / 银行卡号 / 电话 / 邮箱
- 命中后打码替换为 `[REDACTED]` 再写入向量库

**实现状态（已完成）**：

| 条目 | 实现 |
|------|------|
| 9.13 | `api/upload.py` + `main.py` `/upload/document`（需登录）→ `document_ingest.ingest_file()`，元数据 `source=user_uploaded`、`confidence_tier=user_submitted`、`user_session_id` |
| 9.14 | `retrieve_doc_chunks()` / `hybrid_retrieve()` 支持 `user_session_id`；无 session 时屏蔽私有 chunk；有 session 时公开+私有混合（`_merge_public_private_hits`） |
| 9.15 | `ingest_chunks()` 入库前调用 `sensitive_scanner.scan()`；分析链路经 `user_session_id` 传入 `attach_document_evidence()` |

### 涉及文件总览

| 文件 | Phase | 操作 |
|------|-------|------|
| `schemas/evidence_packet.py` | 1 | 新增 `DocumentChunk`、扩展 `EvidencePacket` / `Coverage` |
| `knowledge/document_chunker.py` | 1 | **新建** |
| `knowledge/pdf_parser.py` | 1 | **新建** |
| `knowledge/ingest_service.py` | 1 | 新增 `upsert_document()` |
| `rag/retriever.py` | 1 | 新增 `retrieve_doc_chunks()`、`add_chunks()` |
| `graph/workflow.py` | 1 | `evidence_packet_builder` 接入文档 RAG |
| `agents/*.py` | 1 | Agent prompt 追加 `document_evidence` 渲染 |
| `agents/guard_agent.py` | 2 | 新增 `_find_ungrounded_doc_claims()` |
| `schemas/evidence_packet.py` | 2 | `determine_output_level` 联动 |
| `knowledge/fetchers/hkex_fetcher.py` | 3 | **新建** |
| `knowledge/scheduler.py` | 3 | **新建** |
| `rag/retriever.py` | 3 | 时效性加权 + RRF 混合检索 |
| `api/upload.py` | 4 | **新建** |
| `knowledge/sensitive_scanner.py` | 4 | **新建** |

---

## 10. 实现状态与差距说明（2026-06）

### 10.1 已交付（§9.1–9.15）

| 阶段 | 条目 | 状态 | 验收方式 |
|------|------|------|----------|
| Phase 1 | 9.1–9.6 Schema / 分块 / PDF / 检索 / Workflow / Agent | ✅ | `test_rag_e2e_pipeline.py`、分析日志 `Document RAG: N chunks` |
| Phase 2 | 9.7–9.8 Guard grounding + 输出等级联动 | ✅ | `test_guard_hard_rules.py`、Guard `Valid: True` |
| Phase 3 | 9.9–9.12 Fetcher / Scheduler / 时效加权 / RRF+FTS5 | ✅ | `run_fetch_once()`、TSLA/0700.HK 抓取日志 |
| Phase 4 | 9.13–9.15 上传 / Session 隔离 / 敏感打码 | ✅ | `scripts/verify_p4.py`、`test_session_isolation.py` |

### 10.2 与 Proposal 原文的差距（未做或简化）

| 类别 | 文档描述 | 当前实现 |
|------|----------|----------|
| 路线图 §6 Phase 4 | A/B 测试框架 | ❌ 未实现 |
| 路线图 §6 Phase 4 | 输出等级与文档覆盖度深度联动 | ⚠️ 仅 9.8：`document_evidence=available` → evidence_score +5 |
| §3.4 检索 | 元数据预过滤 `doc_type` / `report_period` | ⚠️ 主要为 `symbol` + `user_session_id` 后过滤 |
| §3.4 向量模型 | BGE-large-zh-v1.5 | 使用 `all-MiniLM-L6-v2`（`RAG_EMBEDDING_MODEL` 可配） |
| §3.2 解析 | MarkItDown + Unstructured.io | pymupdf 为主，markitdown 可选；非 Markdown PDF 自动推断章节标题 |
| §9.3 表格 | camelot / pdfplumber | pdfplumber 默认启用（requirements.txt），camelot 备选 |
| §5.2 时效性 | 冲突文档 `superseded` 版本 | Fact 层有；document chunk 层未做 |
| §5.1 合规 | 完整 audit trail（每次回答记录 chunk_id） | chunk_id 入库 + Guard `[doc:N]`；无独立审计日志服务 |
| §4 上传 | 用户确认内容合法性 | 无前端确认流程 |
| §5.1 合规 | 产品免责声明 | 需在前端/报告层单独维护 |
| §7 成功指标 | Recall@15、P95 延迟、覆盖率等 | 无自动化评测与监控面板 |

### 10.3 运维与环境

- 文档自动抓取：`DOC_FETCH_ENABLED=true`，依赖 `apscheduler`
- 验收脚本：`python scripts/verify_p4.py --username ... --password ...`（HTTP 全链路）
- 运行时数据（`rag_data/faiss_index` 等）不应提交 git

### 10.4 后续可选增强（非 §9 范围）

1. A/B 框架：对比「有/无 document_evidence」对 Guard 通过率与报告质量的影响  
2. 文档级 `superseded` 与检索过滤  
3. 中文 embedding 升级（BGE-large-zh）与标注集 Recall 评测  
4. 分析审计表：记录每次 `analysis_id` 引用的 `chunk_id` 列表  
5. 上传前合规确认弹窗 + 报告免责声明模板

