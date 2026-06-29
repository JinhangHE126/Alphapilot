# AlphaPilot HK Fintech 竞争力提升 — 开发方案

> 依据 [HK-Fintech-AI-竞争力优化方案.md](./HK-Fintech-AI-竞争力优化方案.md) 拆解为可排期、可验收的工程任务。  
> 前提：RAG Phase 1–4（[文档提取与RAG功能.md](./文档提取与RAG功能.md) §9）已落地；本方案聚焦**证据质量、综合层输出、审计闭环、Demo 展示**。  
> 架构背景见 [alphapilot/Docs/architecture.md](../alphapilot/Docs/architecture.md)。

---

## 1. 目标与范围

### 1.1 业务目标

在 **2–3 周内**将 AlphaPilot 从「工程链路完整」提升到「HK Fintech AI Engineer 面试可主展示」：

| 目标 | 成功标准 |
|------|----------|
| 文档证据可用 | Demo 标的（AAPL / 0700.HK）能稳定召回 MD&A、Risk Factors 相关 chunk |
| 报告有洞察 | Recommendation 以综合结论为主，非逐 Agent 复述；含 2–3 条 `[doc:N]` 定性判断 |
| 证据可追溯 | 每次分析落库 `cited_chunk_ids`，History API 可查询 |
| 可演示闭环 | README + 1 份完整 Demo 报告（含截图/引用示例） |

### 1.2 范围（In Scope）

- PDF 解析与分块质量（表格、章节、语义 chunk_id）
- 检索 section boost
- Recommendation Agent prompt 重构
- Audit Trail 表结构与 API
- Demo 标的 ingest + 全链路跑通
- 上传确认 + 报告免责声明（轻量 UI）

### 1.3 范围外（Out of Scope，投递后再做）

- A/B 测试框架、Prometheus 监控、BGE-large-zh 全量 re-embed
- document 级 `superseded`、完整 Fact Store 冲突引擎
- 受控 Agent `tools` 扩展（Phase 2 可选，本方案仅预留接口）

---

## 2. 里程碑总览

```
Week 1                    Week 2                    Week 3（缓冲）
├─ M1 文档解析增强         ├─ M3 Audit Trail         ├─ M5 Demo 定稿
├─ M2 检索 section boost  ├─ M4 Recommendation      ├─ M6 合规 UI + README
└─ 单元/回归测试           └─ 集成测试 + History API  └─ 面试材料
```

| 里程碑 | 交付物 | 验收 |
|--------|--------|------|
| **M1** 解析增强 ✅ | pdfplumber 默认路径、表格挂 section、SEC/HKEX 章节识别 | `test_pdf_section_chunking.py` 通过；0700.HK 季报 E2E（见 `Docs/M1-M4-验收报告.md`） |
| **M2** 检索 boost ✅ | `section` / `doc_type` 加权 | `test_retriever_m2.py` 通过；`hybrid_retrieve` section/doc_type boost |
| **M3** Audit Trail ✅ | DB 落库 + API | `test_analysis_citations.py`；`GET /history/{id}` 返回 citations |
| **M4** Recommendation ✅ | 新 prompt 结构 | 0700.HK full_analysis 人工验收；Executive Synthesis + `[doc:N]` |
| **M5** Demo ✅ | AAPL + 0700.HK 各 1 份 full_analysis 报告 | Guard Valid；报告可对外展示；见 `Docs/demo/` |
| **M6** 包装 ✅ | 免责声明、上传确认、README Demo 区 | 前端可勾选确认；报告页展示免责；API consent_at 记录 |

---

## 3. Phase 1 开发任务（Week 1–2）

### 3.1 文档解析与分块（M1）

#### 3.1.1 pdfplumber 默认可用

| 项 | 内容 |
|----|------|
| **文件** | `knowledge/pdf_parser.py`, `knowledge/pdf_env.py`, `requirements-optional.txt` |
| **改动** | `extract_tables()` 优先 pdfplumber；`check_pdf_parse_dependencies()` 将 pdfplumber 标为 demo 推荐；文档注明 `pip install pdfplumber` |
| **验收** | 启动日志 `tables: pdfplumber=True`；无 camelot 时仍能提取表格 |

#### 3.1.2 表格归属章节（非堆文末）

| 项 | 内容 |
|----|------|
| **文件** | `knowledge/pdf_parser.py`, `knowledge/document_chunker.py` |
| **设计** | 解析时记录 `page → section` 映射；表格 Markdown 插入对应 section 文本或生成独立 chunk，`section` 字段填章节路径，`contains_table=true` |
| **验收** | ingest 后向量库中表格 chunk 的 `section` 含 `Risk Factors` / `MD&A` 等，而非仅 `Extracted Tables` |

#### 3.1.3 财报章节识别

| 项 | 内容 |
|----|------|
| **文件** | `knowledge/document_chunker.py`（新建 `section_detector.py` 可选） |
| **规则** | 美股 10-K：`Item 1A` → Risk Factors，`Item 7` → MD&A；港股：关键词 `风险因素`、`管理层讨论` / `MD&A` |
| **验收** | 对样例 PDF，`chunk.metadata.section` 分布覆盖目标章节 |

#### 3.1.4 语义化 chunk_id

| 项 | 内容 |
|----|------|
| **文件** | `knowledge/document_chunker.py` |
| **格式** | `{symbol}_{doc_type}_{section_slug}_p{page}`，如 `AAPL_annual_RiskFactors_p45` |
| **注意** | 保持全局唯一；与 `_known_doc_ids` 去重兼容 |
| **验收** | 新 ingest 的 chunk_id 可读；旧 chunk 不影响检索 |

#### 3.1.5 测试

| 文件 | 覆盖 |
|------|------|
| `test/test_pdf_section_chunking.py` | 章节切分、chunk_id 格式、表格 section 挂载 |
| `test/test_hkex_fetcher.py` | 回归 HKEX ingest |

---

### 3.2 检索增强（M2）

#### 3.2.1 Section / doc_type boost

| 项 | 内容 |
|----|------|
| **文件** | `rag/retriever.py` → `hybrid_retrieve`, `_vector_doc_chunk_candidates` |
| **逻辑** | 在 `recency_weight` 之后乘 section boost，例如： |

```python
SECTION_BOOST = {
    "risk factors": 1.25,
    "item 1a": 1.25,
    "md&a": 1.15,
    "management discussion": 1.15,
    "风险因素": 1.25,
    "管理层讨论": 1.15,
}
# score *= section_boost(meta.get("section", ""), query)
```

| **可选** | 查询含 "risk" / "regulatory" 时额外 boost Risk Factors chunk |
| **验收** | 固定 query 集上 Risk/MD&A chunk 进入 Top-5 比例提升（脚本 `scripts/eval_doc_recall.py` 可选） |

#### 3.2.2 元数据后过滤（轻量）

| 项 | 内容 |
|----|------|
| **文件** | `rag/retriever.py` |
| **改动** | `hybrid_retrieve(..., doc_type: str = "")` 可选过滤 `annual_report` 等 |
| **验收** | 传 `doc_type=annual_report` 时不返回 news chunk |

> **M1–M4 验收报告**：[`Docs/M1-M4-验收报告.md`](M1-M4-验收报告.md)（2026-06-28）

---

### 3.3 Audit Trail（M3）

#### 3.3.1 数据模型

| 项 | 内容 |
|----|------|
| **文件** | `db/migrations/002_analysis_citations.sql`, `db/models.py`, `db/repository.py` |

```sql
CREATE TABLE IF NOT EXISTS analysis_citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL,
    chunk_ids TEXT NOT NULL,          -- JSON array of chunk_id
    doc_markers TEXT,                 -- JSON array of [doc:N] found in report
    evidence_snapshot TEXT,           -- JSON: [{chunk_id, doc_id, section, source}]
    created_at TEXT NOT NULL,
    FOREIGN KEY (analysis_id) REFERENCES analysis_history(id)
);
CREATE INDEX idx_citations_analysis ON analysis_citations(analysis_id);
```

#### 3.3.2 写入时机

| 项 | 内容 |
|----|------|
| **文件** | `services/analysis_service.py`, `graph/workflow.py` 或 `agents/guard_agent.py` 之后 |
| **逻辑** | 1) 从 `final_report` 正则提取 `[doc:N]`；2) 映射 `evidence_packet.document_evidence[N-1].chunk_id`；3) Guard 通过后 `complete_analysis_record` 时写入 citations |
| **兜底** | 无 `[doc:N]` 时仍保存当时 `document_evidence` 的 chunk_id 列表（检索命中快照） |

#### 3.3.3 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/history/{analysis_id}` | 响应增加 `citations: { chunk_ids, evidence_snapshot }` |

#### 3.3.4 测试

| 文件 | 覆盖 |
|------|------|
| `test/test_analysis_citations.py` | 解析 `[doc:1]`、落库、API 回读 |

---

### 3.4 Recommendation Agent（M4）

> 详见验收报告 §五。

#### 3.4.1 Prompt 重构

| 项 | 内容 |
|----|------|
| **文件** | `agents/recommendation_agent.py`, `prompts/`（若有独立 prompt 文件） |
| **约束** | 禁止「逐 Agent 详细复述」；要求 Executive Synthesis 3–5 条；必须含「文档证据」小节且至少 2 条带 `[doc:N]`（当 `document_evidence` 非空） |
| **结构** | 见竞争力方案 §4.2 五段式 |

#### 3.4.2 Guard 联动

| 项 | 内容 |
|----|------|
| **文件** | `agents/guard_agent.py` |
| **改动** | `document_evidence` 非空且 Recommendation 无 `[doc:N]` 时 → warning 或 limited 降级提示（不阻断 full_analysis，可配置） |

#### 3.4.3 验收

- 同 TSLA/AAPL 输入，新报告字数下降、重复段落减少
- 含至少 2 处合法 `[doc:N]`（有 document_evidence 时）
- Guard `Valid: True`

---

### 3.5 高质量 Demo（M5）

#### 3.5.1 标的与数据

| 市场 | 标的 | 数据来源 |
|------|------|----------|
| 美股 | **AAPL** | SEC `run_fetch_once` 或手动上传 10-K |
| 港股 | **0700.HK** | HKEX fetcher（已验证 stock_id=7609） |

#### 3.5.2 执行脚本（可选）

| 文件 | 用途 |
|------|------|
| `scripts/prepare_demo_ingest.py` | 对 AAPL/0700 执行 fetch + 打印 chunk 统计（按 section） |
| `scripts/run_demo_analysis.sh` | 调用 API analyze/stream，保存 report JSON |

#### 3.5.3 产出物

- `Docs/demo/AAPL_analysis_sample.md`（脱敏摘要 + `[doc:N]` 示例）
- `Docs/demo/0700.HK_analysis_sample.md`（最新 sample；旧路径 `0700HK_analysis_sample.md` 可弃用）
- README「Demo」小节链接上述文件

---

## 4. Phase 2 开发任务（Week 2–3，包装层）

### 4.1 合规 UI（M6）

| 任务 | 文件 | 说明 |
|------|------|------|
| 上传确认 | `frontend/src/pages/AnalyzePage.tsx` | checkbox：「确认上传内容为合法公开资料或个人研究笔记」 ✅ |
| 免责声明 | `AnalyzePage.tsx` / 报告底部组件 | 固定文案：非投资建议、GenAI 生成、需人工复核 ✅ |
| API（可选） | `api/main.py` upload | 记录 `consent_at` 到 metadata 或日志 ✅ |

### 4.2 评估脚本（Medium，时间允许）

| 文件 | 说明 |
|------|------|
| `scripts/eval_doc_recall.py` | 15 条人工标注 query → Recall@5 / @15 ✅ |
| `evaluation/guard_grounding_report.py` | 统计 Guard doc grounding 通过率 ✅ |

### 4.3 README / 面试材料

- 更新根目录 `README.md`：Demo 截图、Audit Trail 说明、SFC 合规三点
- 架构图标注 citations 链路

---

## 5. 任务排期（建议）

### Week 1

| 天 | 任务 | 负责人 | 产出 |
|----|------|--------|------|
| D1–D2 | 3.1.1–3.1.3 解析与章节 | — | M1 80% |
| D3 | 3.1.4 chunk_id + 3.1.5 测试 | — | M1 完成 |
| D4–D5 | 3.2 检索 boost + 回归 | — | M2 完成 |

### Week 2

| 天 | 任务 | 产出 |
|----|------|------|
| D1–D2 | 3.3 Audit Trail ✅ | M3 |
| D3 | 3.4 Recommendation prompt | M4 |
| D4–D5 | 3.5 Demo ingest + 全链路分析 | M5 完成 ✅ |

### Week 3（缓冲）

| 任务 | 产出 |
|------|------|
| Demo 报告润色 + 截图 | M5 定稿 |
| 4.1 合规 UI | M6 ✅ |
| 4.2 评估脚本（可选） | 指标数字供面试 ✅（见 `Docs/M6-评估脚本开发文档.md`） |

---

## 6. 风险与依赖

| 风险 | 缓解 |
|------|------|
| DeepSeek API 余额不足 | `.env` 配置 Gemini 备用；Demo 前充值 |
| HKEX PDF 体积大、ingest 慢 | 限制单 doc chunk 上限；Demo 用单份年报 |
| 旧 FAISS 索引 chunk_id 无语义 | Demo 前对 AAPL/0700 做一次 clean re-ingest |
| Recommendation 仍冗长 | 加 max_tokens + 后处理截断 + Guard warning |

**环境依赖**：`pdfplumber`, `pymupdf`, `apscheduler`, embedding 模型可用；`DOC_FETCH_ENABLED=true`。

---

## 7. 验收清单（投递前勾选）

- [x] AAPL 或 0700.HK 年报 ingest 后，Risk Factors / MD&A 相关 chunk 可被 `hybrid_retrieve` 命中
- [x] Recommendation 报告含 Executive Synthesis + `[doc:N]` 文档小节
- [x] `GET /history/{id}` 返回 `citations.chunk_ids`
- [x] `scripts/verify_p4.py` 仍通过（回归 P4）— 2026-06-29 HTTP 模式验收通过
- [x] README 含 Demo 链接（见根目录 Demo 小节）
- [ ] README 含 2–3 张 Demo 截图（待补；链接与 sample 报告已就绪）
- [x] 分析页有免责声明；上传有确认勾选

---

## 8. 与现有文档映射

| 本开发方案 | 竞争力优化方案 | RAG 文档 §10 |
|------------|----------------|--------------|
| §3.1–3.2 | §4.1 Document Evidence | §10.2 表格/section |
| §3.3 | §4.3 Audit Trail ✅ | §10.2 audit trail |
| §3.4 | §4.2 Recommendation | — |
| §3.5 | §4.4 Demo | §10.1 已交付基线 |
| §4.1 | §3.2 Medium 合规 | §10.2 上传/免责 |
| Out of Scope | §3.3 Low | §10.4 后续增强 |

---

## 9. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-06-28 | 初版：由竞争力优化方案拆解为工程任务、里程碑与排期 |
| 2026-06-28 | M1–M4 验收完成：见 `Docs/M1-M4-验收报告.md`；里程碑表 M1–M4 ✅ |
| 2026-06-29 | M5 Demo 完成：`scripts/prepare_demo_ingest.py`、`scripts/run_demo_analysis.sh`、`Docs/demo/AAPL_analysis_sample.md`、`Docs/demo/0700.HK_analysis_sample.md`、README Demo 小节 ✅ |
| 2026-06-29 | M6 合规 UI 完成：上传确认 checkbox、报告底部免责声明、API consent_at 审计日志 ✅ |
| 2026-06-29 | M6 评估脚本完成：`scripts/eval_doc_recall.py`、`evaluation/guard_grounding_report.py`；修复见 `Docs/M6-评估脚本开发文档.md` §5 |
| 2026-06-29 | P4 回归：`alphapilot/scripts/verify_p4.py` HTTP 模式验收通过；§7 清单 P4 项 ✅ |
| 2026-06-29 | **方案关账**：M1–M6 工程交付完成；§7 仅剩 README Demo 截图待补 |
